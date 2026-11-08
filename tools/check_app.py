#!/usr/bin/env python3
"""Offline checks for the application skeleton. Runs no model and fetches nothing.

What this lane establishes: the runner's modules import, its deterministic
parts behave as their documentation claims, its seams still refuse to run, the
export matches what the page reads, and the frontend has no external
dependency. That is a coherence check on a skeleton.

What it does not establish, and cannot: Alpha connectivity, model behaviour,
conformance to the Lean design oracle, reduced bias, or any experiment result.
``--oracle`` adds one clearly separate observation -- that the oracle binary
accepts a trace this code emitted -- which is evidence about one trace, not a
conformance lane. See docs/status.md for the evidence lanes.

Two checks are deliberately written against an *independent* copy of a
contract rather than importing the module under test, following the Lean
fixtures' habit of specifying expected verdicts separately:
:data:`EXPECTED_EVENT_FIELDS` and :data:`EXPECTED_ARMS`. A check that imports
its own expectations proves only that the module agrees with itself.
"""

from __future__ import annotations

import argparse
from collections import Counter
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]

# The checker lives in tools/ but imports the package under test from the
# repository root, so the root must be importable however the script is run.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED = (
    "runner/__init__.py", "runner/analysis.py", "runner/cases.py",
    "runner/cli.py", "runner/conditions.py", "runner/export.py",
    "runner/models.py", "runner/outcomes.py", "runner/parsing.py",
    "runner/prompts.py", "runner/recording.py", "runner/tools.py",
    "runner/trace.py", "runner/unknown.py",
    "frontend/index.html", "frontend/styles.css", "frontend/app.js",
    "frontend/data/export.json", "frontend/data/export.js",
    "fixtures/cases/example-campus-transport.json",
    "fixtures/attempts/example.jsonl",
    "docs/contracts.md",
)

#: Independently transcribed from lantern-formal/Lantern/Wire.lean's
#: ``parseEvent`` and the oracle README's field table. Compared against
#: runner.trace.EVENT_FIELDS so a drift in either is caught.
EXPECTED_EVENT_FIELDS = {
    "dispatch": {"run", "operation", "attempt", "payload"},
    "succeed": {"run", "attempt", "artifact"},
    "fail": {"run", "attempt"},
    "timeout": {"run", "attempt"},
    "cite": {"run", "attempt", "artifact"},
    "commit": {"run", "operation", "payload"},
    "finalize": {"run", "complete"},
}

#: Independently transcribed from docs/evaluation.md "Use matched cases".
EXPECTED_ARMS = {
    "baseline", "unchanged_rerun", "neutral_edit", "framing", "correction",
}

#: Independently transcribed from docs/evaluation.md "Retain evidence for
#: every attempt". Every one of these must appear in the attempt record's
#: wire form, so a field cannot be dropped from the record silently.
EXPECTED_RECORD_FIELDS = {
    "run_id", "case_id", "condition_id", "arm", "attempt_id", "operation_id",
    "outcome", "correctness", "option_id", "prompt_sha256", "raw_output",
    "parse_signal", "mentions", "errors", "provenance", "unknown",
    "schema_version", "synthetic", "received_explanation",
}

FIELDS_PATTERN = re.compile(r"const FIELDS\s*=\s*\[(.*?)\]\s*;", re.DOTALL)
STRING_PATTERN = re.compile(r"'([^']+)'|\"([^\"]+)\"")
EXTERNAL_URL = re.compile(r"https?://")
FRONTEND_SOURCES = ("frontend/index.html", "frontend/styles.css", "frontend/app.js")


def declared_fields(text: str) -> list[str]:
    """Extract the FIELDS list the page declares it reads."""
    match = FIELDS_PATTERN.search(text)
    if not match:
        raise ValueError("frontend/app.js declares no `const FIELDS = [...]`")
    return [a or b for a, b in STRING_PATTERN.findall(match.group(1))]


def check_layout(root: Path, errors: list[str], counts: Counter) -> None:
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"{relative}: required file is missing")
        else:
            counts["required files"] += 1


def check_modules(errors: list[str], counts: Counter) -> None:
    """Import every runner module, so a syntax or import error fails here."""
    import importlib

    for name in sorted(
        path.stem for path in (ROOT / "runner").glob("*.py")
    ):
        module = "runner" if name == "__init__" else f"runner.{name}"
        try:
            importlib.import_module(module)
            counts["modules imported"] += 1
        except Exception as exc:  # noqa: BLE001 - any failure is a finding
            errors.append(f"{module}: import failed: {type(exc).__name__}: {exc}")


def check_adapter() -> None:
    """Exercise the real adapter through synthetic HTTP, never a live daemon.

    Fixtures establish local request/result wiring and failure preservation.
    They establish neither real Ollama behavior nor model quality.
    """
    from runner import models
    from runner.unknown import Unknown

    payload = models.PromptPayload("SYNTHETIC offline checker input", "fixture-digest", ())
    for scenario in ("stop", "length", "api_error", "transport_error"):
        calls: list[str] = []

        def respond(request, *, timeout):
            calls.append(request.full_url)
            if timeout <= 0:
                raise ValueError("adapter request must have a positive timeout")
            if scenario == "transport_error":
                raise URLError("synthetic offline transport failure")
            if request.full_url == "http://127.0.0.1:11434/api/version":
                if request.get_method() != "GET":
                    raise ValueError("version request must use GET")
                return io.BytesIO(b'{"version":"0.40.7"}')
            if request.full_url != "http://127.0.0.1:11434/api/generate":
                raise ValueError(f"unexpected adapter URL: {request.full_url}")
            expected = {
                "model": "qwen2.5:1.5b-instruct", "prompt": payload.text, "stream": False,
                "options": {"temperature": 0.0, "top_p": 1.0, "seed": 1,
                            "num_predict": 512, "num_ctx": 4096},
            }
            if request.get_method() != "POST" or json.loads(request.data) != expected:
                raise ValueError("adapter request differs from approved settings/prompt")
            if scenario == "api_error":
                return io.BytesIO(b'{"error":"synthetic generation failure"}')
            return io.BytesIO(json.dumps({
                "response": "SYNTHETIC offline checker output", "done_reason": scenario,
                "prompt_eval_count": 7, "eval_count": 3, "total_duration": 125000000,
            }).encode("utf-8"))

        with patch.object(models, "urlopen", side_effect=respond):
            try:
                result = models.UnapprovedAdapter().generate(payload)
            except models.AdapterExecutionError as exc:
                if scenario == "transport_error":
                    if not isinstance(exc.raw_output, Unknown) or len(calls) != 1:
                        raise ValueError("transport failure lost unknown output or continued generation")
                elif scenario == "api_error":
                    if (exc.raw_output != '{"error":"synthetic generation failure"}'
                            or exc.provenance.execution_site is not models.ExecutionSite.LOCAL
                            or exc.outcome.value != "error" or len(calls) != 2):
                        raise ValueError("API failure lost its body, provenance, or error outcome")
                else:
                    raise
            else:
                if scenario in ("api_error", "transport_error"):
                    raise ValueError("adapter converted an execution failure into a response")
                if (not isinstance(result, models.RawOutput)
                        or result.text != "SYNTHETIC offline checker output"
                        or result.truncated_by_limit is not (scenario == "length")
                        or len(calls) != 2):
                    raise ValueError("adapter lost raw output, truncation, or request ordering")
                provenance = result.provenance
                if (provenance.execution_site is not models.ExecutionSite.LOCAL
                        or provenance.model_id != "qwen2.5:1.5b-instruct"
                        or provenance.model_revision != "65ec06548149"
                        or provenance.harness_version != "0.40.7"
                        or provenance.dtype != "Q4_K_M/GGUF"
                        or provenance.prompt_tokens != 7 or provenance.completion_tokens != 3
                        or provenance.runtime_seconds != 0.125
                        or not isinstance(provenance.peak_memory_bytes, Unknown)):
                    raise ValueError("adapter changed local provenance or invented memory usage")


def check_parser(case) -> None:
    """Exercise the real response reader without grading or runtime metadata."""
    from runner import parsing
    from runner.outcomes import Outcome, classify

    def response(option):
        return json.dumps({"option_id": option, "evidence_ids": [], "explanation": ""})

    unknown = "checker-unknown-option"
    while unknown in {option.id for option in case.options}:
        unknown += "-unknown"
    for raw, expected in (
        (response(case.options[0].id), Outcome.DECISION),
        ("not JSON", Outcome.MALFORMED),
        (response(unknown), Outcome.INVALID_CHOICE),
    ):
        decision = parsing.parse(raw, case)
        if not isinstance(decision, parsing.Decision) or not isinstance(decision.signal, parsing.ParseSignal):
            raise ValueError("parser must return a Decision with a ParseSignal")
        if classify(decision.signal) is not expected or decision.signal.refused:
            raise ValueError(f"parser must classify {raw!r} as {expected.value} without refusal")
        if expected is Outcome.DECISION and (
            decision.option_id != case.options[0].id or decision.received_explanation != ""
        ):
            raise ValueError("parser lost the exact option or empty explanation")


def check_seams(errors: list[str], counts: Counter) -> None:
    """Seams must refuse; implemented code must not raise NotImplementedError.

    A seam that starts returning plausible data is the failure mode this
    guards: a stub's output is indistinguishable from a result downstream.
    """
    from runner import prompts, tools
    from runner.cases import load_case
    from runner.conditions import expand
    from runner.parsing import grade

    case = load_case(ROOT / "fixtures/cases/example-campus-transport.json")
    condition = expand(case.id)[0]

    seams = (
        ("runner.parsing.grade", lambda: grade(None, case)),
        ("runner.tools.ToolRegistry.execute",
         lambda: tools.ToolRegistry().execute(
             tools.record_proposal("example", "{}"))),
    )
    for label, call in seams:
        try:
            call()
        except NotImplementedError:
            counts["seams refusing"] += 1
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(
                f"{label}: a seam must raise NotImplementedError, raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        errors.append(f"{label}: a seam returned a value instead of refusing")

    implemented = (
        ("runner.parsing.parse", lambda: check_parser(case)),
        ("runner.prompts.digest", lambda: prompts.digest("x")),
        ("runner.prompts.render", lambda: prompts.render(case, condition)),
        ("runner.models.UnapprovedAdapter.generate", check_adapter),
        ("runner.tools.record_proposal",
         lambda: tools.record_proposal("example", "{}")),
    )
    for label, call in implemented:
        try:
            call()
            counts["implemented callables"] += 1
        except NotImplementedError:
            errors.append(f"{label}: documented as implemented but refused")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: raised {type(exc).__name__}: {exc}")


def check_conditions(errors: list[str], counts: Counter) -> None:
    """The arms are complete, expansion is deterministic, exclusions explained."""
    from runner.conditions import Arm, expand, framing_only, mark_confounded

    arms = {arm.value for arm in Arm}
    if arms != EXPECTED_ARMS:
        errors.append(
            f"conditions: arms {sorted(arms)} do not match the matched-case set "
            f"{sorted(EXPECTED_ARMS)} required by docs/evaluation.md"
        )
    first = [c.id for c in expand("case", reruns=2)]
    second = [c.id for c in expand("case", reruns=2)]
    if first != second:
        errors.append("conditions: expand is not deterministic")
    if len(first) != len(EXPECTED_ARMS) * 2:
        errors.append(
            f"conditions: expand(reruns=2) produced {len(first)} conditions, "
            f"expected {len(EXPECTED_ARMS) * 2}"
        )
    conditions = expand("case")
    eligible = {c.arm.value for c in framing_only(conditions)}
    if eligible != {"baseline", "framing"}:
        errors.append(
            f"conditions: framing-only comparison reads {sorted(eligible)}; "
            "it must read exactly the baseline and framing arms"
        )
    correction = next(c for c in conditions if c.arm is Arm.CORRECTION)
    if correction.framing_only_eligible or not correction.changes_evidence:
        errors.append(
            "conditions: the correction arm changes decision-relevant evidence "
            "and must be excluded from the framing-only comparison"
        )
    confounded = mark_confounded(
        next(c for c in conditions if c.arm is Arm.NEUTRAL_EDIT),
        "the rewrite changed a stated fact",
    )
    if confounded.framing_only_eligible:
        errors.append("conditions: a confounded edit stayed framing-only eligible")
    try:
        from runner.conditions import Condition
        Condition(case_id="c", arm=Arm.NEUTRAL_EDIT, index=0, confounded=True)
    except ValueError:
        counts["unexplained exclusion refused"] += 1
    else:
        errors.append(
            "conditions: a confounded condition was accepted without a reason; "
            "an unexplained exclusion is indistinguishable from dropped data"
        )
    counts["condition checks"] += 1


def check_recording(errors: list[str], counts: Counter) -> None:
    """Unknowns stay unknown, decisions need a choice, writes only append."""
    from runner.conditions import Arm
    from runner.models import ExecutionSite, Provenance
    from runner.outcomes import Correctness, Outcome
    from runner.recording import (
        UNKNOWN, AttemptRecord, RecordError, append, read_attempts,
    )

    record = AttemptRecord(
        run_id="r", case_id="c", condition_id="c:baseline:0", arm=Arm.BASELINE,
        attempt_id="a", operation_id="o", outcome=Outcome.TIMEOUT,
        provenance=Provenance(execution_site=ExecutionSite.LOCAL),
    )
    wire = record.as_dict()

    missing = EXPECTED_RECORD_FIELDS - set(wire)
    if missing:
        errors.append(
            f"recording: the wire form omits {sorted(missing)}, required by "
            "docs/evaluation.md 'Retain evidence for every attempt'"
        )

    provenance = wire["provenance"]
    for field in ("seed", "prompt_tokens", "runtime_seconds", "model_revision"):
        if provenance[field] is not None:
            errors.append(
                f"recording: unmeasured provenance field {field!r} serialised as "
                f"{provenance[field]!r}; an unknown must be null"
            )
        if f"provenance.{field}" not in wire["unknown"]:
            errors.append(
                f"recording: {field!r} is null but is not named in the "
                "'unknown' list, so a reader cannot tell missing from measured"
            )
    if provenance["execution_site"] != "local":
        errors.append("recording: execution_site was not preserved")
    counts["unknown fields named"] += len(wire["unknown"])

    try:
        AttemptRecord(
            run_id="r", case_id="c", condition_id="x", arm=Arm.BASELINE,
            attempt_id="a", operation_id="o", outcome=Outcome.DECISION,
            provenance=Provenance(execution_site=ExecutionSite.LOCAL),
        )
    except RecordError:
        counts["decision without choice refused"] += 1
    else:
        errors.append(
            "recording: an outcome of 'decision' was accepted with no chosen "
            "option, so an unreadable reply could be counted as a decision"
        )

    try:
        AttemptRecord(
            run_id="r", case_id="c", condition_id="x", arm=Arm.BASELINE,
            attempt_id="a", operation_id="o", outcome=Outcome.TIMEOUT,
            provenance=Provenance(execution_site=ExecutionSite.LOCAL),
            correctness=Correctness.CORRECT,
        )
    except RecordError:
        counts["graded non-decision refused"] += 1
    else:
        errors.append(
            "recording: a timed-out attempt was accepted as 'correct'; "
            "correctness is only meaningful for a readable decision"
        )

    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "nested" / "attempts.jsonl"
        append(path, record)
        append(path, record)
        rows = list(read_attempts(path))
        if len(rows) != 2:
            errors.append(
                f"recording: two appends produced {len(rows)} records; the "
                "writer must append rather than truncate"
            )
        if UNKNOWN is None:
            errors.append("recording: UNKNOWN must not be None")
    counts["recording checks"] += 1


def check_trace(errors: list[str], counts: Counter) -> None:
    """Event fields match the oracle's table; citations need their success."""
    from runner import trace

    actual = {kind: set(fields) for kind, fields in trace.EVENT_FIELDS.items()}
    if actual != EXPECTED_EVENT_FIELDS:
        errors.append(
            "trace: EVENT_FIELDS does not match the independently transcribed "
            f"oracle table. emitter={json.dumps({k: sorted(v) for k, v in actual.items()}, sort_keys=True)} "
            f"expected={json.dumps({k: sorted(v) for k, v in EXPECTED_EVENT_FIELDS.items()}, sort_keys=True)}"
        )

    if trace.ORACLE_CONFORMANCE != "NOT_RUN":
        errors.append(
            f"trace: ORACLE_CONFORMANCE is {trace.ORACLE_CONFORMANCE!r}; only an "
            "actual comparison run may change it"
        )

    success = trace.succeed(run=0, attempt=0, artifact=1)
    for bad, why in (
        ({"kind": "succeed", "run": 0, "attempt": 0}, "a missing field"),
        (dict(success, extra=1), "an unknown field"),
        ({"kind": "invented", "run": 0}, "an unknown kind"),
        ({"kind": "succeed", "run": -1, "attempt": 0, "artifact": 0}, "a negative identifier"),
        ({"kind": "finalize", "run": 0, "complete": "yes"}, "a non-boolean complete"),
    ):
        try:
            trace.validate_event(bad)
        except trace.TraceError:
            counts["malformed events rejected"] += 1
        else:
            errors.append(f"trace: validate_event accepted {why}")

    try:
        trace.cite(derived_from={"kind": "timeout", "run": 0, "attempt": 0})
    except trace.UnsupportedEvidence:
        counts["unsupported citation refused"] += 1
    else:
        errors.append(
            "trace: a citation was built from something other than a recorded "
            "success, so an unsupported mention could become observed evidence"
        )
    # Reported rather than raised: a checker that crashes on the first finding
    # hides every later one.
    try:
        cited = trace.cite(derived_from=success)
        if (cited["run"], cited["attempt"], cited["artifact"]) != (0, 0, 1):
            errors.append("trace: a citation did not copy its success's identifiers")
    except trace.TraceError as exc:
        errors.append(f"trace: a valid citation was refused: {exc}")
    counts["trace checks"] += 1


def check_analysis(errors: list[str], counts: Counter) -> None:
    """Denominators, the timeout rule, and the null result."""
    from runner.analysis import Effect, Verdict, summarize

    def row(arm: str, attempt: str, outcome: str, option: str | None = None) -> dict:
        return {
            "run_id": "r", "case_id": "c", "condition_id": f"c:{arm}:0",
            "arm": arm, "attempt_id": attempt, "outcome": outcome,
            "option_id": option,
        }

    # A timeout on the contrast side leaves the pair unresolved, and is never
    # counted as the model resisting the cue.
    timed_out = summarize([
        row("baseline", "a1", "decision", "A"),
        row("framing", "a2", "timeout"),
    ])
    pair = timed_out.framing_pairs[0]
    if pair.verdict is not Verdict.UNRESOLVED:
        errors.append(
            f"analysis: a timed-out contrast produced verdict "
            f"{pair.verdict.value!r}; it must be unresolved"
        )
    counts_block = timed_out.as_dict()["framing_counts"]
    if counts_block["flip"] or counts_block["stable"]:
        errors.append(
            "analysis: a timeout contributed to the flip or stable count; "
            "docs/evaluation.md forbids reading it as either"
        )
    if timed_out.attempts != 2:
        errors.append(
            f"analysis: denominator was {timed_out.attempts}, expected 2; "
            "every attempted run must be counted"
        )
    if timed_out.effect is not Effect.INSUFFICIENT:
        errors.append(
            f"analysis: with no readable pair the effect must be insufficient, "
            f"got {timed_out.effect.value!r}"
        )

    # Failures stay in the denominator and in their own bucket.
    with_failures = summarize([
        row("baseline", "a1", "decision", "A"),
        row("baseline", "a2", "malformed"),
        row("baseline", "a3", "truncated"),
        row("framing", "a4", "decision", "A"),
    ])
    baseline = next(a for a in with_failures.arms if a.arm.value == "baseline")
    if baseline.attempts != 3:
        errors.append(
            f"analysis: baseline denominator was {baseline.attempts}, expected 3"
        )
    if baseline.failures != {"malformed": 1, "truncated": 1}:
        errors.append(
            f"analysis: failure kinds were collapsed: {baseline.failures}"
        )
    if with_failures.effect is not Effect.NONE_MEASURED:
        errors.append(
            f"analysis: agreeing readable pairs must report none_measured, got "
            f"{with_failures.effect.value!r}"
        )
    if not with_failures.framing_pairs:
        errors.append(
            "analysis: a null result must still produce a complete comparison, "
            "not an empty one"
        )

    flipped = summarize([
        row("baseline", "a1", "decision", "A"),
        row("framing", "a2", "decision", "B"),
    ])
    if flipped.effect is not Effect.MEASURED:
        errors.append("analysis: a differing readable pair was not reported as measured")

    # An empty run is vacuously covered, matching the oracle.
    empty = summarize([])
    if empty.coverage:
        errors.append("analysis: no records should produce no coverage rows")
    covered = summarize([row("baseline", "a1", "malformed")])
    if not covered.coverage[0].covered:
        errors.append(
            "analysis: a fully recorded failure must count as covered; coverage "
            "is not task success"
        )
    counts["analysis checks"] += 1


def check_export(root: Path, errors: list[str], counts: Counter) -> None:
    """The export matches what the page reads, and both copies agree."""
    json_path = root / "frontend/data/export.json"
    wrapper_path = root / "frontend/data/export.js"
    app_path = root / "frontend/app.js"
    if not (json_path.is_file() and wrapper_path.is_file() and app_path.is_file()):
        return

    try:
        document = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"frontend/data/export.json: invalid JSON: {exc}")
        return

    try:
        fields = declared_fields(app_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        errors.append(f"frontend/app.js: {exc}")
        fields = []
    for field in fields:
        if field not in document:
            errors.append(
                f"frontend/app.js reads {field!r} but the export does not "
                "provide it; the page would render an empty pane"
            )
    counts["page fields checked"] += len(fields)

    wrapper = wrapper_path.read_text(encoding="utf-8")
    marker = "window.LANTERN_EXPORT = "
    if marker not in wrapper:
        errors.append("frontend/data/export.js does not assign window.LANTERN_EXPORT")
    else:
        body = wrapper.split(marker, 1)[1].rstrip().rstrip(";")
        try:
            if json.loads(body) != document:
                errors.append(
                    "frontend/data/export.js has drifted from export.json; "
                    "regenerate both with `python3 -m runner.cli export`"
                )
            else:
                counts["export copies agreeing"] += 1
        except json.JSONDecodeError as exc:
            errors.append(f"frontend/data/export.js: invalid JSON payload: {exc}")

    if document.get("oracle_conformance") != "NOT_RUN":
        errors.append(
            f"export: oracle_conformance is "
            f"{document.get('oracle_conformance')!r}; no conformance lane has run"
        )
    if not str(document.get("label", "")).strip():
        errors.append("export: every export must state its label")
    if document.get("all_records_synthetic") and "SYNTHETIC" not in str(document.get("label")).upper():
        errors.append(
            "export: every record is synthetic but the label does not say so; "
            "a screenshot would be mistaken for a result"
        )
    if not document.get("boundaries"):
        errors.append("export: the evidence boundaries must travel with the data")
    counts["export checks"] += 1


def check_frontend(root: Path, errors: list[str], counts: Counter) -> None:
    """No external host, so the page works offline and leaks nothing."""
    for relative in FRONTEND_SOURCES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in EXTERNAL_URL.finditer(text):
            line = text[: match.start()].count("\n") + 1
            errors.append(
                f"{relative}:{line}: external URL; the page must be fully "
                "self-contained and make no network request"
            )
        counts["frontend files scanned"] += 1


def check_fixtures(root: Path, errors: list[str], counts: Counter) -> None:
    """Fixtures validate, and synthetic records say so on every line."""
    from runner.cases import CaseError, load_cases
    from runner.recording import read_attempts

    try:
        cases = load_cases(root / "fixtures/cases")
        counts["fixture cases"] += len(cases)
        for case in cases:
            if "EXAMPLE" not in case.status.upper() and "FICTION" not in case.status.upper():
                errors.append(
                    f"fixtures: case {case.id!r} has status {case.status!r}; an "
                    "unapproved fixture must say so in its status"
                )
    except CaseError as exc:
        errors.append(f"fixtures: {exc}")

    attempts = root / "fixtures/attempts/example.jsonl"
    if attempts.is_file():
        for number, record in enumerate(read_attempts(attempts), start=1):
            if record.get("synthetic") is not True:
                errors.append(
                    f"fixtures/attempts/example.jsonl:{number}: record is not "
                    "marked synthetic; placeholder data must be labelled on "
                    "every line"
                )
            counts["fixture attempts"] += 1


def check_oracle(root: Path, oracle: Path, errors: list[str], counts: Counter) -> dict:
    """Optional, off by default: ask the oracle to judge one emitted trace.

    This is a separate lane and a narrow observation. It shows that the oracle
    accepts a document this code produced from the synthetic fixture. It is not
    a conformance lane: one trace, no injected faults, and the oracle is not an
    independent checker of this Python.
    """
    from runner.outcomes import Outcome
    from runner.recording import read_attempts
    from runner import trace as trace_mod

    records = list(read_attempts(root / "fixtures/attempts/example.jsonl"))
    ids = trace_mod.IdSpace()
    events: list[dict] = []
    for record in records:
        run = ids.intern("run", str(record["run_id"]))
        operation = ids.intern("operation", str(record["condition_id"]))
        attempt = ids.intern("attempt", str(record["attempt_id"]))
        payload = ids.intern("payload", str(record.get("prompt_sha256") or "unknown"))
        events.append(trace_mod.dispatch(
            run=run, operation=operation, attempt=attempt, payload=payload))
        outcome = Outcome(str(record["outcome"]))
        if outcome is Outcome.TIMEOUT:
            events.append(trace_mod.timeout(run=run, attempt=attempt))
        elif outcome is Outcome.DECISION:
            artifact = ids.intern("artifact", str(record["attempt_id"]) + ":output")
            events.append(trace_mod.succeed(run=run, attempt=attempt, artifact=artifact))
        else:
            events.append(trace_mod.fail(run=run, attempt=attempt))

    document = json.dumps(trace_mod.document(events))
    try:
        completed = subprocess.run(
            [str(oracle)], input=document, text=True,
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        errors.append(f"oracle lane: could not run {oracle}: {exc}")
        return {"status": "ERROR", "detail": str(exc)}
    if completed.returncode != 0:
        errors.append(
            f"oracle lane: {oracle} exited {completed.returncode}: "
            f"{completed.stderr.strip()[:200]}"
        )
        return {"status": "ERROR", "exit": completed.returncode}
    try:
        verdict = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"oracle lane: unreadable verdict: {exc}")
        return {"status": "ERROR", "detail": str(exc)}
    if verdict.get("accepted") is not True:
        errors.append(
            f"oracle lane: the emitted trace was rejected with category "
            f"{verdict.get('category')!r} at event {verdict.get('index')}"
        )
        return {"status": "REJECTED", "category": verdict.get("category"),
                "index": verdict.get("index")}
    counts["oracle traces accepted"] += 1
    return {
        "status": "ACCEPTED",
        "events": len(events),
        "coverage": verdict["state"]["coverage"],
        "limitation": "One synthetic trace accepted. No injected faults, no "
                      "independent checker: this is not a conformance lane.",
    }


def check(root: Path, *, oracle: Path | None = None) -> tuple[list[str], Counter, dict]:
    """Run every check. Returns errors, counts, and the optional oracle lane."""
    root = root.resolve()
    errors: list[str] = []
    counts: Counter = Counter()
    oracle_lane: dict = {"status": "NOT_RUN",
                         "detail": "no --oracle path given; conformance is NOT_RUN"}

    check_layout(root, errors, counts)
    check_modules(errors, counts)
    if errors:
        # Later checks import the modules; stop rather than cascade.
        return errors, counts, oracle_lane
    check_seams(errors, counts)
    check_conditions(errors, counts)
    check_recording(errors, counts)
    check_trace(errors, counts)
    check_analysis(errors, counts)
    check_export(root, errors, counts)
    check_frontend(root, errors, counts)
    check_fixtures(root, errors, counts)
    if oracle is not None:
        oracle_lane = check_oracle(root, oracle, errors, counts)
    return errors, counts, oracle_lane


class CheckerTests(unittest.TestCase):
    """Each test makes one check fail, so a silent checker cannot pass."""

    def test_adapter_check_catches_a_stub_without_transport(self):
        from runner import models

        stub = models.RawOutput("synthetic stub", models.Provenance(models.ExecutionSite.LOCAL))
        with patch.object(models.UnapprovedAdapter, "generate", return_value=stub):
            with self.assertRaisesRegex(ValueError, "raw output, truncation, or request ordering"):
                check_adapter()

    def test_adapter_check_catches_restored_refusal(self):
        from runner import models

        with patch.object(models.UnapprovedAdapter, "generate", side_effect=NotImplementedError("regressed")):
            errors: list[str] = []
            check_seams(errors, Counter())
        self.assertTrue(any("UnapprovedAdapter.generate: documented as implemented but refused" in e
                            for e in errors), errors)

    def test_adapter_check_catches_lost_truncation(self):
        from dataclasses import replace
        from runner import models

        original = models.UnapprovedAdapter.generate

        def lose_truncation(adapter, payload):
            return replace(original(adapter, payload), truncated_by_limit=False)

        with patch.object(models.UnapprovedAdapter, "generate", lose_truncation):
            with self.assertRaisesRegex(ValueError, "truncation"):
                check_adapter()

    def test_adapter_check_catches_lost_error_body(self):
        from runner import models
        from runner.unknown import UNKNOWN

        original = models.UnapprovedAdapter.generate

        def lose_error_body(adapter, payload):
            try:
                return original(adapter, payload)
            except models.AdapterExecutionError as exc:
                exc.raw_output = UNKNOWN
                raise

        with patch.object(models.UnapprovedAdapter, "generate", lose_error_body):
            with self.assertRaisesRegex(ValueError, "API failure lost its body"):
                check_adapter()

    def test_default_lane_opens_no_socket(self):
        import socket

        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")) as sockets, \
                patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")) as connections:
            errors, counts, oracle = check(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(counts["seams refusing"], 2)
        self.assertEqual(counts["implemented callables"], 5)
        self.assertEqual(oracle["status"], "NOT_RUN")
        sockets.assert_not_called()
        connections.assert_not_called()

    def test_declared_fields_parses_and_rejects_absence(self):
        self.assertEqual(
            declared_fields("const FIELDS = [\n 'a',\n \"b\"\n];"), ["a", "b"])
        with self.assertRaises(ValueError):
            declared_fields("const OTHER = ['a'];")

    def test_layout_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            errors: list[str] = []
            check_layout(Path(temporary), errors, Counter())
            self.assertEqual(len(errors), len(REQUIRED))
            self.assertIn("required file is missing", errors[0])

    def test_event_table_matches_the_oracle(self):
        from runner import trace
        self.assertEqual(
            {k: set(v) for k, v in trace.EVENT_FIELDS.items()},
            EXPECTED_EVENT_FIELDS,
        )

    def test_trace_check_catches_a_drifted_table(self):
        from runner import trace
        original = trace.EVENT_FIELDS
        trace.EVENT_FIELDS = dict(original, succeed=("run", "attempt"))
        try:
            errors: list[str] = []
            check_trace(errors, Counter())
            self.assertTrue(any("does not match" in e for e in errors), errors)
        finally:
            trace.EVENT_FIELDS = original

    def test_trace_check_catches_a_claimed_conformance(self):
        from runner import trace
        original = trace.ORACLE_CONFORMANCE
        trace.ORACLE_CONFORMANCE = "PASS"
        try:
            errors: list[str] = []
            check_trace(errors, Counter())
            self.assertTrue(any("ORACLE_CONFORMANCE" in e for e in errors), errors)
        finally:
            trace.ORACLE_CONFORMANCE = original

    def test_seam_check_catches_an_implemented_seam(self):
        from runner import parsing
        original = parsing.grade
        parsing.grade = lambda decision, case: None
        try:
            errors: list[str] = []
            check_seams(errors, Counter())
            self.assertTrue(
                any("returned a value instead of refusing" in e for e in errors),
                errors,
            )
        finally:
            parsing.grade = original

    def test_parser_check_catches_restored_seam(self):
        from runner import parsing

        with patch.object(parsing, "parse", side_effect=NotImplementedError("regressed")):
            errors: list[str] = []
            check_seams(errors, Counter())
        self.assertTrue(any("runner.parsing.parse: documented as implemented but refused" in e
                            for e in errors), errors)

    def test_parser_check_catches_plausible_but_wrong_results(self):
        from runner import parsing

        for result in [None, parsing.Decision("", parsing.ParseSignal()),
                       parsing.Decision("invented", parsing.ParseSignal(decodable=True, choice_in_rubric=True))]:
            with self.subTest(result=result):
                with patch.object(parsing, "parse", return_value=result):
                    errors: list[str] = []
                    check_seams(errors, Counter())
                self.assertTrue(any("runner.parsing.parse:" in e for e in errors), errors)

    def test_seam_check_catches_an_implemented_callable_that_refuses(self):
        """The mirror guard: a promoted seam must not quietly start refusing.

        Without this, moving a function from `seams` to `implemented` would be
        checked in one direction only, and a regression that restored the
        `NotImplementedError` would read as a clean lane.
        """
        from runner import prompts
        original = prompts.render

        def refuse(case, condition):
            raise NotImplementedError("regressed")

        prompts.render = refuse
        try:
            errors: list[str] = []
            check_seams(errors, Counter())
            self.assertTrue(
                any("documented as implemented but refused" in e for e in errors),
                errors,
            )
        finally:
            prompts.render = original

    def test_analysis_check_catches_a_timeout_counted_as_stable(self):
        from runner import analysis
        original = analysis._usable_choice
        analysis._usable_choice = lambda records: ("A", "pretend readable")
        try:
            errors: list[str] = []
            check_analysis(errors, Counter())
            self.assertTrue(any("unresolved" in e for e in errors), errors)
        finally:
            analysis._usable_choice = original

    def test_recording_check_catches_a_defaulted_unknown(self):
        from runner import recording
        original = recording.encode
        recording.encode = lambda value: 0 if isinstance(value, recording.Unknown) else value
        try:
            errors: list[str] = []
            check_recording(errors, Counter())
            self.assertTrue(any("must be null" in e for e in errors), errors)
        finally:
            recording.encode = original

    def test_frontend_check_catches_an_external_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontend").mkdir()
            (root / "frontend/app.js").write_text(
                "fetch('https://cdn.example.com/x.js');", encoding="utf-8")
            errors: list[str] = []
            check_frontend(root, errors, Counter())
            self.assertTrue(any("external URL" in e for e in errors), errors)

    def test_export_check_catches_a_field_the_page_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontend/data").mkdir(parents=True)
            document = {
                "label": "SYNTHETIC EXAMPLE", "oracle_conformance": "NOT_RUN",
                "boundaries": [{"title": "t"}],
            }
            body = json.dumps(document)
            (root / "frontend/data/export.json").write_text(body, encoding="utf-8")
            (root / "frontend/data/export.js").write_text(
                "window.LANTERN_EXPORT = " + body + ";", encoding="utf-8")
            (root / "frontend/app.js").write_text(
                "const FIELDS = ['label', 'analysis'];", encoding="utf-8")
            errors: list[str] = []
            check_export(root, errors, Counter())
            self.assertTrue(any("'analysis'" in e for e in errors), errors)

    def test_export_check_catches_a_drifted_wrapper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontend/data").mkdir(parents=True)
            document = {
                "label": "SYNTHETIC EXAMPLE", "oracle_conformance": "NOT_RUN",
                "boundaries": [{"title": "t"}],
            }
            (root / "frontend/data/export.json").write_text(
                json.dumps(document), encoding="utf-8")
            (root / "frontend/data/export.js").write_text(
                'window.LANTERN_EXPORT = {"label": "stale"};', encoding="utf-8")
            (root / "frontend/app.js").write_text(
                "const FIELDS = ['label'];", encoding="utf-8")
            errors: list[str] = []
            check_export(root, errors, Counter())
            self.assertTrue(any("drifted" in e for e in errors), errors)

    def test_export_check_catches_an_unlabelled_synthetic_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontend/data").mkdir(parents=True)
            document = {
                "label": "Results", "oracle_conformance": "NOT_RUN",
                "all_records_synthetic": True, "boundaries": [{"title": "t"}],
            }
            body = json.dumps(document)
            (root / "frontend/data/export.json").write_text(body, encoding="utf-8")
            (root / "frontend/data/export.js").write_text(
                "window.LANTERN_EXPORT = " + body + ";", encoding="utf-8")
            (root / "frontend/app.js").write_text(
                "const FIELDS = ['label'];", encoding="utf-8")
            errors: list[str] = []
            check_export(root, errors, Counter())
            self.assertTrue(any("mistaken for a result" in e for e in errors), errors)

    def test_conditions_check_catches_a_framing_eligible_correction(self):
        from runner import conditions
        original = conditions.EVIDENCE_CHANGING
        conditions.EVIDENCE_CHANGING = frozenset()
        try:
            errors: list[str] = []
            check_conditions(errors, Counter())
            self.assertTrue(
                any("excluded from the framing-only" in e for e in errors), errors)
        finally:
            conditions.EVIDENCE_CHANGING = original

    def test_fixture_check_catches_an_unlabelled_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "fixtures/attempts").mkdir(parents=True)
            (root / "fixtures/cases").mkdir(parents=True)
            (root / "fixtures/attempts/example.jsonl").write_text(
                json.dumps({"synthetic": False}) + "\n", encoding="utf-8")
            errors: list[str] = []
            check_fixtures(root, errors, Counter())
            self.assertTrue(any("not\nmarked synthetic" in e or "marked synthetic" in e
                                for e in errors), errors)

    def test_default_lane_spawns_no_subprocess(self):
        """Without --oracle the lane runs nothing: no shell, no model, no binary.

        Asserted behaviourally rather than by grepping this file, so the test
        cannot pass merely because a string was spelled differently.
        """
        calls: list[object] = []

        def refuse(*args, **kwargs):
            calls.append(args)
            raise AssertionError("the default lane must not spawn a subprocess")

        original = subprocess.run
        subprocess.run = refuse
        try:
            check(ROOT)
        finally:
            subprocess.run = original
        self.assertEqual(calls, [])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline checks for the LANTERN application skeleton. "
                    "Establishes coherence, not application correctness.",
    )
    parser.add_argument("--self-test", action="store_true",
                        help="run the checker's own tests and exit")
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    parser.add_argument("--oracle", default=None,
                        help="path to the Lean oracle binary; adds one separate "
                             "observation and is not a conformance lane")
    parser.add_argument("--report", default=None,
                        help="write the result as JSON to this path")
    args = parser.parse_args()

    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CheckerTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    errors, counts, oracle_lane = check(
        Path(args.root), oracle=Path(args.oracle) if args.oracle else None)

    summary = {
        "status": "FAIL" if errors else "PASS",
        "lane": "local application skeleton",
        "establishes": "module coherence, seam refusal, counting rules, "
                       "export/page agreement, offline frontend",
        "does_not_establish": [
            "Alpha connectivity or inference", "model behaviour",
            "design-oracle conformance", "reduced bias", "experiment results",
        ],
        "oracle_lane": oracle_lane,
        "counts": dict(sorted(counts.items())),
        "errors": errors,
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    detail = ", ".join(f"{value} {key}" for key, value in sorted(counts.items()))
    print(f"{summary['status']}: {detail}")
    print(f"oracle lane: {oracle_lane['status']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
