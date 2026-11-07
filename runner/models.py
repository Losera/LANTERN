"""Model provenance (implemented) and the model adapter (a seam).

docs/alpha.md draws a line this module enforces in data: "Running an API-backed
coding CLI on Alpha does not move provider inference to Alpha", and a permitted
local or API fallback "is not an Alpha run". So :class:`Provenance` requires an
``execution_site`` and offers no default for it -- a record cannot omit where
it actually ran and later be presented as an Alpha result.

Every other provenance field defaults to :data:`runner.unknown.UNKNOWN`
rather than to a plausible value. docs/evaluation.md requires that any missing
value stay explicitly unknown, and a recorded ``seed: 0`` that nobody set is
worse than a recorded gap.

The adapter is a seam: docs/project.md lists the model and revision, the
environment, and the generation settings among the decisions the lead must
approve before implementation, and docs/alpha.md warns against downloading a
candidate model merely because it appears in a note.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Protocol

from runner.unknown import UNKNOWN, Unknown


class ExecutionSite(str, Enum):
    """Where inference actually happened.

    ``UNKNOWN`` exists so an imported record with unclear provenance can be
    stored honestly. It must never be used for a run whose site is known.
    """

    ALPHA_BATCH = "alpha_batch"
    ALPHA_ENDPOINT = "alpha_endpoint"
    LOCAL = "local"
    API = "api"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Provenance:
    """Everything needed to say what produced one attempt.

    The field list follows docs/evaluation.md "Retain evidence for every
    attempt": revision, harness and version, generation settings and seed where
    supported, runtime, and usage where available.
    """

    execution_site: ExecutionSite
    model_id: str | Unknown = UNKNOWN
    model_revision: str | Unknown = UNKNOWN
    model_license: str | Unknown = UNKNOWN
    harness: str | Unknown = UNKNOWN
    harness_version: str | Unknown = UNKNOWN
    dtype: str | Unknown = UNKNOWN
    context_limit: int | Unknown = UNKNOWN
    max_new_tokens: int | Unknown = UNKNOWN
    temperature: float | Unknown = UNKNOWN
    top_p: float | Unknown = UNKNOWN
    seed: int | Unknown = UNKNOWN
    started_utc: str | Unknown = UNKNOWN
    finished_utc: str | Unknown = UNKNOWN
    runtime_seconds: float | Unknown = UNKNOWN
    prompt_tokens: int | Unknown = UNKNOWN
    completion_tokens: int | Unknown = UNKNOWN
    peak_memory_bytes: int | Unknown = UNKNOWN

    def unknown_fields(self) -> tuple[str, ...]:
        """Names of every field whose value is genuinely unknown."""
        return tuple(
            f.name for f in fields(self)
            if isinstance(getattr(self, f.name), Unknown)
        )

    @property
    def is_alpha(self) -> bool:
        """True only for execution that actually happened on Alpha."""
        return self.execution_site in {
            ExecutionSite.ALPHA_BATCH, ExecutionSite.ALPHA_ENDPOINT,
        }


@dataclass(frozen=True)
class PromptPayload:
    """Exactly what was sent, plus a digest to tie a record to that text."""

    text: str
    sha256: str
    evidence_order: tuple[str, ...]


@dataclass(frozen=True)
class RawOutput:
    """Exactly what came back, before any interpretation."""

    text: str
    provenance: Provenance
    truncated_by_limit: bool = False


class ModelAdapter(Protocol):
    """The one boundary the runner crosses to reach a model."""

    name: str

    def generate(self, payload: PromptPayload) -> RawOutput:
        """Execute one attempt and return its raw output with provenance."""
        ...


@dataclass
class UnapprovedAdapter:
    """SEAM: stands in for every model backend until one is approved.

    Deliberately a working object with a failing method. Code and tests can be
    written against the boundary now; the first real run cannot happen by
    accident, and nothing in the pipeline receives invented output.
    """

    name: str = "unapproved"

    def generate(self, payload: PromptPayload) -> RawOutput:
        """Raises:
            NotImplementedError: always.
        """
        raise NotImplementedError(
            f"model adapter {self.name!r} is a seam: no model, revision, "
            "environment, or generation setting is approved. See "
            "docs/project.md 'Decisions still required' and docs/alpha.md "
            "'Inference and experiment gates'."
        )


__all__ = [
    "ExecutionSite", "Provenance", "PromptPayload", "RawOutput",
    "ModelAdapter", "UnapprovedAdapter",
]
