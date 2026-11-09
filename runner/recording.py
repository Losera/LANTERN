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
from typing import TYPE_CHECKING, Iterator

from runner import SCHEMA_VERSION
from runner.conditions import Arm
from runner.outcomes import Correctness, Outcome, classify
from runner.unknown import UNKNOWN, Unknown, encode, is_known

if TYPE_CHECKING:
    from runner.parsing import Decision, ParseSignal

__all__ = [
    "UNKNOWN", "Unknown", "encode", "is_known",
    "AttemptRecord", "RecordError", "IDENTITY", "append", "append_many",
    "dataset_identity", "read_attempts", "make_attempt_record",
]

#: The provenance fields that together name what produced an attempt. One
#: dataset holds one identity: ``runner/analysis.py`` pairs attempts across
#: arms and computes a single effect, so two models' attempts in one file would
#: be averaged into an effect belonging to neither. The same tuple gates bundle
#: import in ``runner/alpha_import.py``; it is defined here so both paths
#: enforce one rule rather than two that can drift apart.
IDENTITY = ("execution_site", "model_id", "model_revision", "harness",
            "harness_version")


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


def make_attempt_record(
    *,
    run_id: str,
    case_id: str,
    condition_id: str,
    arm: Arm,
    attempt_id: str,
    operation_id: str,
    signal: ParseSignal,
    provenance: object,
    raw_output: str | Unknown,
    prompt_sha256: str | Unknown,
    decision: Decision | None = None,
    correctness: Correctness = Correctness.UNKNOWN,
    errors: tuple[str, ...] = (),
    synthetic: bool = False,
) -> AttemptRecord:
    """Build the shared record shape from one parse result or failure signal.

    This is the common conversion used by local execution and Alpha import:
    outcome classification, extracted choice, mentions, explanation, and
    explicit unknowns are kept consistent at the recording boundary.
    """
    outcome = classify(signal)
    if decision is None:
        option_id = UNKNOWN
        mentions = ()
        explanation = UNKNOWN
    else:
        option_id = decision.option_id
        mentions = tuple(
            {
                "source": mention.source,
                "supported": mention.supported,
                "evidence_id": mention.evidence_id,
            }
            for mention in decision.mentions
        )
        explanation = (
            decision.received_explanation
            if decision.received_explanation is not None else UNKNOWN
        )
    if outcome is not Outcome.DECISION:
        correctness = Correctness.UNKNOWN
    return AttemptRecord(
        run_id=run_id,
        case_id=case_id,
        condition_id=condition_id,
        arm=arm,
        attempt_id=attempt_id,
        operation_id=operation_id,
        outcome=outcome,
        provenance=provenance,
        raw_output=raw_output,
        prompt_sha256=prompt_sha256,
        option_id=option_id,
        correctness=correctness,
        parse_signal=signal.as_dict(),
        mentions=mentions,
        received_explanation=explanation,
        errors=errors,
        synthetic=synthetic,
    )


def _enum_value(value: object) -> object:
    """Unwrap an Enum for JSON without touching the unknown sentinel."""
    return value.value if hasattr(value, "value") and not isinstance(value, Unknown) else value


def _identity_of(provenance: object, where: str) -> tuple:
    """The IDENTITY values of one record's provenance, in a comparable form.

    An unobserved field is ``None`` on the wire and is **not** treated as
    matching a known value. Claiming one model per dataset is not possible when
    a record cannot say which model produced it, so an unknown identity is a
    distinct identity rather than a wildcard.
    """
    if not isinstance(provenance, dict):
        raise RecordError(f"{where}: provenance must be an object")
    return tuple(provenance.get(name) for name in IDENTITY)


def _describe(identity: tuple) -> str:
    """Name an identity in an error, showing an unobserved field as unknown."""
    return ", ".join(
        f"{name}={'unknown' if value is None else value!r}"
        for name, value in zip(IDENTITY, identity)
    )


def dataset_identity(path: str | Path) -> tuple | None:
    """The one model/runtime identity an existing dataset holds.

    Returns ``None`` for a missing or empty file, which any identity may then
    start. Raises if the file already holds more than one identity, so a
    dataset that predates this check cannot pass silently.
    """
    path = Path(path)
    if not path.exists():
        return None
    found: dict[tuple, int] = {}
    for number, record in enumerate(read_attempts(path), start=1):
        found.setdefault(_identity_of(record.get("provenance"), f"{path}:{number}"), number)
    if len(found) > 1:
        lines = sorted(found.values())
        raise RecordError(
            f"{path}: dataset already holds {len(found)} model/runtime identities, "
            f"first differing at lines {lines[0]} and {lines[1]}: "
            + " | ".join(_describe(i) for i in found)
        )
    return next(iter(found), None)


def append(path: str | Path, record: AttemptRecord) -> Path:
    """Append one record as a JSON line. Never truncates or rewrites."""
    return append_many(path, (record,))


def append_many(path: str | Path, records: tuple[AttemptRecord, ...] | list[AttemptRecord]) -> Path:
    """Append several records in order, creating parent directories.

    Refuses a write that would put a second model or runtime identity in one
    dataset. The refusal happens before any byte is written, so a rejected
    batch leaves the file exactly as it was; this module has no update or
    delete path to undo a partial append with.
    """
    path = Path(path)
    if path.exists() and not path.is_file():
        raise RecordError(f"{path}: not a regular file")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    identity = dataset_identity(path)
    for position, record in enumerate(records, start=1):
        if not isinstance(record, AttemptRecord):
            raise RecordError(f"expected AttemptRecord, got {type(record).__name__}")
        wire = record.as_dict()
        incoming = _identity_of(wire.get("provenance"), f"record {position}")
        if identity is None:
            identity = incoming
        elif incoming != identity:
            raise RecordError(
                f"{path}: record {position} would add a second model/runtime identity "
                f"to this dataset. Dataset holds {_describe(identity)}; "
                f"record {position} carries {_describe(incoming)}. "
                "Write it to a separate attempts file."
            )
        line = json.dumps(wire, ensure_ascii=False, sort_keys=True)
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
