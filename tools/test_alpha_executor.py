#!/usr/bin/env python3
"""Offline supervisor tests: no CUDA, model libraries, SSH, or Slurm execution."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import alpha_batch

spec = importlib.util.spec_from_file_location("executor", ROOT / "examples/alpha-batch-executor.py")
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)


def batch_fixture():
    attempts = []
    for index, arm in enumerate(("baseline", "unchanged_rerun", "neutral_edit", "framing", "correction")):
        for repetition in range(4):
            condition = f"case:{arm}:{repetition}"
            prompt = "Synthetic fixture prompt"
            attempts.append(dict(attempt_id=f"attempt-{len(attempts):02d}", case_id="case",
                condition_id=condition, operation_id=condition, arm=arm, prompt=prompt,
                prompt_sha256=executor.hashlib.sha256(prompt.encode()).hexdigest()))
    return dict(format="lantern.alpha.batch", schema_version=0, purpose="experimental",
                synthetic=False, run_id="offline-fixture", identity=alpha_batch.IDENTITY.copy(),
                attempts=attempts, evidence=[])


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = batch_fixture()
        executor.write(self.root / "batch.json", self.batch)
        executor.write(self.root / "policy.json", executor.POLICY)

    def results(self):
        return [json.loads(line) for line in (self.root / "results.jsonl").read_text().splitlines()]

    def complete_worker(self, command, stdout, stderr, timeout):
        index = int(command[-1])
        executor.write(self.root / f"worker-{index:02d}.json", dict(stage="complete",
            raw_output="synthetic raw output", termination_reason="eos", completion_tokens=1,
            prompt_tokens=10, load_seconds=0.1, generation_seconds=0.2,
            effective_generation_config=dict(temperature=1.0, top_p=1.0)))
        return 0

    def supervise(self, action=None):
        with patch.object(executor, "preflight"), patch.object(executor, "bounded_process",
                side_effect=action or self.complete_worker):
            return executor.supervise(self.root, self.root / "unused-model")

    def test_both_eos_and_eos_at_cap(self):
        for token in (151643, 151645):
            self.assertEqual(executor.termination([42] * 127 + [token]), "eos")
        self.assertEqual(executor.termination([42] * 128), "token_limit")
        self.assertEqual(executor.termination([42]), "unknown")

    def test_oversized_prompt_refuses_without_slicing(self):
        class Tokenizer:
            def apply_chat_template(self, *args, **kwargs):
                return [1] * 1025
        with self.assertRaisesRegex(ValueError, "no truncation"):
            executor.tokenize_batch(Tokenizer(), self.batch["attempts"])

    def test_exact_input_limit_preserves_template_and_ids(self):
        class Tokenizer:
            def apply_chat_template(self, *args, **kwargs):
                return [1] * 1024
            def decode(self, *args, **kwargs):
                return "synthetic rendered input"
        rows = executor.tokenize_batch(Tokenizer(), self.batch["attempts"])
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["prompt_tokens"], 1024)
        self.assertEqual(rows[0]["rendered_prompt"], "synthetic rendered input")

    def test_policy_schedule_and_hash_drift_refused(self):
        executor.validate_batch(self.root, self.batch)
        for change in (lambda b: b["attempts"].pop(),
                       lambda b: b["identity"].update(model_revision="other"),
                       lambda b: b["attempts"][0].update(prompt="changed")):
            altered = copy.deepcopy(self.batch)
            change(altered)
            with self.assertRaises(ValueError):
                executor.validate_batch(self.root, altered)
        executor.write(self.root / "policy.json", {})
        with self.assertRaisesRegex(ValueError, "Policy"):
            executor.validate_batch(self.root, self.batch)

    def test_success_preserves_raw_output_and_scheduled_count(self):
        self.assertEqual(self.supervise(), 0)
        rows = self.results()
        self.assertEqual(len(rows), 20)
        self.assertTrue(all(r["status"] == "returned" for r in rows))
        self.assertEqual(rows[0]["raw_output"], "synthetic raw output")
        self.assertTrue(executor.read(self.root / "execution-summary.json")["includes_preflight_and_model_loading"])
        with self.assertRaises(FileExistsError):
            self.supervise()

    def test_timeout_keeps_attempt_then_continues_without_replacement(self):
        def action(command, *args):
            if command[-1] == "0":
                raise subprocess.TimeoutExpired(command, 60)
            return self.complete_worker(command, *args)
        self.supervise(action)
        rows = self.results()
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["status"], "timeout")
        self.assertEqual(rows[1]["attempt_id"], "attempt-01")
        self.assertEqual(rows[1]["status"], "returned")

    def test_preflight_failure_accounts_for_every_unstarted_attempt(self):
        with patch.object(executor, "preflight", side_effect=ValueError("oversized")), \
             patch.object(executor, "bounded_process") as process:
            self.assertEqual(executor.supervise(self.root, self.root), 1)
        process.assert_not_called()
        self.assertTrue(all(r["status"] == "not_started" for r in self.results()))

    def test_signal_stops_current_attempt_and_accounts_for_remaining(self):
        self.supervise(lambda *args: (_ for _ in ()).throw(executor.ExecutionStopped("TERM")))
        rows = self.results()
        self.assertEqual(rows[0]["status"], "error")
        self.assertTrue(all(r["status"] == "not_started" for r in rows[1:]))

    def test_signal_preserves_completed_worker_receipt(self):
        def interrupted(command, *args):
            self.complete_worker(command, *args)
            raise executor.ExecutionStopped("TERM after receipt was saved")
        self.assertEqual(self.supervise(interrupted), 1)
        rows = self.results()
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(rows[0]["termination_reason"], "unknown")
        self.assertEqual(rows[0]["raw_output"], "synthetic raw output")
        self.assertEqual(rows[0]["provenance"]["prompt_tokens"], 10)
        self.assertEqual(rows[0]["provenance"]["completion_tokens"], 1)
        self.assertTrue(all(r["status"] == "not_started" for r in rows[1:]))

    def test_signal_with_malformed_receipt_still_accounts_for_work(self):
        def interrupted(*args):
            (self.root / "worker-00.json").write_text("{")
            raise executor.ExecutionStopped("TERM with unreadable receipt")
        self.assertEqual(self.supervise(interrupted), 1)
        rows = self.results()
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["status"], "error")
        self.assertIsNone(rows[0]["raw_output"])
        self.assertIn("TERM", rows[0]["errors"][0])
        self.assertTrue(all(r["status"] == "not_started" for r in rows[1:]))

    def test_malformed_worker_receipt_is_attempted_error(self):
        def broken(*args):
            (self.root / "worker-00.json").write_text("{")
            return 0
        self.supervise(broken)
        rows = self.results()
        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(rows[1]["status"], "not_started")

    def test_missing_worker_receipt_is_attempted_error(self):
        self.supervise(lambda *args: 0)
        self.assertTrue(all(row["status"] == "error" for row in self.results()))

    def test_truncation_and_unknown_termination_preserved_for_importer(self):
        def action(command, *args):
            self.complete_worker(command, *args)
            index = int(command[-1])
            path = self.root / f"worker-{index:02d}.json"
            receipt = executor.read(path)
            receipt["termination_reason"] = "token_limit" if index == 0 else "unknown"
            executor.write(path, receipt)
            return 0
        self.supervise(action)
        rows = self.results()
        self.assertEqual(rows[0]["termination_reason"], "token_limit")
        self.assertEqual(rows[1]["termination_reason"], "unknown")
        self.assertTrue(all(row["status"] == "returned" for row in rows))

    def test_real_timeout_kills_and_reaps_child(self):
        pidfile = self.root / "pid"
        command = [sys.executable, "-c",
                   "import os,time,pathlib; pathlib.Path(" + repr(str(pidfile)) +
                   ").write_text(str(os.getpid())); time.sleep(30)"]
        with (self.root / "out").open("w") as stream:
            with self.assertRaises(subprocess.TimeoutExpired):
                executor.bounded_process(command, stream, stream, 0.3)
        pid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_signal_during_spawn_kills_and_reaps_child(self):
        original_popen = executor.subprocess.Popen
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signum):
                children = []
                previous_handler = signal.signal(signum, executor.stop)
                def interrupted_spawn(*args, **kwargs):
                    process = original_popen(*args, **kwargs)
                    children.append(process)
                    # Real signal after fork/exec, before Popen returns its
                    # handle to bounded_process. The child is not signaled.
                    os.kill(os.getpid(), signum)
                    return process
                try:
                    with (self.root / f"spawn-{signum}.out").open("w") as stream, \
                         patch.object(executor.subprocess, "Popen", side_effect=interrupted_spawn):
                        with self.assertRaises(executor.ExecutionStopped):
                            executor.bounded_process([sys.executable, "-c", "import time; time.sleep(30)"],
                                                     stream, stream, 60)
                    self.assertEqual(len(children), 1)
                    self.assertIsNotNone(children[0].poll(), "Shutdown stranded a live worker")
                    self.assertEqual(children[0].returncode, -signal.SIGKILL)
                    self.assertIs(signal.getsignal(signum), executor.stop)
                finally:
                    signal.signal(signum, previous_handler)
                    for process in children:
                        if process.poll() is None:
                            process.kill()
                        process.wait()

    def test_failed_spawn_restores_signal_handlers(self):
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        with patch.object(executor.subprocess, "Popen", side_effect=OSError("spawn failed")), \
             patch.object(executor.os, "killpg") as kill:
            with self.assertRaisesRegex(OSError, "spawn failed"):
                executor.bounded_process([], None, None, 60)
        kill.assert_not_called()
        for sig, handler in handlers.items():
            self.assertEqual(signal.getsignal(sig), handler)

    def test_spawn_deferral_does_not_block_worker_signals(self):
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        with (self.root / "worker-signal.out").open("w") as stream:
            code = executor.bounded_process([sys.executable, "-c",
                "import os,signal; os.kill(os.getpid(), signal.SIGTERM)"], stream, stream, 5)
        self.assertEqual(code, -signal.SIGTERM)
        for sig, handler in handlers.items():
            self.assertEqual(signal.getsignal(sig), handler)


if __name__ == "__main__":
    unittest.main(verbosity=2)
