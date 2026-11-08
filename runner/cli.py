"""Command line entry point: ``python3 -m runner.cli <command>``."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import uuid

from runner import LANE, SCHEMA_VERSION
from runner.analysis import summarize
from runner.cases import Case, CaseError, load_case, load_cases
from runner.conditions import Arm, Condition, expand, mark_confounded
from runner.export import build_export, write_export
from runner.models import (
    AdapterExecutionError, ExecutionSite, PromptPayload, UnapprovedAdapter,
    Provenance,
)
from runner.outcomes import Correctness, Outcome
from runner.prompts import digest, render
from runner import parsing
from runner.recording import (
    UNKNOWN, Unknown, AttemptRecord, append, append_many, make_attempt_record,
    read_attempts,
)
from runner.trace import IdSpace, ORACLE_CONFORMANCE, document, write_document
from runner import trace as trace_mod

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "fixtures" / "cases"
DEFAULT_ATTEMPTS = ROOT / "fixtures" / "attempts" / "example.jsonl"
DEFAULT_EXPORT = ROOT / "frontend" / "data" / "export.json"
DEFAULT_RUN_ATTEMPTS = ROOT / "data" / "attempts" / "local.jsonl"
SYNTHETIC_LABEL = "SYNTHETIC EXAMPLE — not experiment results"


def _echo(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _conditions_for(cases: tuple[Case, ...], reruns: int) -> tuple[Condition, ...]:
    out: list[Condition] = []
    for case in cases:
        out.extend(expand(case.id, reruns=reruns))
    return tuple(out)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate one case document, or every case in a directory."""
    target = Path(args.path)
    try:
        cases = (load_case(target),) if target.is_file() else load_cases(target)
    except CaseError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    _echo({
        "result": "PASS",
        "schema_version": SCHEMA_VERSION,
        "schema_status": "PROPOSED — see docs/contracts.md",
        "cases": [
            {
                "id": c.id,
                "status": c.status,
                "options": len(c.options),
                "evidence": len(c.evidence),
                "relevant_evidence": len(c.relevant_evidence),
                "irrelevant_evidence": len(c.irrelevant_evidence),
                "rubric": c.rubric.id,
            }
            for c in cases
        ],
    })
    return 0


def cmd_expand(args: argparse.Namespace) -> int:
    """Print the matched condition set for a case."""
    _echo([c.as_dict() for c in expand(args.case_id, reruns=args.reruns)])
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Summarise recorded attempts."""
    records = list(read_attempts(args.attempts))
    analysis = summarize(records)
    _echo(analysis.as_dict())
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Build an oracle trace document from recorded attempts.

    The document is emitted for the oracle to judge. This command never
    reports acceptance: see runner/trace.py for why.
    """
    records = list(read_attempts(args.attempts))
    ids = IdSpace()
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
            success = trace_mod.succeed(run=run, attempt=attempt, artifact=artifact)
            events.append(success)
            for mention in record.get("mentions") or []:
                if isinstance(mention, dict) and mention.get("supported") is True:
                    events.append(trace_mod.cite(derived_from=success))
        else:
            events.append(trace_mod.fail(run=run, attempt=attempt))
    payload = {
        "oracle_conformance": ORACLE_CONFORMANCE,
        "note": "Emitted for the oracle to judge; acceptance is not decided here.",
        "identifiers": ids.mapping(),
        "document": document(events),
    }
    if args.out:
        write_document(args.out, events)
        payload["written"] = str(args.out)
    _echo(payload)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Build the frontend export from cases and recorded attempts."""
    try:
        cases = load_cases(args.cases)
    except CaseError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    records = list(read_attempts(args.attempts))
    conditions = _conditions_for(cases, args.reruns)
    confounded = set(args.confounded or ())
    conditions = tuple(
        mark_confounded(c, "marked confounded on the command line: the edit "
                           "changed facts or accessibility requirements")
        if c.id in confounded else c
        for c in conditions
    )
    analysis = summarize(records, conditions)
    document_ = build_export(
        cases=cases,
        conditions=conditions,
        records=records,
        analysis=analysis,
        label=args.label,
    )
    json_path, wrapper_path = write_export(args.out, document_)
    _echo({
        "result": "written",
        "path": str(json_path),
        "wrapper": str(wrapper_path),
        "label": args.label,
        "lane": LANE,
        "oracle_conformance": ORACLE_CONFORMANCE,
        "cases": len(cases),
        "attempts": analysis.attempts,
        "effect": analysis.effect.value,
    })
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run one case across its matched conditions, recording each attempt."""
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        print("FAIL: --timeout-seconds must be a finite positive number", file=sys.stderr)
        return 1
    if args.run_id is not None and not args.run_id.strip():
        print("FAIL: --run-id must not be empty", file=sys.stderr)
        return 1
    if not args.label.strip():
        print("FAIL: --label must not be empty", file=sys.stderr)
        return 1
    try:
        case = load_case(args.case)
        conditions = expand(case.id, reruns=args.reruns)
    except (CaseError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    run_id = args.run_id or uuid.uuid4().hex
    print(f"RUN_ID={run_id}", file=sys.stderr, flush=True)
    attempts_path = Path(args.attempts)
    case_path = Path(args.case)
    export_path = Path(args.export)
    wrapper_path = export_path.with_suffix(".js")
    try:
        case_target = case_path.resolve()
        attempts_target = attempts_path.resolve()
        export_targets = {export_path.resolve(), wrapper_path.resolve()}
    except OSError as exc:
        print(f"FAIL: cannot resolve input/output paths: {exc}", file=sys.stderr)
        return 1
    if (attempts_target == case_target
            or attempts_target in export_targets
            or case_target in export_targets
            or len(export_targets) != 2):
        print(
            "FAIL: case, attempts, export JSON, and export wrapper must use "
            "different paths",
            file=sys.stderr,
        )
        return 1
    try:
        previous = list(read_attempts(attempts_path)) if attempts_path.exists() else []
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot resume from {attempts_path}: {exc}", file=sys.stderr)
        return 1

    completed: dict[str, dict[str, object]] = {}
    for row in previous:
        if row.get("run_id") != run_id:
            continue
        attempt_id = row.get("attempt_id")
        if not isinstance(attempt_id, str) or attempt_id in completed:
            print(f"FAIL: duplicate or invalid attempt id in run {run_id}", file=sys.stderr)
            return 1
        completed[attempt_id] = row

    expected_ids = {condition.id for condition in conditions}
    unexpected_ids = set(completed) - expected_ids
    if unexpected_ids:
        print(
            "FAIL: existing run has attempts outside this case/rerun plan: "
            + ", ".join(sorted(unexpected_ids)),
            file=sys.stderr,
        )
        return 1

    adapter = UnapprovedAdapter(timeout_seconds=args.timeout_seconds)
    counts: dict[str, int] = {}
    appended = 0
    skipped = 0
    for condition in conditions:
        attempt_id = condition.id
        prompt = None
        render_error = None
        try:
            prompt = render(case, condition)
            if (not isinstance(prompt, PromptPayload)
                    or not isinstance(prompt.text, str)
                    or not isinstance(prompt.sha256, str)):
                raise TypeError("renderer returned an invalid PromptPayload")
            if digest(prompt.text) != prompt.sha256:
                raise ValueError("renderer prompt digest does not match its text")
        except Exception as exc:
            prompt = None
            render_error = f"prompt rendering failed: {type(exc).__name__}: {exc}"

        prompt_hash = prompt.sha256 if prompt is not None else UNKNOWN
        prior = completed.get(attempt_id)
        if prior is not None:
            stored_hash = prior.get("prompt_sha256")
            expected_hash = None if isinstance(prompt_hash, type(UNKNOWN)) else prompt_hash
            if (prior.get("condition_id") != condition.id
                    or prior.get("case_id") != case.id
                    or prior.get("arm") != condition.arm.value
                    or stored_hash != expected_hash):
                print(f"FAIL: existing attempt {attempt_id} conflicts with this run", file=sys.stderr)
                return 1
            skipped += 1
            counts[str(prior.get("outcome", "unknown"))] = (
                counts.get(str(prior.get("outcome", "unknown")), 0) + 1
            )
            continue

        raw_output: str | Unknown = UNKNOWN
        provenance: object = Provenance(execution_site=ExecutionSite.UNKNOWN)
        decision = None
        errors: tuple[str, ...] = ()
        if render_error is not None:
            signal = parsing.ParseSignal(transport_error=True)
            errors = (render_error,)
        else:
            try:
                result = adapter.generate(prompt)
                if not isinstance(result.text, str):
                    raise TypeError("model adapter returned non-string raw output")
                raw_output = result.text
                provenance = result.provenance
                if result.truncated_by_limit:
                    signal = parsing.ParseSignal(truncated=True)
                else:
                    try:
                        decision = parsing.parse(result.text, case)
                        signal = decision.signal
                    except Exception as exc:
                        signal = parsing.ParseSignal(transport_error=True)
                        errors = (f"parsing failed: {type(exc).__name__}: {exc}",)
            except AdapterExecutionError as exc:
                raw_output = exc.raw_output if isinstance(exc.raw_output, str) else UNKNOWN
                provenance = exc.provenance
                signal = parsing.ParseSignal(
                    timed_out=exc.timed_out,
                    transport_error=not exc.timed_out,
                )
                errors = (str(exc) or type(exc).__name__,)
            except Exception as exc:
                signal = parsing.ParseSignal(transport_error=True)
                errors = (f"model execution failed: {type(exc).__name__}: {exc}",)

        record_fields = {
            "run_id": run_id,
            "case_id": case.id,
            "condition_id": condition.id,
            "arm": condition.arm,
            "attempt_id": attempt_id,
            "operation_id": condition.id,
            "signal": signal,
            "provenance": provenance,
            "raw_output": raw_output,
            "prompt_sha256": prompt_hash,
            "decision": decision,
            "correctness": Correctness.UNKNOWN,
            "errors": errors,
        }
        try:
            record = make_attempt_record(**record_fields)
        except Exception as exc:
            record_fields.update({
                "signal": parsing.ParseSignal(transport_error=True),
                "decision": None,
                "errors": errors + (
                    f"record construction failed: {type(exc).__name__}: {exc}",
                ),
            })
            record = make_attempt_record(**record_fields)
        try:
            append(attempts_path, record)
        except (OSError, ValueError) as exc:
            print(f"FAIL: could not append {attempt_id}: {exc}", file=sys.stderr)
            return 1
        appended += 1
        counts[record.outcome.value] = counts.get(record.outcome.value, 0) + 1

    try:
        run_records = [
            row for row in read_attempts(attempts_path)
            if row.get("run_id") == run_id and row.get("case_id") == case.id
        ]
        analysis = summarize(run_records, conditions)
        export_document = build_export(
            cases=(case,),
            conditions=conditions,
            records=run_records,
            analysis=analysis,
            label=args.label,
        )
        export_path, wrapper_path = write_export(args.export, export_document)
    except (OSError, ValueError) as exc:
        print(f"FAIL: attempts were recorded, but analysis/export failed: {exc}", file=sys.stderr)
        return 1

    _echo({
        "result": "complete",
        "run_id": run_id,
        "case_id": case.id,
        "attempts_path": str(attempts_path),
        "conditions": len(conditions),
        "appended": appended,
        "resumed": skipped,
        "outcomes": counts,
        "correctness": "unknown",
        "effect": analysis.effect.value,
        "export": str(export_path),
        "export_wrapper": str(wrapper_path),
    })
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Write the synthetic attempt fixture used by the checker and the page.

    Every record carries ``synthetic: true``. The fixture deliberately covers
    the states a demo would omit: a timeout, a truncation, a malformed reply,
    an unsupported source mention, and a null framing result.
    """
    path = Path(args.out)
    if path.exists() and not args.force:
        print(f"FAIL: {path} exists; pass --force to rewrite", file=sys.stderr)
        return 1
    if path.exists():
        path.unlink()
    case = load_case(args.case)
    local = Provenance(
        execution_site=ExecutionSite.LOCAL,
        model_id="unapproved-placeholder",
        harness="runner.cli synthesize",
        harness_version=f"schema {SCHEMA_VERSION}",
        started_utc="2026-11-07T00:00:00+00:00",
        runtime_seconds=0.0,
    )
    first, second = case.options[0].id, case.options[1].id
    plan = [
        (Arm.BASELINE, 0, Outcome.DECISION, first, ()),
        (Arm.UNCHANGED_RERUN, 0, Outcome.DECISION, first, ()),
        (Arm.NEUTRAL_EDIT, 0, Outcome.DECISION, first, ()),
        (Arm.FRAMING, 0, Outcome.DECISION, first,
         ({"source": "unnamed campus blog", "supported": False, "evidence_id": None},)),
        (Arm.CORRECTION, 0, Outcome.DECISION, second, ()),
        (Arm.FRAMING, 1, Outcome.TIMEOUT, None, ()),
        (Arm.BASELINE, 1, Outcome.TRUNCATED, None, ()),
        (Arm.UNCHANGED_RERUN, 1, Outcome.MALFORMED, None, ()),
    ]
    records: list[AttemptRecord] = []
    for index, (arm, rerun, outcome, option, mentions) in enumerate(plan):
        records.append(AttemptRecord(
            run_id=f"{case.id}-synthetic",
            case_id=case.id,
            condition_id=f"{case.id}:{arm.value}:{rerun}",
            arm=arm,
            attempt_id=f"attempt-{index:02d}",
            operation_id=f"{case.id}:{arm.value}:{rerun}",
            outcome=outcome,
            provenance=local,
            raw_output=f"synthetic placeholder output for {arm.value}",
            prompt_sha256=UNKNOWN,
            option_id=option if option is not None else UNKNOWN,
            correctness=Correctness.UNKNOWN,
            parse_signal={
                "timed_out": outcome is Outcome.TIMEOUT,
                "transport_error": False,
                "truncated": outcome is Outcome.TRUNCATED,
                "refused": False,
                "decodable": outcome is Outcome.DECISION,
                "choice_in_rubric": outcome is Outcome.DECISION,
            },
            mentions=mentions,
            errors=(),
            synthetic=True,
        ))
    append_many(path, records)
    _echo({
        "result": "written",
        "path": str(path),
        "records": len(records),
        "synthetic": True,
        "note": "Placeholder states, not experiment results. No model was run.",
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m runner.cli",
        description="LANTERN runner commands, including a resumable local "
                    "Ollama run for one case.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate a case file or directory")
    p.add_argument("path", nargs="?", default=str(DEFAULT_CASES))
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("expand", help="print a case's matched condition set")
    p.add_argument("case_id")
    p.add_argument("--reruns", type=int, default=1)
    p.set_defaults(func=cmd_expand)

    p = sub.add_parser("analyze", help="summarise recorded attempts")
    p.add_argument("--attempts", default=str(DEFAULT_ATTEMPTS))
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("trace", help="emit an oracle trace document")
    p.add_argument("--attempts", default=str(DEFAULT_ATTEMPTS))
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_trace)

    p = sub.add_parser("export", help="write the frontend export")
    p.add_argument("--cases", default=str(DEFAULT_CASES))
    p.add_argument("--attempts", default=str(DEFAULT_ATTEMPTS))
    p.add_argument("--out", default=str(DEFAULT_EXPORT))
    p.add_argument("--reruns", type=int, default=2)
    p.add_argument("--label", default=SYNTHETIC_LABEL)
    p.add_argument("--confounded", action="append",
                   help="condition id to exclude as confounded; repeatable")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("synthesize", help="write the synthetic attempt fixture")
    p.add_argument("--case", default=str(DEFAULT_CASES / "example-campus-transport.json"))
    p.add_argument("--out", default=str(DEFAULT_ATTEMPTS))
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_synthesize)

    p = sub.add_parser("run", help="run a case with the local Ollama model")
    p.add_argument("--case", required=True, help="path to one case JSON file")
    p.add_argument("--attempts", default=str(DEFAULT_RUN_ATTEMPTS))
    p.add_argument("--reruns", type=int, default=1)
    p.add_argument(
        "--run-id",
        help="stable id for resuming this run; reuse the same value after interruption",
    )
    p.add_argument("--timeout-seconds", type=float, default=300.0)
    p.add_argument("--export", default=str(DEFAULT_EXPORT))
    p.add_argument(
        "--label",
        default="LOCAL OLLAMA RUN — correctness unknown",
        help="label for the generated evidence export",
    )
    p.set_defaults(func=cmd_run)

    return parser


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
