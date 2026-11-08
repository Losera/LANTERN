#!/usr/bin/env python3
"""Offline importer fixtures. Interpretation is mocked, never inferred here."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runner import alpha_import as importer
from runner.analysis import summarize
from runner.cases import load_cases
from runner.conditions import expand
from runner.export import build_export, write_export
from runner.models import ExecutionSite, Provenance
from runner.outcomes import Correctness, Outcome
from runner.parsing import Decision, Mention, ParseSignal
from runner.recording import AttemptRecord, append_many, read_attempts
from runner.conditions import Arm


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


STRUCTURED_CHOICE = (
    ' \n{"option_id": "route-north", "evidence_ids": ["ev-ridership"], '
    '"explanation": "Synthetic received explanation"}\n'
)
UNKNOWN_EVIDENCE_CHOICE = (
    '{"option_id":"route-north","evidence_ids":["ev-ridership","ev-unknown"],'
    '"explanation":"Synthetic explanation with an unknown reference"}'
)
INVALID_CHOICE = '{"option_id":"not-an-option","evidence_ids":[],"explanation":""}'
MALFORMED_RESPONSE = '{"option_id":'


def mock_parse(raw, case):
    # Exact fixture-to-result mapping, not a JSON parser or matching algorithm.
    # These are assumed outputs of the separately owned parser under #9.
    structured = {
        STRUCTURED_CHOICE: Decision(
            "route-north", ParseSignal(decodable=True, choice_in_rubric=True),
            mentions=(Mention(case.evidence[0].source, False, "ev-ridership"),),
            received_explanation="Synthetic received explanation",
        ),
        UNKNOWN_EVIDENCE_CHOICE: Decision(
            "route-north", ParseSignal(decodable=True, choice_in_rubric=True),
            mentions=(Mention(case.evidence[0].source, False, "ev-ridership"),
                      Mention("ev-unknown", False, None)),
            received_explanation="Synthetic explanation with an unknown reference",
        ),
        INVALID_CHOICE: Decision("not-an-option", ParseSignal(decodable=True)),
        MALFORMED_RESPONSE: Decision("", ParseSignal()),
    }
    if raw in structured:
        return structured[raw]
    signals = {
        "choice": ParseSignal(decodable=True, choice_in_rubric=True),
        "malformed": ParseSignal(),
        "refusal": ParseSignal(refused=True),
        "invalid": ParseSignal(decodable=True),
    }
    return Decision(
        option_id=case.options[0].id, signal=signals[raw],
        mentions=(Mention("fixture source", False),),
        received_explanation="Synthetic received explanation",
    )


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "fetched"
        self.bundle.mkdir()
        self.cases = self.root / "cases"
        self.cases.mkdir()
        shutil.copyfile(ROOT / "fixtures/cases/example-campus-transport.json", self.cases / "case.json")
        self.destination = self.root / "dataset" / "attempts.jsonl"
        self.identity = dict(execution_site="alpha_batch", model_id="synthetic-model",
                             model_revision="synthetic-revision", harness="synthetic-runtime",
                             harness_version="fixture-0")
        self.batch = dict(format="lantern.alpha.batch", schema_version=0,
                          purpose="experimental", synthetic=True, run_id="synthetic-alpha-001",
                          identity=self.identity.copy(), attempts=[], evidence=[])
        self.results = []
        for index, (status, termination, output) in enumerate([
            ("returned", "eos", STRUCTURED_CHOICE),
            ("returned", "eos", MALFORMED_RESPONSE),
            ("returned", "eos", "refusal"),
            ("returned", "eos", INVALID_CHOICE),
            ("returned", "token_limit", "partial choice"),
            ("timeout", "unknown", None),
            ("error", "unknown", "partial output before crash"),
            ("returned", "unknown", "choice"),
            ("not_started", "unknown", None),
        ]):
            aid = f"synthetic-attempt-{index}"
            condition = f"campus-transport:baseline:{index}"
            prompt = f"Synthetic prompt {index}\nExact bytes matter."
            sha = digest(prompt.encode())
            self.batch["attempts"].append(dict(attempt_id=aid, case_id="campus-transport",
                condition_id=condition, arm="baseline", operation_id=condition,
                prompt=prompt, prompt_sha256=sha))
            self.results.append(dict(attempt_id=aid, prompt_sha256=sha, status=status,
                termination_reason=termination, raw_output=output,
                provenance={**self.identity, "dtype": "synthetic", "runtime_seconds": None},
                errors=[] if status == "returned" else [f"Synthetic {status} evidence"]))
        for name, raw in {"submission.txt": b"12345\n", "job.sbatch": b"#!/bin/bash\nexit 0\n",
                          "slurm-12345.out": b"Synthetic log: not a model answer.\n",
                          "installed-packages.txt": b"synthetic-runtime==fixture-0\n"}.items():
            (self.bundle / name).write_bytes(raw)
            self.batch["evidence"].append(dict(path=name, purpose="synthetic supporting evidence", sha256=digest(raw)))
        self.write()
        self.parse_patch = patch.object(importer.parsing, "parse", side_effect=mock_parse)
        self.grade_patch = patch.object(importer.parsing, "grade", return_value=Correctness.CORRECT)
        self.parser = self.parse_patch.start()
        self.grader = self.grade_patch.start()
        self.addCleanup(self.parse_patch.stop)
        self.addCleanup(self.grade_patch.stop)

    def write(self):
        (self.bundle / "batch.json").write_text(json.dumps(self.batch) + "\n")
        (self.bundle / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in self.results))

    def snapshot(self):
        return {str(p.relative_to(self.bundle)): p.read_bytes()
                for p in self.bundle.rglob("*") if p.is_file()}

    def run_import(self):
        return importer.import_bundle(self.bundle, cases_dir=self.cases, attempts_path=self.destination)

    def refuse(self, message):
        before = self.snapshot()
        previous = self.destination.read_bytes() if self.destination.exists() else None
        with self.assertRaisesRegex(importer.ImportError, message):
            self.run_import()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(previous, self.destination.read_bytes() if self.destination.exists() else None)

    def test_complete_import_and_export_preserve_every_source_byte(self):
        before = self.snapshot()
        report = self.run_import()
        rows = list(read_attempts(self.destination))
        self.assertEqual((report.appended, report.skipped), (8, 0))
        self.assertEqual(report.not_started, ("synthetic-attempt-8",))
        self.assertEqual([r["outcome"] for r in rows], ["decision", "malformed", "refusal",
            "invalid_choice", "truncated", "timeout", "error", "error"])
        self.assertEqual(rows[6]["raw_output"], "partial output before crash")
        self.assertIn("provenance.runtime_seconds", rows[0]["unknown"])
        self.assertIsNone(rows[0]["provenance"]["runtime_seconds"])
        self.assertEqual(rows[0]["mentions"][0]["supported"], False)
        self.assertEqual(rows[0]["received_explanation"], "Synthetic received explanation")
        self.assertEqual(self.parser.call_count, 4)
        self.grader.assert_called_once()
        self.assertTrue(all(row["synthetic"] for row in rows))
        self.assertEqual(report.evidence_hashes, {name: digest(raw) for name, raw in before.items()})
        cases = load_cases(self.cases)
        conditions = expand(cases[0].id, reruns=9)
        analysis = summarize(rows, conditions)
        self.assertEqual(analysis.attempts, 8)
        export = build_export(cases=cases, conditions=conditions, records=rows,
                              analysis=analysis, label="SYNTHETIC Alpha import fixture")
        path, wrapper = write_export(self.root / "export.json", export)
        self.assertTrue(json.loads(path.read_text())["all_records_synthetic"])
        self.assertTrue(wrapper.is_file())
        self.assertEqual(before, self.snapshot())

    def test_repeat_import_is_a_noop(self):
        self.run_import()
        previous = self.destination.read_bytes()
        report = self.run_import()
        self.assertEqual((report.appended, report.skipped), (0, 8))
        self.assertEqual(previous, self.destination.read_bytes())

    def test_structured_response_preserves_raw_text_and_interpreted_fields(self):
        self.batch["attempts"] = self.batch["attempts"][:1]
        self.results = self.results[:1]
        self.write()
        before = self.snapshot()
        self.run_import()
        self.parser.assert_called_once_with(STRUCTURED_CHOICE, load_cases(self.cases)[0])
        row = next(read_attempts(self.destination))
        self.assertEqual(row["raw_output"], STRUCTURED_CHOICE)
        self.assertEqual(row["outcome"], "decision")
        self.assertEqual(row["option_id"], "route-north")
        self.assertEqual(row["received_explanation"], "Synthetic received explanation")
        self.assertEqual(row["mentions"][0]["evidence_id"], "ev-ridership")
        self.assertFalse(row["mentions"][0]["supported"])
        self.assertEqual(before, self.snapshot())
        previous = self.destination.read_bytes()
        report = self.run_import()
        self.assertEqual((report.appended, report.skipped), (0, 1))
        self.assertEqual(previous, self.destination.read_bytes())

    def test_mocked_unknown_evidence_keeps_choice_and_unsupported_reference(self):
        self.batch["attempts"] = self.batch["attempts"][:1]
        self.results = self.results[:1]
        self.results[0]["raw_output"] = UNKNOWN_EVIDENCE_CHOICE
        self.grader.return_value = Correctness.UNKNOWN
        self.write()
        self.run_import()
        row = next(read_attempts(self.destination))
        self.assertEqual(row["raw_output"], UNKNOWN_EVIDENCE_CHOICE)
        self.assertEqual((row["outcome"], row["option_id"]), ("decision", "route-north"))
        self.assertEqual(row["correctness"], "unknown")
        self.assertEqual(row["mentions"][1],
                         dict(source="ev-unknown", supported=False, evidence_id=None))
        self.grader.assert_called_once()

    def test_mocked_malformed_and_invalid_choices_still_count(self):
        self.batch["attempts"] = [self.batch["attempts"][1], self.batch["attempts"][3]]
        self.results = [self.results[1], self.results[3]]
        self.write()
        report = self.run_import()
        rows = list(read_attempts(self.destination))
        self.assertEqual(report.appended, 2)
        self.assertEqual([row["outcome"] for row in rows], ["malformed", "invalid_choice"])
        self.assertEqual([row["raw_output"] for row in rows], [MALFORMED_RESPONSE, INVALID_CHOICE])
        self.assertEqual(summarize(rows).attempts, 2)
        self.grader.assert_not_called()

    def test_valid_json_at_token_limit_is_truncated_without_parsing(self):
        self.batch["attempts"] = self.batch["attempts"][:1]
        self.results = self.results[:1]
        self.results[0]["termination_reason"] = "token_limit"
        self.write()
        self.run_import()
        row = next(read_attempts(self.destination))
        self.assertEqual(row["outcome"], "truncated")
        self.assertEqual(row["raw_output"], STRUCTURED_CHOICE)
        self.assertIsNone(row["option_id"])
        self.parser.assert_not_called()
        self.grader.assert_not_called()

    def test_parser_truncation_signal_remains_visible(self):
        self.parser.side_effect = None
        self.parser.return_value = Decision("route-north", ParseSignal(truncated=True))
        self.run_import()
        self.assertEqual(next(read_attempts(self.destination))["outcome"], "truncated")
        self.grader.assert_not_called()

    def test_conflicting_identity_refuses_before_any_append(self):
        self.run_import()
        rows = list(read_attempts(self.destination))
        rows[0]["raw_output"] = "changed evidence"
        self.destination.write_text("".join(json.dumps(r) + "\n" for r in rows[:1]))
        self.refuse("conflicting existing attempt")

    def test_missing_results_report_all_missing_ids(self):
        self.results = self.results[:-2]
        self.write()
        self.refuse("missing terminal results.*synthetic-attempt-7, synthetic-attempt-8")
        self.parser.assert_not_called()

    def test_missing_supporting_file(self):
        (self.bundle / "job.sbatch").unlink()
        self.refuse("job.sbatch.*missing")

    def test_prompt_hash_mismatch(self):
        self.batch["attempts"][0]["prompt"] += "changed"
        self.write()
        self.refuse("prompt hash mismatch")

    def test_result_hash_mismatch(self):
        self.results[0]["prompt_sha256"] = "0" * 64
        self.write()
        self.refuse("result prompt hash mismatch")

    def test_supporting_hash_mismatch(self):
        (self.bundle / "submission.txt").write_text("67890\n")
        self.refuse("evidence hash mismatch")

    def test_diagnostic_bundle_refused(self):
        self.batch["purpose"] = "diagnostic"
        self.write()
        self.refuse("only experimental")

    def test_incompatible_existing_datasets(self):
        self.run_import()
        pristine = self.destination.read_text()
        for key, value in [("model_id", "other"), ("model_revision", "other"),
                           ("harness", "other"), ("harness_version", "other"),
                           ("execution_site", "local")]:
            with self.subTest(key=key):
                row = json.loads(pristine.splitlines()[0])
                row["provenance"][key] = value
                self.destination.write_text(json.dumps(row) + "\n")
                self.refuse("incompatible model/runtime")

    def test_synthetic_and_real_records_cannot_mix(self):
        self.run_import()
        row = next(read_attempts(self.destination))
        row["synthetic"] = False
        self.destination.write_text(json.dumps(row) + "\n")
        self.refuse("incompatible synthetic")

    def test_model_runtime_mismatch_within_bundle(self):
        self.results[-1]["provenance"]["harness_version"] = "other"
        self.write()
        self.refuse("model/runtime identity differs")

    def test_malformed_or_truncated_results(self):
        for raw in (b"{bad json}\n", b'{"attempt_id":', b"\n", b"[]\n"):
            with self.subTest(raw=raw):
                (self.bundle / "results.jsonl").write_bytes(raw)
                self.refuse("results.jsonl")

    def test_strict_json_and_version(self):
        path = self.bundle / "batch.json"
        for raw in (b'{"format":1,"format":2}', b'{"version":NaN}'):
            path.write_bytes(raw)
            self.refuse("duplicate JSON key|non-finite")
        self.batch["schema_version"] = True
        self.write()
        self.refuse("unsupported format/schema_version")

    def test_duplicate_or_unexpected_result(self):
        self.results.append(copy.deepcopy(self.results[0]))
        self.write()
        self.refuse("duplicate result")
        self.results[-1]["attempt_id"] = "unplanned"
        self.write()
        self.refuse("unexpected")

    def test_duplicate_schedule_and_condition_mismatch(self):
        self.batch["attempts"].append(copy.deepcopy(self.batch["attempts"][0]))
        self.write()
        self.refuse("duplicate scheduled")
        self.batch["attempts"].pop()
        self.batch["attempts"][0]["arm"] = "framing"
        self.write()
        self.refuse("condition")

    def test_invalid_provenance_and_execution_metadata(self):
        original = copy.deepcopy(self.results)
        changes = [("runtime_seconds", -1), ("prompt_tokens", True), ("top_p", 2), ("dtype", [])]
        for field, value in changes:
            with self.subTest(field=field):
                self.results = copy.deepcopy(original)
                self.results[0]["provenance"][field] = value
                self.write()
                self.refuse(field)
        self.results = copy.deepcopy(original)
        self.results[0]["option_id"] = "route-north"
        self.write()
        self.refuse("unexpected fields")

    def test_unsafe_paths_and_symlinks_refused(self):
        original = copy.deepcopy(self.batch["evidence"])
        for path in ("../outside", "/tmp/outside", "nested/../job.sbatch", "./job.sbatch"):
            with self.subTest(path=path):
                self.batch["evidence"] = [dict(path=path, purpose="fixture", sha256="0" * 64)]
                self.write()
                self.refuse("canonical relative path")
        self.batch["evidence"] = original
        (self.root / "external.log").write_text("external")
        (self.bundle / "link").symlink_to(self.root, target_is_directory=True)
        self.batch["evidence"].append(dict(path="link/external.log", purpose="fixture", sha256="0" * 64))
        self.write()
        self.refuse("symlinks are refused")

    def test_main_files_cannot_be_symlinks(self):
        original = (self.bundle / "batch.json").read_bytes()
        (self.root / "external.json").write_bytes(original)
        (self.bundle / "batch.json").unlink()
        (self.bundle / "batch.json").symlink_to(self.root / "external.json")
        self.refuse("symlinks are refused")

    def test_dataset_inside_bundle_refused(self):
        self.destination = self.bundle / "attempts.jsonl"
        self.refuse("outside the evidence")

    def test_destination_symlink_or_hardlink_refused(self):
        self.destination.parent.mkdir()
        original = self.root / "original.jsonl"
        original.write_text("preserve this file\n")
        self.destination.symlink_to(original)
        self.refuse("symlink")
        self.destination.unlink()
        os.link(original, self.destination)
        self.refuse("single hard link")
        self.assertEqual(original.read_text(), "preserve this file\n")

    def test_all_not_started_reports_without_creating_dataset(self):
        self.batch["attempts"] = self.batch["attempts"][-1:]
        self.results = self.results[-1:]
        self.write()
        report = self.run_import()
        self.assertEqual((report.appended, report.skipped), (0, 0))
        self.assertEqual(report.not_started, ("synthetic-attempt-8",))
        self.assertFalse(self.destination.exists())

    def test_inconsistent_terminal_metadata_refused(self):
        original = copy.deepcopy(self.results)
        for index, changes in [(0, {"raw_output": None}), (5, {"termination_reason": "eos"}),
                               (6, {"errors": []}), (8, {"raw_output": "model answer"})]:
            with self.subTest(index=index):
                self.results = copy.deepcopy(original)
                self.results[index].update(changes)
                self.write()
                self.refuse("raw_output|termination|explanation|not_started")

    def test_existing_record_missing_fields_or_unknown_index_refused(self):
        self.run_import()
        row = next(read_attempts(self.destination))
        bad = copy.deepcopy(row)
        del bad["outcome"]
        self.destination.write_text(json.dumps(bad) + "\n")
        self.refuse("missing fields")
        row["unknown"] = []
        self.destination.write_text(json.dumps(row) + "\n")
        self.refuse("unknown index")

    def test_existing_recorder_defaults_remain_compatible(self):
        identity = {**self.identity, "execution_site": ExecutionSite.ALPHA_BATCH}
        prior = AttemptRecord(run_id="another-synthetic-run", case_id="campus-transport",
            condition_id="campus-transport:baseline:0", arm=Arm.BASELINE,
            attempt_id="prior-attempt", operation_id="campus-transport:baseline:0",
            outcome=Outcome.ERROR, provenance=Provenance(**identity), synthetic=True)
        append_many(self.destination, [prior])
        report = self.run_import()
        self.assertEqual(report.appended, 8)
        self.assertEqual(next(read_attempts(self.destination)), prior.as_dict())

    def test_partial_previous_append_resumes(self):
        self.run_import()
        first = self.destination.read_text().splitlines()[0] + "\n"
        self.destination.write_text(first)
        report = self.run_import()
        self.assertEqual((report.appended, report.skipped), (7, 1))
        self.assertEqual(len(list(read_attempts(self.destination))), 8)

    def test_truncated_or_malformed_destination_refused(self):
        self.destination.parent.mkdir()
        for raw in (b"{", b"{bad}\n", b"[]\n"):
            with self.subTest(raw=raw):
                self.destination.write_bytes(raw)
                self.refuse("unterminated|dataset")

    def test_existing_duplicate_identity_refused(self):
        self.run_import()
        first = self.destination.read_text().splitlines()[0]
        self.destination.write_text(first + "\n" + first + "\n")
        self.refuse("already contains duplicate")

    def test_not_started_cannot_overwrite_attempt_evidence(self):
        self.run_import()
        self.results[0].update(status="not_started", termination_reason="unknown", raw_output=None,
                               errors=["Never started according to conflicting evidence"])
        self.write()
        self.refuse("not_started conflicts")

    def test_actual_parser_seam_and_grader_seam_refuse(self):
        self.parse_patch.stop()
        self.refuse("parser/grader unavailable")
        self.parse_patch.start()
        self.grader.side_effect = NotImplementedError("grading not approved")
        self.refuse("parser/grader unavailable")

    def test_explicit_failures_import_without_parser(self):
        self.batch["attempts"] = self.batch["attempts"][4:]
        self.results = self.results[4:]
        self.write()
        self.parser.side_effect = AssertionError("parser must not receive failed output")
        report = self.run_import()
        self.assertEqual(report.appended, 4)
        self.parser.assert_not_called()

    def test_evidence_change_during_conversion_refuses(self):
        def changing_parser(raw, case):
            (self.bundle / "submission.txt").write_text("changed during import")
            return mock_parse(raw, case)
        self.parser.side_effect = changing_parser
        with self.assertRaisesRegex(importer.ImportError, "evidence changed"):
            self.run_import()
        self.assertFalse(self.destination.exists())

    def test_io_failure_after_one_complete_record_can_resume(self):
        def interrupted_append(path, records):
            append_many(path, records[:1])
            raise OSError("simulated disk interruption")
        with patch.object(importer.recording, "append_many", side_effect=interrupted_append):
            with self.assertRaisesRegex(importer.ImportError, "simulated disk"):
                self.run_import()
        report = self.run_import()
        self.assertEqual((report.appended, report.skipped), (7, 1))

    def test_cli_report_and_refusal(self):
        args = ["--bundle", str(self.bundle), "--cases", str(self.cases),
                "--attempts", str(self.destination)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(importer.main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["appended"], 8)
        self.assertEqual(stderr.getvalue(), "")
        # A separate process uses the real parser and must refuse.
        result = subprocess.run([sys.executable, "-m", "runner.alpha_import", *args],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("parser/grader unavailable", json.loads(result.stderr)["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
