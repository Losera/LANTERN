#!/usr/bin/env python3
"""Real response parsing and Alpha import; grading alone is a test double.

All inputs are synthetic. This suite executes no model, transport or GPU work.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runner import alpha_import, parsing
from runner.cases import Case, EvidenceItem, Option, Rubric
from runner.outcomes import Correctness, Outcome, classify
from runner.recording import read_attempts
import test_alpha_import as fixtures


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.case = Case(
            id="synthetic", question="Synthetic question",
            options=(Option("north", "North"), Option("insufficient", "Insufficient")),
            evidence=(EvidenceItem("ev-known", "Synthetic fact", "Synthetic source", "Synthetic authority", True),),
            cues=(), rubric=Rubric("synthetic", ("Synthetic requirement",)),
            status="SYNTHETIC_TEST_ONLY",
        )

    def response(self, option="north", evidence=None, explanation=""):
        return json.dumps(dict(option_id=option, evidence_ids=evidence or [], explanation=explanation))

    def test_valid_response_needs_no_files(self):
        with patch("builtins.open", side_effect=AssertionError("parser must not open files")):
            result = parsing.parse(" \n" + self.response() + "\n", self.case)
        self.assertIsInstance(result, parsing.Decision)
        self.assertIsInstance(result.signal, parsing.ParseSignal)
        self.assertEqual(classify(result.signal), Outcome.DECISION)
        self.assertEqual(result.received_explanation, "")
        self.assertEqual(result.correctness, Correctness.UNKNOWN)

    def test_strict_shape_and_types(self):
        valid = json.loads(self.response())
        invalid = [None, "", "[]", "null", "true", "1", "{}", "I refuse to answer",
                   "```json\n" + self.response() + "\n```", "Answer: " + self.response(),
                   self.response() + self.response(), self.response()[:-1]]
        invalid += [json.dumps({k: v for k, v in valid.items() if k != missing}) for missing in valid]
        invalid += [json.dumps({**valid, "case_id": self.case.id})]
        for key, values in {
            "option_id": [None, True, 1, [], ""],
            "evidence_ids": [None, "ev-known", {}, [None], [1], [""]],
            "explanation": [None, True, 1, []],
        }.items():
            invalid += [json.dumps({**valid, key: value}) for value in values]
        for raw in invalid:
            with self.subTest(raw=raw):
                result = parsing.parse(raw, self.case)
                self.assertIsInstance(result, parsing.Decision)
                self.assertEqual(classify(result.signal), Outcome.MALFORMED)
                self.assertFalse(result.signal.refused)

    def test_duplicate_keys_and_nonfinite_numbers(self):
        raw = self.response()
        invalid = [raw.replace('"north"', '"north", "option_id": "insufficient"', 1)]
        invalid += [raw.replace('"explanation": ""', '"explanation": ' + number)
                    for number in ["NaN", "Infinity", "-Infinity", "1e999"]]
        for text in invalid:
            with self.subTest(raw=text):
                self.assertEqual(classify(parsing.parse(text, self.case).signal), Outcome.MALFORMED)

    def test_option_matching_is_exact(self):
        for option in ["North", " north", "north ", "unknown", "refuse"]:
            with self.subTest(option=option):
                result = parsing.parse(self.response(option), self.case)
                self.assertEqual(classify(result.signal), Outcome.INVALID_CHOICE)
                self.assertEqual(result.option_id, option)
                self.assertFalse(result.signal.refused)

    def test_insufficient_and_refusal_language_remain_decisions(self):
        for option in ["north", "insufficient"]:
            with self.subTest(option=option):
                text = "I refuse to answer."
                result = parsing.parse(self.response(option, explanation=text), self.case)
                self.assertEqual(classify(result.signal), Outcome.DECISION)
                self.assertFalse(result.signal.refused)
                self.assertEqual(result.received_explanation, text)

    def test_evidence_order_duplicates_and_unknowns_are_preserved(self):
        result = parsing.parse(self.response(evidence=["ev-known", "ev-unknown", "ev-known"]), self.case)
        self.assertEqual([m.evidence_id for m in result.mentions], ["ev-known", None, "ev-known"])
        self.assertEqual(result.mentions[1].source, "ev-unknown")
        self.assertTrue(all(isinstance(m, parsing.Mention) and not m.supported for m in result.mentions))

    def test_invalid_choice_still_resolves_known_evidence(self):
        result = parsing.parse(self.response("unknown", ["ev-known", "ev-unknown"]), self.case)
        self.assertEqual(classify(result.signal), Outcome.INVALID_CHOICE)
        self.assertEqual([m.evidence_id for m in result.mentions], ["ev-known", None])


class RealParserImportTests(unittest.TestCase):
    def setUp(self):
        # Reuse the retained bundle fixture, not its mocked parser expectations.
        self.fixture = fixtures.ImportTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.fixture.parse_patch.stop()

    def rows(self):
        return list(read_attempts(self.fixture.destination))

    def test_import_preserves_raw_output_identities_and_failures(self):
        f = self.fixture
        before = f.snapshot()
        f.run_import()
        rows = self.rows()
        self.assertEqual([r["outcome"] for r in rows], [
            "decision", "malformed", "malformed", "invalid_choice", "truncated", "timeout", "error", "error",
        ])
        self.assertEqual([r["raw_output"] for r in rows], [r["raw_output"] for r in f.results[:-1]])
        self.assertEqual([r["attempt_id"] for r in rows], [r["attempt_id"] for r in f.results[:-1]])
        self.assertEqual([r["operation_id"] for r in rows], [a["operation_id"] for a in f.batch["attempts"][:-1]])
        self.assertEqual(rows[0]["option_id"], "route-north")
        self.assertEqual(rows[0]["correctness"], "correct")
        self.assertEqual(rows[0]["received_explanation"], "Synthetic received explanation")
        self.assertEqual(rows[0]["mentions"][0]["evidence_id"], "ev-ridership")
        self.assertFalse(rows[0]["mentions"][0]["supported"])
        self.assertTrue(all(r["correctness"] == "unknown" for r in rows[1:]))
        f.grader.assert_called_once()
        self.assertEqual(before, f.snapshot())

    def test_only_eos_reaches_real_parser(self):
        f = self.fixture
        real_parse = parsing.parse
        with patch.object(parsing, "parse", wraps=real_parse) as spy:
            f.run_import()
        self.assertEqual([c.args[0] for c in spy.call_args_list], [r["raw_output"] for r in f.results[:4]])

    def test_token_limit_wins_even_for_valid_json(self):
        f = self.fixture
        f.results[0]["termination_reason"] = "token_limit"
        f.write()
        f.run_import()
        self.assertEqual(self.rows()[0]["outcome"], "truncated")
        f.grader.assert_not_called()

    def test_invalid_choice_does_not_drop_known_evidence(self):
        f = self.fixture
        f.results[3]["raw_output"] = json.dumps(dict(
            option_id="unknown", evidence_ids=["ev-ridership"], explanation=""))
        f.write()
        f.run_import()
        row = self.rows()[3]
        self.assertEqual(row["outcome"], "invalid_choice")
        self.assertEqual(row["mentions"][0]["evidence_id"], "ev-ridership")

    def test_unavailable_grader_refuses_before_writes(self):
        f = self.fixture
        f.grade_patch.stop()
        f.refuse("parser/grader unavailable")
        self.assertFalse(f.destination.exists())

    def test_real_parser_reimport_is_idempotent_and_conflicts_refuse(self):
        f = self.fixture
        f.run_import()
        before = f.destination.read_bytes()
        report = f.run_import()
        self.assertEqual((report.appended, report.skipped), (0, 8))
        self.assertEqual(before, f.destination.read_bytes())
        f.results[0]["raw_output"] = f.results[0]["raw_output"] + " "
        f.write()
        f.refuse("conflicting existing attempt")

    def test_missing_and_duplicate_terminal_results_refuse_before_writes(self):
        f = self.fixture
        original = f.results.copy()
        for results, message in [(original[:-1], "missing terminal results"),
                                 (original + original[:1], "duplicate result")]:
            with self.subTest(message=message):
                f.results = results
                f.write()
                f.refuse(message)
                self.assertFalse(f.destination.exists())

    def test_real_parser_decisions_reach_analysis_and_export(self):
        f = self.fixture
        f.run_import()
        rows = self.rows()
        cases = fixtures.load_cases(f.cases)
        analysis = fixtures.summarize(rows)
        document = fixtures.build_export(cases=cases, conditions=fixtures.expand(cases[0].id),
                                        records=rows, analysis=analysis,
                                        label="SYNTHETIC PARSER INTEGRATION TEST")
        self.assertEqual(document["attempts"], rows)
        self.assertTrue(document["all_records_synthetic"])
        self.assertEqual(document["oracle_conformance"], "NOT_RUN")
        export, wrapper = fixtures.write_export(f.root / "real-parser-export.json", document)
        self.assertEqual(json.loads(export.read_text()), document)
        self.assertTrue(wrapper.is_file())

    @unittest.skipUnless((ROOT / "runner/alpha_batch.py").is_file(), "requires PR #44 in combined checkout")
    def test_batch_interpretation_probe_uses_real_parser(self):
        from runner import alpha_batch

        case = fixtures.load_cases(self.fixture.cases)[0]
        alpha_batch.interpretation_ready(case)
        self.fixture.grader.assert_called_once()

    @unittest.skipUnless((ROOT / "runner/alpha_batch.py").is_file(), "requires PR #44 in combined checkout")
    def test_real_grader_blocks_batch_preparation_before_directory_creation(self):
        from runner import alpha_batch

        f = self.fixture
        f.grade_patch.stop()
        case_path = f.cases / "case.json"
        document = json.loads(case_path.read_text())
        document["status"] = "SYNTHETIC_TEST_ONLY"
        case_path.write_text(json.dumps(document))
        out = f.root / "unprepared-run"
        with self.assertRaisesRegex(alpha_batch.BatchError, "parser/grader is not ready"):
            alpha_batch.prepare(cases_dir=f.cases, grading_key=f.root / "key.md",
                                approval=f.root / "approval.md", out=out, host="synthetic@example")
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
