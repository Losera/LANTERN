"""Model provenance and the approved local Ollama adapter.

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
from datetime import datetime, timezone
from enum import Enum
import json
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from runner.outcomes import Outcome
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


class AdapterExecutionError(RuntimeError):
    """A failed inference with any received body and measured provenance.

    The recording boundary can use ``raw_output`` and ``provenance`` to write
    an ``Outcome.ERROR`` attempt, or ``Outcome.TIMEOUT`` when ``timed_out`` is
    true. ``UNKNOWN`` means no response body or required measurement exists.
    """

    outcome = Outcome.ERROR

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | Unknown = UNKNOWN,
        provenance: Provenance | Unknown = UNKNOWN,
        timed_out: bool = False,
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.provenance = provenance
        self.timed_out = timed_out


@dataclass
class UnapprovedAdapter:
    """The approved Qwen2.5 Ollama adapter for the local fallback.

    The model, quantization, and generation settings are fixed by issue #15.
    The daemon version is queried for each attempt so a record describes the
    runtime that served it rather than the local CLI version.
    """

    name: str = "ollama"
    timeout_seconds: float = 300.0

    BASE_URL = "http://127.0.0.1:11434"
    MODEL_ID = "qwen2.5:1.5b-instruct"
    MODEL_REVISION = "65ec06548149"
    MODEL_LICENSE = "Apache"
    DTYPE = "Q4_K_M/GGUF"
    CONTEXT_LIMIT = 4096
    MAX_NEW_TOKENS = 512
    TEMPERATURE = 0.0
    TOP_P = 1.0
    SEED = 1

    #: JSON schema sent as Ollama's ``format``, constraining generation to the
    #: approved response contract. docs/evaluation.md treats fences,
    #: surrounding prose, and missing or extra fields as ``malformed`` and
    #: forbids extracting or repairing candidate JSON, so an unconstrained
    #: instruct model would very likely produce nothing readable. This makes
    #: the shape a decoding constraint rather than a request the model may
    #: decline. It constrains shape only: no option, evidence id, or wording is
    #: suggested, so it cannot bias which recommendation is chosen.
    #:
    #: The field names must stay identical to the set
    #: :func:`runner.parsing.parse` requires; the offline lane checks that they
    #: do, because the two are the same contract written in two places.
    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "option_id": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string"},
        },
        "required": ["option_id", "evidence_ids", "explanation"],
        "additionalProperties": False,
    }

    def _request(self, path: str, body: dict[str, object] | None = None) -> bytes:
        """Make one bounded request and retain HTTP error bodies for callers."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.BASE_URL.rstrip('/')}{path}",
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method="GET" if data is None else "POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            raw = exc.read()
            raise AdapterExecutionError(
                f"Ollama {path} returned HTTP {exc.code}", raw_output=raw.decode(
                    "utf-8", errors="replace"),
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise AdapterExecutionError(
                f"Ollama {path} request failed: {exc}",
                timed_out=(
                    isinstance(exc, TimeoutError)
                    or isinstance(exc, URLError)
                    and isinstance(exc.reason, TimeoutError)
                ),
            ) from exc

    def generate(self, payload: PromptPayload) -> RawOutput:
        """Generate once and return the raw response with observed provenance.

        Transport and API-declared generation failures raise
        :class:`AdapterExecutionError`; its raw response and provenance let a
        runner record an ``Outcome.ERROR`` without treating an error as an
        answer. A daemon-version preflight failure raises before generation.
        """
        started = datetime.now(timezone.utc)
        monotonic_start = time.monotonic()

        try:
            version_document = json.loads(self._request("/api/version"))
            harness_version = version_document["version"]
            if not isinstance(harness_version, str) or not harness_version.strip():
                raise ValueError("Ollama /api/version returned no version string")
        except AdapterExecutionError:
            raise
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AdapterExecutionError(
                f"could not read Ollama daemon version: {exc}",
            ) from exc

        provenance_values: dict[str, object] = {
            "execution_site": ExecutionSite.LOCAL,
            "model_id": self.MODEL_ID,
            "model_revision": self.MODEL_REVISION,
            "model_license": self.MODEL_LICENSE,
            "harness": "ollama",
            "harness_version": harness_version,
            "dtype": self.DTYPE,
            "context_limit": self.CONTEXT_LIMIT,
            "max_new_tokens": self.MAX_NEW_TOKENS,
            "temperature": self.TEMPERATURE,
            "top_p": self.TOP_P,
            "seed": self.SEED,
            "started_utc": started.isoformat(),
        }

        try:
            response_bytes = self._request("/api/generate", {
                "model": self.MODEL_ID,
                "prompt": payload.text,
                "stream": False,
                "format": self.RESPONSE_SCHEMA,
                "options": {
                    "temperature": self.TEMPERATURE,
                    "top_p": self.TOP_P,
                    "seed": self.SEED,
                    "num_predict": self.MAX_NEW_TOKENS,
                    "num_ctx": self.CONTEXT_LIMIT,
                },
            })
            response = json.loads(response_bytes)
            if not isinstance(response, dict):
                raise ValueError("Ollama response was not a JSON object")
            api_error = response.get("error")
            if api_error:
                raise AdapterExecutionError(
                    f"Ollama generation failed: {api_error}",
                    raw_output=response_bytes.decode("utf-8", errors="replace"),
                    provenance=self._provenance(
                        provenance_values, response, monotonic_start),
                )
            raw_text = response.get("response")
            if not isinstance(raw_text, str):
                raise ValueError("Ollama response did not contain text")
            done_reason = response.get("done_reason")
            if done_reason not in {"stop", "length"}:
                raise ValueError(
                    f"Ollama response returned an unrecognized done reason: "
                    f"{done_reason!r}"
                )
        except AdapterExecutionError as exc:
            if isinstance(exc.provenance, Unknown):
                exc.provenance = self._provenance(
                    provenance_values, {}, monotonic_start)
            raise
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AdapterExecutionError(
                f"could not decode Ollama generation response: {exc}",
                raw_output=response_bytes.decode("utf-8", errors="replace"),
                provenance=self._provenance(
                    provenance_values, {}, monotonic_start),
            ) from exc

        provenance = self._provenance(
            provenance_values, response, monotonic_start)
        return RawOutput(
            text=raw_text,
            provenance=provenance,
            truncated_by_limit=done_reason == "length",
        )

    @staticmethod
    def _provenance(
        values: dict[str, object],
        response: dict[str, object],
        monotonic_start: float,
    ) -> Provenance:
        """Build provenance from approved settings and fields actually seen."""
        finished = datetime.now(timezone.utc)
        elapsed = max(0.0, time.monotonic() - monotonic_start)
        total_ns = response.get("total_duration")
        runtime_seconds = (
            total_ns / 1_000_000_000
            if isinstance(total_ns, (int, float)) and not isinstance(total_ns, bool)
            else elapsed
        )
        for source, target in (
            ("prompt_eval_count", "prompt_tokens"),
            ("eval_count", "completion_tokens"),
        ):
            count = response.get(source)
            values[target] = (
                count if isinstance(count, int) and not isinstance(count, bool)
                else UNKNOWN
            )
        values.update({
            "finished_utc": finished.isoformat(),
            "runtime_seconds": runtime_seconds,
        })
        return Provenance(**values)


__all__ = [
    "ExecutionSite", "Provenance", "PromptPayload", "RawOutput",
    "ModelAdapter", "UnapprovedAdapter", "AdapterExecutionError",
]
