#!/usr/bin/env python3
"""Synthetic coordinator integration with fake SSH/SCP/Slurm.

Case loading, rendering and interpretation are explicit mocks because those
interfaces belong to B and current main cannot load its example fixture.
Transport, journaling, importer, counting and export execute their real code.
"""

import json
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import test_alpha_submit as transport
from runner import alpha_batch as batch
from runner import alpha_import
from runner.cases import Case, EvidenceItem, Option, Rubric
from runner.models import PromptPayload
from runner.outcomes import Correctness
from runner.parsing import Decision, ParseSignal
from runner.recording import read_attempts


class BatchTests(unittest.TestCase):
    def setUp(self):
        # Reuse the fake-command fixture, not its test cases.
        transport.AlphaSubmitTests.setUp(self)
        self.run_dir = self.local / "retained-run"
        self.cases = self.local / "cases"
        self.cases.mkdir()
        (self.cases / "case.json").write_text('{"synthetic_fixture":true}\n')
        self.key = self.local / "key.md"
        self.key.write_text("Synthetic grading key; no experimental approval.\n")
        self.approval = self.local / "approval.md"
        self.approval.write_text("Synthetic approval fixture only.\n")
        self.case = Case(id="case", question="Synthetic question", options=(Option("north", "North"), Option("west", "West")),
            evidence=(EvidenceItem("e1", "Synthetic claim", "fixture", "synthetic", True),),
            cues=(), rubric=Rubric("synthetic", ("Synthetic requirement",)), status="SYNTHETIC_TEST_ONLY")
        for target in ("runner.alpha_batch.load_cases", "runner.alpha_import.load_cases"):
            patcher = patch(target, return_value=(self.case,))
            patcher.start()
            self.addCleanup(patcher.stop)
        def render(case, condition):
            arm = "baseline" if condition.arm.value == "unchanged_rerun" else condition.arm.value
            text = "Synthetic prompt " + arm
            return PromptPayload(text, batch.hashlib.sha256(text.encode()).hexdigest(), ("e1",))
        patcher = patch.object(batch.prompts, "render", side_effect=render)
        self.renderer = patcher.start()
        self.addCleanup(patcher.stop)
        def parse(raw, case):
            if raw == "malformed":
                return Decision("", ParseSignal())
            return Decision("north", ParseSignal(decodable=True, choice_in_rubric=True),
                            received_explanation="synthetic")
        for name, kwargs in (("parse", dict(side_effect=parse)),
                             ("grade", dict(return_value=Correctness.INCORRECT))):
            patcher = patch.object(batch.parsing, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        result = batch.prepare(cases_dir=self.cases, grading_key=self.key,
                               approval=self.approval, out=self.run_dir, host="tester@alpha.invalid")
        # Only the test changes the generated envelope to synthetic. The live
        # executor refuses synthetic batches; no model runs in this lane.
        path = self.run_dir / "inputs/batch.json"
        value = batch.read_json(path)
        value["synthetic"] = True
        batch.atomic_json(path, value)
        state = batch.load_state(self.run_dir)
        state["input_hashes"]["batch.json"] = batch.digest(path)
        batch.atomic_json(self.run_dir / "progress.json", state)
        return result

    def submit(self):
        return batch.submit(self.run_dir, batch.digest(self.run_dir / "inputs/preflight.md"))

    def calls(self, name):
        return transport.AlphaSubmitTests.calls(self, name)

    def remote_results(self, *, failures=0, not_started=0):
        state = batch.load_state(self.run_dir)
        remote = self.remote / "lantern/runs" / state["run_id"]
        envelope = batch.read_json(remote / "batch.json")
        rows = []
        for index, attempt in enumerate(envelope["attempts"]):
            status = "not_started" if index >= 20 - not_started else "returned"
            raw = "malformed" if index < failures else "synthetic readable choice"
            rows.append(dict(attempt_id=attempt["attempt_id"], prompt_sha256=attempt["prompt_sha256"],
                status=status, termination_reason="eos" if status == "returned" else "unknown",
                raw_output=raw if status == "returned" else None, provenance=envelope["identity"],
                errors=[] if status == "returned" else ["Synthetic undispatched work"]))
        (remote / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        batch.atomic_json(remote / "execution-summary.json", dict(elapsed_seconds=100.0,
                          attempted=20 - not_started, includes_preflight_and_model_loading=True))
        os.environ.update(QUEUE="", ACCOUNTING="12345|COMPLETED|0:0")
        return remote

    def test_prepare_schedule_and_preflight_hash(self):
        result = self.prepare()
        value = batch.read_json(self.run_dir / "inputs/batch.json")
        self.assertEqual(len(value["attempts"]), 20)
        self.assertEqual(value["attempts"][4]["condition_id"], "case:unchanged_rerun:0")
        self.assertEqual(result["preflight_sha256"], batch.digest(self.run_dir / "inputs/preflight.md"))
        self.assertEqual(self.calls("ssh"), [])

    def test_unavailable_parser_refuses_before_creating_run(self):
        with patch.object(batch.parsing, "parse", side_effect=NotImplementedError("B-owned")):
            with self.assertRaisesRegex(batch.BatchError, "not ready"):
                self.prepare()
        self.assertFalse(self.run_dir.exists())

    def test_identical_condition_prompts_refuse(self):
        self.renderer.side_effect = lambda *args: PromptPayload("same", batch.hashlib.sha256(b"same").hexdigest(), ())
        with self.assertRaisesRegex(batch.BatchError, "Condition-sensitive"):
            self.prepare()
        self.assertFalse(self.run_dir.exists())

    def test_approval_and_input_drift_prevent_network(self):
        self.prepare()
        with self.assertRaisesRegex(batch.BatchError, "approval hash"):
            batch.submit(self.run_dir, "0" * 64)
        (self.run_dir / "inputs/grading-key.md").write_text("changed")
        with self.assertRaisesRegex(batch.BatchError, "Frozen input"):
            self.submit()
        self.assertEqual(self.calls("ssh"), [])

    def test_complete_transport_import_and_export_with_wrong_decisions(self):
        self.prepare()
        self.submit()
        remote = self.remote_results(failures=10)
        before = {p.name: p.read_bytes() for p in remote.iterdir() if p.is_file()}
        summary = batch.resume(self.run_dir)
        self.assertEqual((summary["attempted"], summary["decisions"]), (20, 10))
        self.assertTrue(summary["gate_passed"])
        rows = list(read_attempts(self.run_dir / "dataset/attempts.jsonl"))
        self.assertTrue(all(row["synthetic"] for row in rows))
        self.assertEqual(rows[-1]["correctness"], "incorrect")
        self.assertTrue((self.run_dir / "dataset/export.js").exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in remote.iterdir() if p.is_file()})
        with self.assertRaisesRegex(batch.BatchError, "already attempted"):
            self.submit()
        batch.resume(self.run_dir)
        report = batch.read_json(self.run_dir / "dataset/import-report.json")
        self.assertEqual((report["appended"], report["skipped"]), (0, 20))
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_lost_receipt_resumes_without_resubmission(self):
        self.prepare()
        with patch.dict(os.environ, {"DROP_AFTER_SUBMIT": "1"}):
            with self.assertRaises(batch.BatchError):
                self.submit()
        self.assertEqual(batch.load_state(self.run_dir)["phase"], "submission_uncertain")
        self.remote_results()
        self.assertTrue(batch.resume(self.run_dir)["gate_passed"])
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_uncertain_submission_without_receipt_never_submits_again(self):
        self.prepare()
        with patch.dict(os.environ, {"FAIL_SSH_CREATE": "1"}):
            with self.assertRaises(batch.BatchError):
                self.submit()
        with self.assertRaises(batch.BatchError):
            batch.resume(self.run_dir)
        self.assertEqual(self.calls("sbatch"), [])

    def test_missing_or_contradictory_accounting_waits(self):
        self.prepare()
        self.submit()
        for queue, account in (("", ""), ("12345|RUNNING", "12345|COMPLETED|0:0")):
            with patch.dict(os.environ, {"QUEUE": queue, "ACCOUNTING": account}):
                self.assertEqual(batch.resume(self.run_dir)["phase"], "waiting")
        self.assertFalse(any("/." in str(c["args"]) for c in self.calls("scp")))

    def test_failed_fetch_preserved_and_next_resume_uses_new_path(self):
        self.prepare()
        self.submit()
        self.remote_results()
        with patch.dict(os.environ, {"FAIL_SCP": "1"}):
            with self.assertRaises(batch.BatchError):
                batch.resume(self.run_dir)
        partial = next(self.run_dir.glob("fetch-*"))
        (partial / "keep").write_text("preserved")
        batch.resume(self.run_dir)
        self.assertEqual((partial / "keep").read_text(), "preserved")
        self.assertNotEqual(batch.load_state(self.run_dir)["fetched"], partial.name)
        self.assertEqual(len(self.calls("sbatch")), 1)

    def test_not_started_work_does_not_pass_twenty_attempt_gate(self):
        self.prepare()
        self.submit()
        self.remote_results(not_started=1)
        summary = batch.resume(self.run_dir)
        self.assertEqual(summary["attempted"], 19)
        self.assertFalse(summary["gate_passed"])

    def test_inconsistent_timing_refuses_before_dataset_or_export_writes(self):
        self.prepare()
        self.submit()
        remote = self.remote_results()
        metrics = batch.read_json(remote / "execution-summary.json")
        metrics["attempted"] = 19
        batch.atomic_json(remote / "execution-summary.json", metrics)
        before = {str(p.relative_to(remote)): p.read_bytes() for p in remote.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(batch.BatchError, "inconsistent execution timing"):
            batch.resume(self.run_dir)
        self.assertFalse((self.run_dir / "dataset").exists())
        self.assertEqual(batch.load_state(self.run_dir)["phase"], "fetched")
        self.assertEqual(before, {str(p.relative_to(remote)): p.read_bytes() for p in remote.rglob("*") if p.is_file()})

    def test_nonfinite_elapsed_time_refuses_before_dataset_writes(self):
        self.prepare()
        self.submit()
        remote = self.remote_results()
        (remote / "execution-summary.json").write_text('{"elapsed_seconds":1e999,"attempted":20}\n')
        with self.assertRaisesRegex(batch.BatchError, "inconsistent execution timing"):
            batch.resume(self.run_dir)
        self.assertFalse((self.run_dir / "dataset").exists())

    def test_inconsistent_timing_preserves_existing_records_and_export(self):
        self.prepare()
        self.submit()
        remote = self.remote_results()
        dataset = self.run_dir / "dataset"
        real_append = alpha_import.recording.append_many
        def partial(path, rows):
            real_append(path, rows[:3])
            raise OSError("synthetic interrupted append")
        with patch.object(alpha_import.recording, "append_many", side_effect=partial):
            with self.assertRaises(alpha_import.ImportError):
                alpha_import.import_bundle(remote, cases_dir=remote / "cases",
                                          attempts_path=dataset / "attempts.jsonl")
        (dataset / "export.json").write_text("previous export must remain untouched\n")
        before = {p.name: p.read_bytes() for p in dataset.iterdir()}
        metrics = batch.read_json(remote / "execution-summary.json")
        metrics["attempted"] = 19
        batch.atomic_json(remote / "execution-summary.json", metrics)
        with self.assertRaisesRegex(batch.BatchError, "inconsistent execution timing"):
            batch.resume(self.run_dir)
        self.assertEqual(before, {p.name: p.read_bytes() for p in dataset.iterdir()})

    def test_runtime_failures_override_valid_looking_output(self):
        self.prepare()
        self.submit()
        remote = self.remote_results()
        path = remote / "results.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["termination_reason"] = "token_limit"
        rows[1].update(status="timeout", termination_reason="unknown", errors=["synthetic timeout"])
        rows[2].update(status="error", termination_reason="unknown", errors=["synthetic error"])
        rows[3]["termination_reason"] = "unknown"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        batch.resume(self.run_dir)
        records = list(read_attempts(self.run_dir / "dataset/attempts.jsonl"))
        self.assertEqual([r["outcome"] for r in records[:4]], ["truncated", "timeout", "error", "error"])
        self.assertTrue(all(r["raw_output"] == "synthetic readable choice" for r in records[:4]))

    def test_incomplete_bundle_refuses_without_records(self):
        self.prepare()
        self.submit()
        remote = self.remote_results()
        path = remote / "results.jsonl"
        path.write_text("\n".join(path.read_text().splitlines()[:-1]) + "\n")
        with self.assertRaisesRegex(alpha_import.ImportError, "missing terminal"):
            batch.resume(self.run_dir)
        self.assertFalse((self.run_dir / "dataset/attempts.jsonl").exists())

    def test_incompatible_dataset_refuses_without_replacement(self):
        self.prepare()
        self.submit()
        self.remote_results()
        batch.resume(self.run_dir)
        path = self.run_dir / "dataset/attempts.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["provenance"]["model_revision"] = "incompatible"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        before = path.read_bytes()
        with self.assertRaisesRegex(alpha_import.ImportError, "incompatible"):
            batch.resume(self.run_dir)
        self.assertEqual(path.read_bytes(), before)

    def test_interrupted_import_resumes_from_complete_records(self):
        self.prepare()
        self.submit()
        self.remote_results()
        real_append = alpha_import.recording.append_many
        def partial(path, rows):
            real_append(path, rows[:3])
            raise OSError("synthetic disk interruption")
        with patch.object(alpha_import.recording, "append_many", side_effect=partial):
            with self.assertRaisesRegex(alpha_import.ImportError, "disk interruption"):
                batch.resume(self.run_dir)
        self.assertEqual(len(list(read_attempts(self.run_dir / "dataset/attempts.jsonl"))), 3)
        batch.resume(self.run_dir)
        report = batch.read_json(self.run_dir / "dataset/import-report.json")
        self.assertEqual((report["appended"], report["skipped"]), (17, 3))

    def test_changed_retained_evidence_refuses_repeat_import(self):
        self.prepare()
        self.submit()
        self.remote_results()
        batch.resume(self.run_dir)
        state = batch.load_state(self.run_dir)
        (self.run_dir / state["fetched"] / "fake-job.out").write_text("changed")
        with self.assertRaisesRegex(batch.BatchError, "Retained evidence changed"):
            batch.resume(self.run_dir)

    def test_exclusive_run_lock(self):
        self.prepare()
        with batch.locked(self.run_dir):
            with self.assertRaisesRegex(batch.BatchError, "Another coordinator"):
                self.submit()

    def test_unknown_journal_version_refuses(self):
        self.prepare()
        state = batch.load_state(self.run_dir)
        state["version"] = 999
        batch.atomic_json(self.run_dir / "progress.json", state)
        with self.assertRaisesRegex(batch.BatchError, "Unsupported progress"):
            self.submit()

    def test_terminal_accounting_accepts_other_jobs_and_refuses_ambiguity(self):
        self.assertEqual(batch.accounting("QUEUE\n999|RUNNING\nACCOUNTING\n12345|COMPLETED|0:0\n", "12345"),
                         ("COMPLETED", "0:0"))
        self.assertIsNone(batch.accounting("QUEUE\nACCOUNTING\n12345|COMPLETED|0:0\n12345|FAILED|1:0\n", "12345"))
        with self.assertRaisesRegex(batch.BatchError, "nonzero exit"):
            batch.accounting("QUEUE\nACCOUNTING\n12345|COMPLETED|1:0\n", "12345")


class PilotBatchTests(unittest.TestCase):
    """Real fictional case, renderer, parser and importer; fake transport only."""

    def setUp(self):
        transport.AlphaSubmitTests.setUp(self)
        self.run_dir = self.local / "pilot-run"
        self.cases = self.local / "cases"
        self.cases.mkdir()
        shutil.copyfile(ROOT / "fixtures/cases/example-campus-transport.json", self.cases / "case.json")
        self.approval = self.local / "approval.md"
        self.approval.write_text("Offline fixture: approve a fictional ungraded Alpha pilot.\n")
        self.grader = patch.object(batch.parsing, "grade", side_effect=AssertionError("Pilot must not grade"))
        self.grade = self.grader.start()
        self.addCleanup(self.grader.stop)
        patcher = patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        return batch.prepare(cases_dir=self.cases, grading_key=None, approval=self.approval,
                             out=self.run_dir, host="tester@alpha.invalid", pilot=True)

    submit = BatchTests.submit

    def remote_results(self, *, not_started=0):
        state = batch.load_state(self.run_dir)
        remote = self.remote / "lantern/runs" / state["run_id"]
        envelope = batch.read_json(remote / "batch.json")
        choice = json.dumps(dict(option_id="route-west", evidence_ids=["ev-ridership"],
                                 explanation="Offline fixture explanation"))
        plan = [("returned", "eos", choice), ("returned", "eos", "not JSON"),
                ("returned", "token_limit", choice), ("timeout", "unknown", None),
                ("error", "unknown", "partial transport output"),
                ("returned", "unknown", choice)]
        rows = []
        for index, attempt in enumerate(envelope["attempts"]):
            status, termination, raw = plan[index] if index < len(plan) else plan[0]
            if index >= 20 - not_started:
                status, termination, raw = "not_started", "unknown", None
            rows.append(dict(attempt_id=attempt["attempt_id"], prompt_sha256=attempt["prompt_sha256"],
                status=status, termination_reason=termination, raw_output=raw,
                provenance=envelope["identity"], errors=[] if status == "returned" else ["Offline fixture failure"]))
        (remote / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        batch.atomic_json(remote / "execution-summary.json", dict(elapsed_seconds=100.0,
            attempted=20 - not_started, includes_preflight_and_model_loading=True))
        os.environ.update(QUEUE="", ACCOUNTING="12345|COMPLETED|0:0")
        return remote

    def test_real_pilot_freeze_matches_local_prompts_without_grading(self):
        self.prepare()
        envelope = batch.read_json(self.run_dir / "inputs/batch.json")
        self.assertEqual(envelope["purpose"], "pilot")
        self.assertFalse(envelope["synthetic"])
        self.assertFalse((self.run_dir / "inputs/grading-key.md").exists())
        expected = json.loads((ROOT / "evidence/local/pilot-2026-11-08/manifest.json").read_text())
        self.assertEqual([a["prompt_sha256"] for a in envelope["attempts"]],
                         [a["prompt_sha256"] for a in expected["schedule"]])
        self.grade.assert_not_called()

    def test_default_experiment_still_refuses_fictional_case_and_missing_key(self):
        with self.assertRaisesRegex(batch.BatchError, "approved case"):
            batch.prepare(cases_dir=self.cases, grading_key=None, approval=self.approval,
                          out=self.run_dir, host="tester@alpha.invalid")
        self.assertFalse(self.run_dir.exists())
        case_file = self.cases / "case.json"
        case = json.loads(case_file.read_text())
        case["status"] = "APPROVED_TEST_FIXTURE"
        case_file.write_text(json.dumps(case))
        with self.assertRaisesRegex(batch.BatchError, "grading key"):
            batch.prepare(cases_dir=self.cases, grading_key=None, approval=self.approval,
                          out=self.run_dir, host="tester@alpha.invalid")
        self.assertFalse(self.run_dir.exists())

    def test_pilot_requires_approval_and_refuses_key(self):
        self.approval.write_text("")
        with self.assertRaisesRegex(batch.BatchError, "approval"):
            self.prepare()
        self.assertFalse(self.run_dir.exists())
        with self.assertRaisesRegex(batch.BatchError, "does not accept"):
            batch.prepare(cases_dir=self.cases, grading_key=self.approval, approval=self.approval,
                          out=self.run_dir, host="tester@alpha.invalid", pilot=True)

    def test_cli_pilot_prepares_without_a_key(self):
        with redirect_stdout(io.StringIO()):
            status = batch.main(["prepare", "--pilot", "--cases", str(self.cases),
                "--approval", str(self.approval), "--out", str(self.run_dir),
                "--host", "tester@alpha.invalid"])
        self.assertEqual(status, 0)
        self.assertEqual(batch.read_json(self.run_dir / "inputs/batch.json")["purpose"], "pilot")
        self.grade.assert_not_called()

    def test_pilot_still_requires_parser_and_experiment_still_requires_grader(self):
        with patch.object(batch.parsing, "parse", side_effect=NotImplementedError("not ready")):
            with self.assertRaisesRegex(batch.BatchError, "not ready"):
                self.prepare()
        self.assertFalse(self.run_dir.exists())
        case_file = self.cases / "case.json"
        case = json.loads(case_file.read_text())
        case["status"] = "APPROVED_TEST_FIXTURE"
        case_file.write_text(json.dumps(case))
        with patch.object(batch.parsing, "grade", side_effect=NotImplementedError("missing key contract")):
            with self.assertRaisesRegex(batch.BatchError, "not ready"):
                batch.prepare(cases_dir=self.cases, grading_key=self.approval, approval=self.approval,
                              out=self.run_dir, host="tester@alpha.invalid")
        self.assertFalse(self.run_dir.exists())

    def test_changed_pilot_purpose_refuses_before_transport(self):
        self.prepare()
        path = self.run_dir / "inputs/batch.json"
        envelope = batch.read_json(path)
        envelope["purpose"] = "experimental"
        batch.atomic_json(path, envelope)
        with self.assertRaisesRegex(batch.BatchError, "Frozen input changed"):
            self.submit()
        self.assertEqual(batch.load_state(self.run_dir)["operations"], [])

    def test_full_pilot_failures_export_and_repeat_resume(self):
        self.prepare()
        self.submit()
        self.remote_results()
        summary = batch.resume(self.run_dir)
        self.assertEqual(summary["purpose"], "pilot")
        self.assertEqual(summary["attempted"], 20)
        self.assertEqual(summary["decisions"], 15)
        self.assertTrue(summary["gate_passed"])
        destination = self.run_dir / "dataset/attempts.jsonl"
        original = destination.read_bytes()
        records = list(read_attempts(destination))
        self.assertEqual([r["outcome"] for r in records[:6]],
                         ["decision", "malformed", "truncated", "timeout", "error", "error"])
        self.assertTrue(all(r["correctness"] == "unknown" and not r["synthetic"] for r in records))
        self.assertEqual(records[4]["raw_output"], "partial transport output")
        export = batch.read_json(self.run_dir / "dataset/export.json")
        self.assertIn("fictional-case pilot", export["label"])
        self.assertFalse(export["all_records_synthetic"])
        self.assertEqual(export["attempts"], records)
        batch.resume(self.run_dir)
        self.assertEqual(destination.read_bytes(), original)
        self.grade.assert_not_called()

    def test_pilot_unstarted_attempts_do_not_pass_gate(self):
        self.prepare()
        self.submit()
        self.remote_results(not_started=1)
        summary = batch.resume(self.run_dir)
        self.assertEqual(summary["attempted"], 19)
        self.assertEqual(len(summary["not_started"]), 1)
        self.assertFalse(summary["gate_passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
