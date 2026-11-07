"""Append-only attempt records: one line per attempted run, failures included.

Three requirements from docs/evaluation.md shape this module:

1. "Count all attempted runs in completion denominators." Nothing filters here.
   A timeout, a malformed reply, and a clean decision are all written the same
   way, so a denominator computed later cannot silently shrink.
2. "Any missing value remains explicitly unknown." Unknown provenance is
   serialised as ``null`` and named in the record's ``unknown`` list.
3. "A model's explanation is a received explanation." The raw text is retained
   verbatim alongside whatever was extracted from it, and unsupported source
   mentions stay visible instead of being promoted to observed evidence.

The writer opens files in append mode only. There is no update or delete path:
rewriting an attempt record is how a surprising result quietly disappears.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
import json
from pathlib import Path
from typing import Iterator

from runner import SCHEMA_VERSION
from runner.conditions import Arm
from runner.outcomes import Correctness, Outcome
from runner.unknown import UNKNOWN, Unknown, encode, is_known

__all__ = [
    "UNKNOWN", "Unknown", "encode", "is_known",
    "AttemptRecord", "RecordError", "append", "append_many", "read_attempts",
]


class RecordError(ValueError):
    """A record is unusable, or a write would not be append-only."""


@dataclass(frozen=True)
class AttemptRecord:
    """One attempted run, whatever happened to it.

    ``run_id``, ``attempt_id`` and ``operation_id`` are the identifiers the
    Lean design oracle reasons about. The oracle requires attempts to be unique
    within a run and a retry to reuse the operation while taking a new attempt
    id; :mod:`runner.trace` turns these into its integer identifiers. As the
    oracle's README notes, identifiers are not cryptographic attestations.
    """

    run_id: str
    case_id: str
    condition_id: str
    arm: Arm
    attempt_id: str
    operation_id: str
    outcome: Outcome
    provenance: object
    raw_output: str | Unknown = UNKNOWN
    prompt_sha256: str | Unknown = UNKNOWN
    option_id: str | Unknown = UNKNOWN
    correctness: Correctness = Correctness.UNKNOWN
    parse_signal: dict[str, bool] = field(default_factory=dict)
    mentions: tuple[dict[str, object], ...] = ()
    received_explanation: str | Unknown = UNKNOWN
    errors: tuple[str, ...] = ()
    synthetic: bool = False
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("run_id", "case_id", "condition_id", "attempt_id", "operation_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise RecordError(f"{name} must be a non-empty string")
        if self.outcome is Outcome.DECISION and not is_known(self.option_id):
            raise RecordError(
                "an outcome of 'decision' must record which option was chosen; "
                "an unreadable choice is MALFORMED or INVALID_CHOICE instead"
            )
        if self.outcome is not Outcome.DECISION and self.correctness is not Correctness.UNKNOWN:
            raise RecordError(
                f"correctness is only meaningful for a readable decision, "
                f"but outcome is {self.outcome.value!r}"
            )

    def unknown_fields(self) -> tuple[str, ...]:
        """Every unobserved field on the record, provenance included.

        Provenance gaps are reported with a ``provenance.`` prefix so one flat
        list tells a reader exactly what was never measured.
        """
        own = [
            f.name for f in fields(self)
            if isinstance(getattr(self, f.name), Unknown)
        ]
        nested = getattr(self.provenance, "unknown_fields", None)
        if callable(nested):
            own.extend(f"provenance.{name}" for name in nested())
        return tuple(own)

    def as_dict(self) -> dict[str, object]:
        """The wire form: unknowns as ``null``, plus the ``unknown`` index."""
        provenance = self.provenance
        if hasattr(provenance, "__dataclass_fields__"):
            provenance_json: object = {
                f.name: encode(_enum_value(getattr(provenance, f.name)))
                for f in fields(provenance)
            }
        else:
            provenance_json = encode(provenance)
        return {
            "schema_version": self.schema_version,
            "synthetic": self.synthetic,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "condition_id": self.condition_id,
            "arm": self.arm.value,
            "attempt_id": self.attempt_id,
            "operation_id": self.operation_id,
            "outcome": self.outcome.value,
            "correctness": self.correctness.value,
            "option_id": encode(self.option_id),
            "prompt_sha256": encode(self.prompt_sha256),
            "raw_output": encode(self.raw_output),
            "received_explanation": encode(self.received_explanation),
            "parse_signal": dict(self.parse_signal),
            "mentions": [dict(m) for m in self.mentions],
            "errors": list(self.errors),
            "provenance": provenance_json,
            "unknown": list(self.unknown_fields()),
        }


def _enum_value(value: object) -> object:
    """Unwrap an Enum for JSON without touching the unknown sentinel."""
    return value.value if hasattr(value, "value") and not isinstance(value, Unknown) else value


def append(path: str | Path, record: AttemptRecord) -> Path:
    """Append one record as a JSON line. Never truncates or rewrites."""
    return append_many(path, (record,))


def append_many(path: str | Path, records: tuple[AttemptRecord, ...] | list[AttemptRecord]) -> Path:
    """Append several records in order, creating parent directories."""
    path = Path(path)
    if path.exists() and not path.is_file():
        raise RecordError(f"{path}: not a regular file")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for record in records:
        if not isinstance(record, AttemptRecord):
            raise RecordError(f"expected AttemptRecord, got {type(record).__name__}")
        line = json.dumps(record.as_dict(), ensure_ascii=False, sort_keys=True)
        if "\n" in line:
            raise RecordError("a JSON line must not contain a newline")
        lines.append(line)
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")
    return path


def read_attempts(path: str | Path) -> Iterator[dict[str, object]]:
    """Yield decoded records in file order, reporting the offending line number.

    Records are returned as dictionaries rather than rebuilt objects: a file
    written by an earlier schema version must remain readable for inspection
    even when it can no longer be reconstructed.
    """
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                decoded = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RecordError(f"{path}:{number}: invalid JSON: {exc}") from exc
            if not isinstance(decoded, dict):
                raise RecordError(f"{path}:{number}: record must be an object")
            yield decoded
