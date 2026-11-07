"""Emitting event traces in the Lean design oracle's vocabulary.

The oracle at ``lantern-formal`` proves safety properties about a transition
system over seven events. Its handoff note carries one instruction that
determines this module's whole shape:

    "Do not create a dummy Python state machine merely to claim conformance."

So this module **builds and shapes events; it never decides whether a trace is
acceptable.** That verdict belongs to the oracle binary, fed a trace and asked.
Reimplementing ``step`` here in Python would produce a second, unproved
implementation that agrees with itself -- and agreement with yourself is not
evidence. :data:`ORACLE_CONFORMANCE` stays ``NOT_RUN`` until a real lane runs.

What this module *can* check locally, because it is construction and not
semantics:

Field discipline
    ``Lantern/Wire.lean`` rejects unknown fields so a misspelled
    safety-relevant field cannot be ignored. :func:`validate_event` enforces
    the exact field set per kind, and that every identifier is a natural
    number.

The citation guard
    :func:`cite` will not build a citation unless the caller hands over the
    recorded success it derives from. That is a guard at the construction
    site, not a state machine: the oracle still decides whether the resulting
    trace is accepted. It exists because the oracle's README is emphatic that
    ``cite`` admits observed evidence only, and that a raw source mention must
    stay visible without being promoted to an observed edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

#: Whether the application's traces have been checked against the oracle.
#: Recorded in every export. Changing this requires an actual comparison run,
#: not an assertion: see docs/status.md for the evidence lanes.
ORACLE_CONFORMANCE = "NOT_RUN"

#: Exact field set per event kind, transcribed from the table in
#: ``lantern-formal/Lantern/Wire.lean`` and its README. ``kind`` is implicit.
EVENT_FIELDS: Mapping[str, tuple[str, ...]] = {
    "dispatch": ("run", "operation", "attempt", "payload"),
    "succeed": ("run", "attempt", "artifact"),
    "fail": ("run", "attempt"),
    "timeout": ("run", "attempt"),
    "cite": ("run", "attempt", "artifact"),
    "commit": ("run", "operation", "payload"),
    "finalize": ("run", "complete"),
}

#: Stable transition errors the oracle may return. Listed so a caller can
#: recognise a verdict without re-deriving the oracle's rules.
TRANSITION_ERRORS = (
    "run_sealed", "attempt_exists", "operation_payload_conflict",
    "request_missing", "outcome_exists", "unsupported_evidence",
    "commit_payload_conflict", "commit_unconfirmed", "incomplete_coverage",
    "malformed_input",
)


class TraceError(ValueError):
    """An event could not be built or is not well shaped."""


class UnsupportedEvidence(TraceError):
    """A citation was attempted without the recorded success behind it."""


def _nat(value: object, name: str) -> int:
    """Require a natural number: the oracle's identifiers are ``Nat``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TraceError(f"{name} must be a non-negative integer, got {value!r}")
    if value < 0:
        raise TraceError(f"{name} must be non-negative, got {value}")
    return value


def dispatch(*, run: int, operation: int, attempt: int, payload: int) -> dict[str, Any]:
    """A request was registered. Must precede its outcome."""
    return {
        "kind": "dispatch",
        "run": _nat(run, "run"),
        "operation": _nat(operation, "operation"),
        "attempt": _nat(attempt, "attempt"),
        "payload": _nat(payload, "payload"),
    }


def succeed(*, run: int, attempt: int, artifact: int) -> dict[str, Any]:
    """A registered attempt produced an artifact."""
    return {
        "kind": "succeed",
        "run": _nat(run, "run"),
        "attempt": _nat(attempt, "attempt"),
        "artifact": _nat(artifact, "artifact"),
    }


def fail(*, run: int, attempt: int) -> dict[str, Any]:
    """A registered attempt definitively failed."""
    return {"kind": "fail", "run": _nat(run, "run"), "attempt": _nat(attempt, "attempt")}


def timeout(*, run: int, attempt: int) -> dict[str, Any]:
    """A registered attempt did not return. This is uncertainty, not failure.

    The oracle stores timeouts separately from outcomes and permits a late
    success to resolve one before the run is sealed.
    """
    return {"kind": "timeout", "run": _nat(run, "run"), "attempt": _nat(attempt, "attempt")}


def cite(*, derived_from: Mapping[str, Any]) -> dict[str, Any]:
    """Admit observed evidence, derived from the success that supports it.

    There is no way to pass a run, attempt, and artifact directly: they are
    copied from the ``succeed`` event handed in. A mention with no recorded
    success therefore cannot become a citation through this function.

    Raises:
        UnsupportedEvidence: if ``derived_from`` is not a ``succeed`` event.
    """
    if not isinstance(derived_from, Mapping) or derived_from.get("kind") != "succeed":
        raise UnsupportedEvidence(
            "a citation must be derived from a recorded 'succeed' event; an "
            "unsupported source mention stays in the attempt record and never "
            "becomes observed evidence"
        )
    validate_event(derived_from)
    return {
        "kind": "cite",
        "run": derived_from["run"],
        "attempt": derived_from["attempt"],
        "artifact": derived_from["artifact"],
    }


def commit(*, run: int, operation: int, payload: int) -> dict[str, Any]:
    """Record one simulated ledger entry. Not an external effect of any kind."""
    return {
        "kind": "commit",
        "run": _nat(run, "run"),
        "operation": _nat(operation, "operation"),
        "payload": _nat(payload, "payload"),
    }


def finalize(*, run: int, complete: bool) -> dict[str, Any]:
    """Seal a run. ``complete=True`` additionally asserts coverage.

    Coverage is not task success: a fully recorded failure is covered, and an
    empty run is vacuously covered.
    """
    if not isinstance(complete, bool):
        raise TraceError(f"complete must be a boolean, got {complete!r}")
    return {"kind": "finalize", "run": _nat(run, "run"), "complete": complete}


def validate_event(event: object) -> dict[str, Any]:
    """Check one event's kind and exact field set. Returns it unchanged.

    Raises:
        TraceError: on an unknown kind, a missing field, an extra field, or an
            identifier that is not a natural number.
    """
    if not isinstance(event, Mapping):
        raise TraceError(f"event must be a mapping, got {type(event).__name__}")
    kind = event.get("kind")
    if kind not in EVENT_FIELDS:
        raise TraceError(
            f"unknown event kind {kind!r}; expected one of "
            f"{', '.join(sorted(EVENT_FIELDS))}"
        )
    expected = set(EVENT_FIELDS[kind]) | {"kind"}
    present = set(event)
    missing = sorted(expected - present)
    extra = sorted(present - expected)
    if missing:
        raise TraceError(f"{kind}: missing field(s) {', '.join(missing)}")
    if extra:
        raise TraceError(f"{kind}: unknown field(s) {', '.join(extra)}")
    for name in EVENT_FIELDS[kind]:
        if name == "complete":
            if not isinstance(event[name], bool):
                raise TraceError(f"{kind}: complete must be a boolean")
        else:
            _nat(event[name], f"{kind}.{name}")
    return dict(event)


def document(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the oracle's input document, validating every event."""
    return {"events": [validate_event(event) for event in events]}


def write_document(path: str | Path, events: Iterable[Mapping[str, Any]]) -> Path:
    """Write a trace document the oracle binary can read on standard input."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document(events), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


@dataclass
class IdSpace:
    """Interns the application's string identifiers as the oracle's integers.

    The oracle reasons about natural numbers; the application uses readable
    ids like ``campus-transport:framing:0``. This assigns each string a stable
    integer per namespace, in first-seen order, and keeps the mapping so an
    emitted trace stays interpretable. The oracle's README is explicit that
    such identifiers are not attestations: the mapping records what was named,
    not that the name was truthful.
    """

    namespaces: dict[str, dict[str, int]] = field(default_factory=dict)

    def intern(self, namespace: str, key: str) -> int:
        """Return the integer for ``key``, assigning the next one if new."""
        if not namespace.strip() or not key.strip():
            raise TraceError("namespace and key must be non-empty")
        table = self.namespaces.setdefault(namespace, {})
        if key not in table:
            table[key] = len(table)
        return table[key]

    def mapping(self) -> dict[str, dict[str, int]]:
        """The full assignment, for export alongside a trace."""
        return {name: dict(table) for name, table in sorted(self.namespaces.items())}


__all__ = [
    "ORACLE_CONFORMANCE", "EVENT_FIELDS", "TRANSITION_ERRORS",
    "TraceError", "UnsupportedEvidence",
    "dispatch", "succeed", "fail", "timeout", "cite", "commit", "finalize",
    "validate_event", "document", "write_document", "IdSpace",
]
