"""Import a complete Alpha evidence bundle without changing its source files.

This module never submits jobs, executes models, or interprets logs as answers.
The version-0 bundle contract is documented in docs/alpha-import.md.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

from runner import SCHEMA_VERSION, parsing, recording
from runner.cases import Case, load_cases
from runner.conditions import Arm, Condition
from runner.models import ExecutionSite, Provenance
from runner.outcomes import Correctness, Outcome, classify
from runner.unknown import UNKNOWN

FORMAT = "lantern.alpha.batch"
IDENTITY = ("execution_site", "model_id", "model_revision", "harness", "harness_version")
SHA256 = re.compile(r"[0-9a-f]{64}")


class ImportError(ValueError):
    """A bundle or destination is unsafe to import; no validation writes occur."""


@dataclass(frozen=True)
class ImportReport:
    bundle_path: str
    run_id: str
    evidence_hashes: dict[str, str]
    appended: int
    skipped: int
    not_started: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def _fail(message: str):
    raise ImportError(message)


def _object(value: object, keys: set[str], where: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{where}: expected an object")
    if set(value) != keys:
        _fail(f"{where}: missing fields {sorted(keys - set(value))}; "
              f"unexpected fields {sorted(set(value) - keys)}")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{where}: expected a non-empty string")
    return value


def _hash(value: object, where: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        _fail(f"{where}: expected a lowercase SHA-256 digest")
    return value


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            _fail(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def _json(raw: bytes | str, where: str):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda value: _fail(f"non-finite number {value}"))
    except (ValueError, UnicodeError) as exc:
        raise ImportError(f"{where}: {exc}") from exc


def _file(root: Path, name: str) -> Path:
    """Only canonical relative paths; reject symlinks even within the bundle."""
    _text(name, "evidence path")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or ".." in relative.parts or "\\" in name
            or relative.as_posix() != name or name == "."):
        _fail(f"evidence path {name!r}: expected a canonical relative path")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            _fail(f"evidence path {name!r}: symlinks are refused")
    if not path.is_file() or not path.resolve().is_relative_to(root):
        _fail(f"evidence path {name!r}: missing or not a regular file in the bundle")
    return path


def _identity(value: object, where: str) -> dict:
    value = _object(value, set(IDENTITY), where)
    for key in IDENTITY:
        _text(value[key], f"{where}.{key}")
    if value["execution_site"] != ExecutionSite.ALPHA_BATCH.value:
        _fail(f"{where}: execution_site must be alpha_batch")
    return value


def _provenance(raw: object, identity: dict, where: str) -> Provenance:
    names = {field.name for field in fields(Provenance)}
    if not isinstance(raw, dict) or set(raw) - names or set(IDENTITY) - set(raw):
        _fail(f"{where}: invalid provenance fields or missing model/runtime identity")
    if any(raw[key] != identity[key] for key in IDENTITY):
        _fail(f"{where}: model/runtime identity differs from batch")
    integers = {"context_limit", "max_new_tokens", "seed", "prompt_tokens",
                "completion_tokens", "peak_memory_bytes"}
    numbers = {"temperature", "top_p", "runtime_seconds"}
    values = {}
    for key, value in raw.items():
        if value is None:
            values[key] = UNKNOWN
        elif key in integers:
            if type(value) is not int or value < 0:
                _fail(f"{where}.{key}: expected a non-negative integer or null")
            values[key] = value
        elif key in numbers:
            if (type(value) not in (int, float) or value < 0
                    or isinstance(value, float) and not math.isfinite(value)):
                _fail(f"{where}.{key}: expected a finite non-negative number or null")
            if key == "top_p" and value > 1:
                _fail(f"{where}.top_p: must be at most 1")
            values[key] = value
        else:
            values[key] = _text(value, f"{where}.{key}")
    values["execution_site"] = ExecutionSite.ALPHA_BATCH
    return Provenance(**values)


def _existing_row(row: object, identity: dict, synthetic: bool, where: str) -> dict:
    """Require an existing record to round-trip through current runner types."""
    row = _object(row, {f.name for f in fields(recording.AttemptRecord)} | {"unknown"}, where)
    if type(row["schema_version"]) is not int or row["schema_version"] != SCHEMA_VERSION:
        _fail(f"{where}: incompatible schema_version")
    if type(row["synthetic"]) is not bool or row["synthetic"] != synthetic:
        _fail(f"{where}: incompatible synthetic/experimental evidence")
    provenance = row["provenance"]
    if not isinstance(provenance, dict) or any(provenance.get(k) != identity[k] for k in IDENTITY):
        _fail(f"{where}: incompatible model/runtime identity")
    signal = row["parse_signal"]
    if (not isinstance(signal, dict) or set(signal) - {f.name for f in fields(parsing.ParseSignal)}
            or any(type(value) is not bool for value in signal.values())):
        _fail(f"{where}: parse signals must contain known boolean fields")
    if not isinstance(row["mentions"], list) or not isinstance(row["errors"], list):
        _fail(f"{where}: mentions and errors must be lists")
    for mention in row["mentions"]:
        mention = _object(mention, {"source", "supported", "evidence_id"}, f"{where}.mention")
        _text(mention["source"], f"{where}.mention.source")
        if type(mention["supported"]) is not bool:
            _fail(f"{where}: mention.supported must be boolean")
        if mention["evidence_id"] is not None:
            _text(mention["evidence_id"], f"{where}.mention.evidence_id")
    for error in row["errors"]:
        _text(error, f"{where}.errors")
    values = {key: value for key, value in row.items() if key != "unknown"}
    for name in ("raw_output", "prompt_sha256", "option_id", "received_explanation"):
        value = values[name]
        if value is not None and not isinstance(value, str):
            _fail(f"{where}.{name}: expected a string or null")
        values[name] = value if value is not None else UNKNOWN
    values.update(arm=Arm(row["arm"]), outcome=Outcome(row["outcome"]),
                  correctness=Correctness(row["correctness"]),
                  provenance=_provenance(provenance, identity, f"{where}.provenance"),
                  mentions=tuple(row["mentions"]), errors=tuple(row["errors"]))
    if recording.AttemptRecord(**values).as_dict() != row:
        _fail(f"{where}: record fields/unknown index do not match the current schema")
    return row


def _record(attempt: dict, result: dict, case: Case, batch: dict) -> recording.AttemptRecord:
    """Use the existing parser only for completed, non-truncated output."""
    status, termination = result["status"], result["termination_reason"]
    errors = tuple(result["errors"])
    signal = parsing.ParseSignal(
        timed_out=status == "timeout",
        transport_error=status == "error" or (status == "returned" and termination == "unknown"),
        truncated=termination == "token_limit",
    )
    decision = None
    correctness = Correctness.UNKNOWN
    if status == "returned" and termination == "eos":
        try:
            decision = parsing.parse(result["raw_output"], case)
            signal = decision.signal
            if classify(signal) is Outcome.DECISION:
                if decision.option_id not in {option.id for option in case.options}:
                    _fail(f"{attempt['attempt_id']}: parser returned an option outside the case")
                correctness = parsing.grade(decision, case)
        except NotImplementedError as exc:
            raise ImportError(f"{attempt['attempt_id']}: approved parser/grader unavailable: {exc}") from exc
    elif status == "returned" and termination == "unknown":
        errors += ("termination unknown; output cannot establish a completed decision",)
    outcome = classify(signal)
    return recording.AttemptRecord(
        run_id=batch["run_id"], case_id=attempt["case_id"],
        condition_id=attempt["condition_id"], arm=Arm(attempt["arm"]),
        attempt_id=attempt["attempt_id"], operation_id=attempt["operation_id"],
        outcome=outcome, provenance=_provenance(result["provenance"], batch["identity"], attempt["attempt_id"]),
        raw_output=result["raw_output"] if result["raw_output"] is not None else UNKNOWN,
        prompt_sha256=attempt["prompt_sha256"],
        option_id=decision.option_id if decision is not None else UNKNOWN,
        correctness=correctness, parse_signal=signal.as_dict(),
        mentions=tuple(asdict(mention) for mention in decision.mentions) if decision else (),
        received_explanation=(decision.received_explanation
                              if decision and decision.received_explanation is not None else UNKNOWN),
        errors=errors, synthetic=batch["synthetic"],
    )


def import_bundle(bundle_dir: str | Path, *, cases_dir: str | Path,
                  attempts_path: str | Path) -> ImportReport:
    """Validate everything, reconcile existing records, then append new ones.

    Requires exclusive human-coordinated ownership of the dataset and stable
    evidence during import. I/O failure can leave a partial append: retry skips
    complete matching records, but refuses a truncated destination line.
    """
    try:
        return _import_bundle(Path(bundle_dir), Path(cases_dir), Path(attempts_path))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, ImportError):
            raise
        raise ImportError(str(exc)) from exc


def _import_bundle(bundle: Path, cases_dir: Path, destination: Path) -> ImportReport:
    root = bundle.resolve(strict=True)
    if not root.is_dir():
        _fail(f"{root}: bundle must be a directory")
    if destination.is_symlink() or destination.resolve().is_relative_to(root):
        _fail("dataset must be outside the evidence bundle and must not be a symlink")
    if destination.exists() and (not destination.is_file() or destination.stat().st_nlink != 1):
        _fail("dataset must be a regular file with a single hard link")
    batch_bytes = _file(root, "batch.json").read_bytes()
    result_bytes = _file(root, "results.jsonl").read_bytes()
    batch = _object(_json(batch_bytes, "batch.json"), {
        "format", "schema_version", "purpose", "synthetic", "run_id", "identity", "attempts", "evidence",
    }, "batch.json")
    if batch["format"] != FORMAT or type(batch["schema_version"]) is not int or batch["schema_version"] != 0:
        _fail("batch.json: unsupported format/schema_version")
    if batch["purpose"] != "experimental":
        _fail("batch.json: only experimental bundles can enter an attempt dataset")
    if type(batch["synthetic"]) is not bool:
        _fail("batch.json.synthetic: expected a boolean")
    _text(batch["run_id"], "batch.json.run_id")
    _identity(batch["identity"], "batch.json.identity")
    hashes = {"batch.json": _digest(batch_bytes), "results.jsonl": _digest(result_bytes)}
    if not isinstance(batch["evidence"], list):
        _fail("batch.json.evidence: expected a list")
    for entry in batch["evidence"]:
        entry = _object(entry, {"path", "purpose", "sha256"}, "evidence entry")
        name = _text(entry["path"], "evidence path")
        if name in hashes:
            _fail(f"evidence: duplicate or reserved path {name!r}")
        _text(entry["purpose"], f"{name}.purpose")
        actual = _digest(_file(root, name).read_bytes())
        if actual != _hash(entry["sha256"], f"{name}.sha256"):
            _fail(f"{name}: evidence hash mismatch")
        hashes[name] = actual
    cases = {case.id: case for case in load_cases(cases_dir)}
    attempts: dict[str, dict] = {}
    if not isinstance(batch["attempts"], list) or not batch["attempts"]:
        _fail("batch.json.attempts: expected a non-empty list")
    for attempt in batch["attempts"]:
        attempt = _object(attempt, {"attempt_id", "case_id", "condition_id", "arm", "operation_id",
                                    "prompt", "prompt_sha256"}, "scheduled attempt")
        for key in attempt:
            _text(attempt[key], f"attempt.{key}")
        aid = attempt["attempt_id"]
        if aid in attempts:
            _fail(f"{aid}: duplicate scheduled attempt")
        if attempt["case_id"] not in cases:
            _fail(f"{aid}: unknown case {attempt['case_id']!r}")
        # Condition IDs encode the case, arm, and a canonical non-negative index.
        prefix = f"{attempt['case_id']}:{Arm(attempt['arm']).value}:"
        index = attempt["condition_id"].removeprefix(prefix)
        if not re.fullmatch(r"0|[1-9][0-9]*", index):
            _fail(f"{aid}: condition_id does not match case/arm/index")
        condition = Condition(attempt["case_id"], Arm(attempt["arm"]), int(index))
        if condition.id != attempt["condition_id"] or attempt["operation_id"] != condition.id:
            _fail(f"{aid}: condition/operation identity mismatch")
        if _digest(attempt["prompt"].encode("utf-8")) != _hash(attempt["prompt_sha256"], f"{aid}.prompt_sha256"):
            _fail(f"{aid}: prompt hash mismatch")
        attempts[aid] = attempt
    results: dict[str, dict] = {}
    for number, line in enumerate(result_bytes.splitlines(), 1):
        result = _object(_json(line, f"results.jsonl:{number}"), {
            "attempt_id", "prompt_sha256", "status", "termination_reason", "raw_output", "provenance", "errors",
        }, f"results.jsonl:{number}")
        aid = _text(result["attempt_id"], f"results.jsonl:{number}.attempt_id")
        if aid not in attempts or aid in results:
            _fail(f"{aid}: unexpected or duplicate result")
        if result["prompt_sha256"] != attempts[aid]["prompt_sha256"]:
            _fail(f"{aid}: result prompt hash mismatch")
        status, termination = result["status"], result["termination_reason"]
        if status not in ("returned", "timeout", "error", "not_started"):
            _fail(f"{aid}: unsupported execution status")
        if termination not in ("eos", "token_limit", "unknown"):
            _fail(f"{aid}: unsupported termination reason")
        if status != "returned" and termination != "unknown":
            _fail(f"{aid}: non-returned status requires unknown termination")
        raw = result["raw_output"]
        if ((raw is not None and not isinstance(raw, str))
                or (status == "returned" and raw is None)):
            _fail(f"{aid}: raw_output must be a string (or null for a non-returned attempt)")
        if status == "not_started" and raw is not None:
            _fail(f"{aid}: not_started cannot have model output")
        errors = result["errors"]
        if not isinstance(errors, list) or any(not isinstance(e, str) or not e.strip() for e in errors):
            _fail(f"{aid}: errors must be a list of non-empty strings")
        if status != "returned" and not errors:
            _fail(f"{aid}: non-returned status requires an explanation in errors")
        _provenance(result["provenance"], batch["identity"], aid)
        results[aid] = result
    missing = sorted(set(attempts) - set(results))
    if missing:
        _fail(f"missing terminal results for attempts: {', '.join(missing)}")
    not_started = tuple(aid for aid in attempts if results[aid]["status"] == "not_started")
    records = [_record(a, results[aid], cases[a["case_id"]], batch)
               for aid, a in attempts.items() if aid not in not_started]
    existing: dict[tuple[str, str], dict] = {}
    if destination.exists():
        raw_dataset = destination.read_bytes()
        if raw_dataset and not raw_dataset.endswith(b"\n"):
            _fail("dataset has an unterminated final line; inspect it before retrying")
        for number, line in enumerate(raw_dataset.splitlines(), 1):
            row = _existing_row(_json(line, f"dataset:{number}"), batch["identity"],
                                batch["synthetic"], f"dataset:{number}")
            key = (_text(row.get("run_id"), "dataset.run_id"), _text(row.get("attempt_id"), "dataset.attempt_id"))
            if key in existing:
                _fail(f"dataset already contains duplicate identity {key}")
            existing[key] = row
    new = []
    skipped = 0
    for aid in not_started:
        if (batch["run_id"], aid) in existing:
            _fail(f"{aid}: not_started conflicts with an existing attempted response")
    for record in records:
        key = (record.run_id, record.attempt_id)
        if key in existing:
            if existing[key] != record.as_dict():
                _fail(f"{key}: conflicting existing attempt")
            skipped += 1
        else:
            new.append(record)
    # Recheck all source hashes immediately before any destination mutation.
    for name, expected in hashes.items():
        if _digest(_file(root, name).read_bytes()) != expected:
            _fail(f"{name}: evidence changed during import")
    if new:
        recording.append_many(destination, new)
    return ImportReport(str(root), batch["run_id"], hashes, len(new), skipped, not_started)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--attempts", required=True)
    args = parser.parse_args(argv)
    try:
        report = import_bundle(args.bundle, cases_dir=args.cases, attempts_path=args.attempts)
    except ImportError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(report.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
