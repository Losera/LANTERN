#!/usr/bin/env python3
"""Offline demo workflow checks: real CLI/renderer/parser, no model or socket."""

import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import local_demo as demo
from runner.models import AdapterExecutionError, ExecutionSite, Provenance, RawOutput


class DemoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ("frontend/index.html", "frontend/app.js", "frontend/styles.css",
                     "fixtures/cases/example-campus-transport.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        patcher = patch.object(demo, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_two_runs_are_isolated_and_failures_remain_recorded(self):
        provenance = Provenance(execution_site=ExecutionSite.LOCAL,
            model_id=demo.UnapprovedAdapter.MODEL_ID, model_revision=demo.UnapprovedAdapter.MODEL_REVISION,
            harness="ollama", harness_version="0.40.7")
        response = RawOutput(json.dumps(dict(option_id="route-west", evidence_ids=[], explanation="")), provenance)
        failure = AdapterExecutionError("offline fixture timeout", provenance=provenance, timed_out=True)
        with patch.object(demo, "preflight", return_value={"offline_fixture": True}), \
             patch.object(demo.subprocess, "check_output", return_value="fixture-revision\n"), \
             patch.object(demo.cli.UnapprovedAdapter, "generate", side_effect=[failure] + [response] * 39), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            first = demo.fresh_run()
            before = (first / "attempts.jsonl").read_bytes()
            second = demo.fresh_run()
            site = demo.preview(second)
        self.assertNotEqual(first, second)
        self.assertEqual((first / "attempts.jsonl").read_bytes(), before)
        rows = [json.loads(line) for line in before.splitlines()]
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["outcome"], "timeout")
        self.assertTrue(all(r["synthetic"] is False for r in rows))
        self.assertEqual((site / "data/export.json").read_bytes(), (second / "export.json").read_bytes())
        self.assertEqual((self.root / "frontend/app.js").read_bytes(), (ROOT / "frontend/app.js").read_bytes())

    def test_replay_never_calls_ollama(self):
        original = (demo.RETAINED / "export.json").read_bytes()
        with patch.object(demo, "preflight", side_effect=AssertionError("No model access")), \
             patch.object(demo, "serve") as server, redirect_stdout(io.StringIO()):
            self.assertEqual(demo.main(["replay", "--port", "8001"]), 0)
        server.assert_called_once()
        self.assertEqual(server.call_args.args[1], 8001)
        self.assertEqual((server.call_args.args[0] / "data/export.json").read_bytes(), original)
        self.assertEqual((demo.RETAINED / "export.json").read_bytes(), original)

    def test_preflight_failure_creates_no_run(self):
        with patch.object(demo, "preflight", side_effect=ValueError("wrong revision")), \
             redirect_stderr(io.StringIO()):
            self.assertEqual(demo.main(["run"]), 1)
        self.assertFalse((self.root / ".demo").exists())

    def test_wrong_runtime_and_model_are_refused(self):
        for documents in ([{"version": "other"}],
                          [{"version": "0.40.7"}, {"models": []}],
                          [{"version": "0.40.7"}, {"models": [
                              {"name": demo.UnapprovedAdapter.MODEL_ID, "digest": "other"}]}]):
            with self.subTest(documents=documents), patch.object(demo, "urlopen",
                    side_effect=[io.StringIO(json.dumps(d)) for d in documents]):
                with self.assertRaises(ValueError):
                    demo.preflight()

    def test_guided_demo_pauses_and_shows_real_inputs_responses_and_analysis(self):
        provenance = Provenance(execution_site=ExecutionSite.LOCAL,
            model_id=demo.UnapprovedAdapter.MODEL_ID, model_revision=demo.UnapprovedAdapter.MODEL_REVISION,
            harness="ollama", harness_version="0.40.7")
        raw = json.dumps(dict(option_id="route-west", evidence_ids=["ev-ridership"],
                              explanation="Offline walkthrough response"))
        observed = {"daemon": {"version": "0.40.7"},
                    "model": {"name": demo.UnapprovedAdapter.MODEL_ID}}
        with patch.object(demo, "preflight", return_value=observed), \
             patch.object(demo.subprocess, "check_output", return_value="fixture-revision\n"), \
             patch.object(demo.cli.UnapprovedAdapter, "generate", return_value=RawOutput(raw, provenance)) as generate, \
             patch.object(demo, "serve") as server, patch.object(demo.sys.stdin, "isatty", return_value=True), \
             patch("builtins.input", return_value="") as advance, \
             redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            self.assertEqual(demo.main(["demo"]), 0)
        self.assertEqual(generate.call_count, 20)
        self.assertEqual(advance.call_count, 8)
        text = out.getvalue()
        positions = [text.index(f"[{i}/8]") for i in range(1, 9)]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("1,840", text)
        self.assertIn("FRAMING CHANGES", text)
        self.assertIn(raw, text)
        self.assertIn("Framing effect: none_measured", text)
        self.assertIn("do not automatically gate", text)
        run = next((self.root / ".demo/runs").iterdir())
        conditions = json.loads((run / "conditions.json").read_text())
        rows = [json.loads(line) for line in (run / "attempts.jsonl").read_text().splitlines()]
        self.assertEqual([c["prompt_sha256"] for c in conditions], [r["prompt_sha256"] for r in rows])
        for condition in conditions:
            self.assertEqual(demo.hashlib.sha256((run / condition["prompt_file"]).read_bytes()).hexdigest(),
                             condition["prompt_sha256"])
        self.assertEqual(json.loads((run / "summary.json").read_text()),
                         json.loads((run / "export.json").read_text())["analysis"])
        server.assert_called_once()

    def test_yes_skips_pauses_and_ctrl_c_before_generation_makes_no_calls(self):
        with patch.object(demo, "fresh_run", return_value=demo.RETAINED) as run, \
             patch.object(demo, "serve"), patch.object(demo.sys.stdin, "isatty", return_value=True), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(demo.main(["demo", "--yes"]), 0)
            run.assert_called_once_with(walkthrough=True, pause=False)
        with patch("builtins.input", side_effect=KeyboardInterrupt), \
             patch.object(demo.sys.stdin, "isatty", return_value=True), \
             patch.object(demo, "preflight") as runtime, \
             patch.object(demo.cli.UnapprovedAdapter, "generate") as generate, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(demo.main(["demo"]), 0)
        runtime.assert_not_called()
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
