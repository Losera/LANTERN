"""Case documents: the frozen evidence packet, options, and rubric reference.

A case is the thing held fixed across conditions. docs/evaluation.md requires
that relevant authority differences be declared *in advance*, because relying
on a reliable source can be entirely rational -- so every evidence item must
state whether it is decision-relevant, and the loader refuses a packet that
leaves that implicit.

Structural validation is implemented: it is deterministic and needs no
approval. Interpreting a rubric is not, and lives behind the parsing seam.
The format itself is PROPOSED at ``schema_version`` 0; see docs/contracts.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from runner import SCHEMA_VERSION


class CaseError(ValueError):
    """A case document is structurally unusable. The path and field are named."""


@dataclass(frozen=True)
class Option:
    """One selectable recommendation."""

    id: str
    label: str


@dataclass(frozen=True)
class EvidenceItem:
    """One piece of evidence, with its provenance preserved.

    ``source_authority`` is retained rather than stripped. docs/evaluation.md
    is explicit that reliability information must not be removed merely to
    force unchanged answers, and that a correction which removes legitimate
    source authority is itself a change to decision-relevant evidence.
    """

    id: str
    claim: str
    source: str
    source_authority: str
    relevant: bool


@dataclass(frozen=True)
class Rubric:
    """A reference to the agreed decision rule, plus its requirements.

    This records *which* rubric a case was judged under so an export can be
    read later. It does not implement the rule.
    """

    id: str
    requirements: tuple[str, ...]

@dataclass(frozen=True)
class Cue:
    """A case-level presentation or context cue with declared relevance."""

    id: str
    cue: str
    relevant: bool

@dataclass(frozen=True)
class Case:
    """A complete, fixed decision problem."""

    id: str
    question: str
    options: tuple[Option, ...]
    evidence: tuple[EvidenceItem, ...]
    cues: tuple[Cue, ...]
    rubric: Rubric
    status: str
    schema_version: int = SCHEMA_VERSION

    def evidence_by_id(self, evidence_id: str) -> EvidenceItem | None:
        for item in self.evidence:
            if item.id == evidence_id:
                return item
        return None

    @property
    def relevant_evidence(self) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.evidence if item.relevant)

    @property
    def irrelevant_evidence(self) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.evidence if not item.relevant)
        
    @property
    def relevant_cues(self) -> tuple[Cue, ...]:
        return tuple(item for item in self.cues if item.relevant)
        
    @property
    def irrelevant_cues(self) -> tuple[Cue, ...]:
        return tuple(item for item in self.cues if not item.relevant)


def _require(data: dict, key: str, kind: type, where: str):
    if key not in data:
        raise CaseError(f"{where}: missing required field {key!r}")
    value = data[key]
    # bool is a subclass of int, so an int field must reject True explicitly.
    if kind is int and isinstance(value, bool):
        raise CaseError(f"{where}: field {key!r} must be {kind.__name__}, got bool")
    if not isinstance(value, kind):
        raise CaseError(
            f"{where}: field {key!r} must be {kind.__name__}, "
            f"got {type(value).__name__}"
        )
    if kind is str and not value.strip():
        raise CaseError(f"{where}: field {key!r} must not be empty")
    return value


def _exact_keys(data: dict, allowed: set[str], where: str) -> None:
    """Reject unknown keys, following the oracle's strict-field discipline.

    Lantern/Wire.lean rejects unknown fields so a misspelled safety-relevant
    field cannot be silently ignored. The same risk applies to a case packet:
    ``relevent: false`` must fail loudly rather than default to relevant.
    """
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise CaseError(f"{where}: unknown field(s) {', '.join(repr(k) for k in unknown)}")


def validate_case(data: object, *, where: str = "case") -> Case:
    """Validate a decoded case document and build a :class:`Case`.

    Raises:
        CaseError: on any structural problem, naming the offending field.
    """
    if not isinstance(data, dict):
        raise CaseError(f"{where}: document must be a JSON object")
    _exact_keys(
        data,
        {
            "schema_version", "id", "status", "question", "options",
            "evidence", "cues", "rubric",
        },
        where,
    )

    version = _require(data, "schema_version", int, where)
    if version != SCHEMA_VERSION:
        raise CaseError(
            f"{where}: schema_version {version} is not the supported "
            f"version {SCHEMA_VERSION}"
        )

    case_id = _require(data, "id", str, where)
    status = _require(data, "status", str, where)
    question = _require(data, "question", str, where)
    
    #UPDATE WITH HELP
    raw_options = _require(data, "options", list, where)
    if len(raw_options) < 2:
        raise CaseError(f"{where}: a decision needs at least two options")
    options: list[Option] = []
    for index, raw in enumerate(raw_options):
        spot = f"{where}.options[{index}]"
        if not isinstance(raw, dict):
            raise CaseError(f"{spot}: must be an object")
        _exact_keys(raw, {"id", "label"}, spot)
        options.append(Option(_require(raw, "id", str, spot), _require(raw, "label", str, spot)))
    _reject_duplicates([o.id for o in options], f"{where}.options", "id")
    
    #UPDATE WITH HELP
    raw_evidence = _require(data, "evidence", list, where)
    if not raw_evidence:
        raise CaseError(f"{where}: evidence packet must not be empty")
    evidence: list[EvidenceItem] = []
    for index, raw in enumerate(raw_evidence):
        spot = f"{where}.evidence[{index}]"
        if not isinstance(raw, dict):
            raise CaseError(f"{spot}: must be an object")
        _exact_keys(raw, {"id", "claim", "source", "source_authority", "relevant"}, spot)
        relevant = raw.get("relevant")
        if not isinstance(relevant, bool):
            raise CaseError(
                f"{spot}: 'relevant' must be declared as a boolean in advance; "
                "see docs/evaluation.md"
            )
        evidence.append(EvidenceItem(
            id=_require(raw, "id", str, spot),
            claim=_require(raw, "claim", str, spot),
            source=_require(raw, "source", str, spot),
            source_authority=_require(raw, "source_authority", str, spot),
            relevant=relevant,
        ))
    _reject_duplicates([item.id for item in evidence], f"{where}.evidence", "id")

    raw_cues = _require(data, "cues", list, where)
    cues: list[Cue] = []
    for index, raw in enumerate(raw_cues):
        spot = f"{where}.cues[{index}]"
        if not isinstance(raw, dict):
            raise CaseError(f"{spot}: must be an object")
        _exact_keys(raw, {"id", "cue", "relevant"}, spot)
        relevant = raw.get("relevant")
        if not isinstance(relevant, bool):
            raise CaseError(
                f"{spot}: 'relevant' must be declared as a boolean in advance; "
                "see docs/evaluation.md"
            )
        cues.append(Cue(
            id=_require(raw, "id", str, spot),
            cue=_require(raw, "cue", str, spot),
            relevant=relevant,
        ))
    _reject_duplicates([item.id for item in cues], f"{where}.cues", "id")
    
    #UPDATE WITH HELP
    raw_rubric = _require(data, "rubric", dict, where)
    spot = f"{where}.rubric"
    _exact_keys(raw_rubric, {"id", "requirements"}, spot)
    requirements = _require(raw_rubric, "requirements", list, spot)
    if not requirements:
        raise CaseError(f"{spot}: a rubric must state at least one requirement")
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, str) or not requirement.strip():
            raise CaseError(f"{spot}.requirements[{index}]: must be a non-empty string")
    rubric = Rubric(_require(raw_rubric, "id", str, spot), tuple(requirements))

    return Case(
        id=case_id,
        question=question,
        options=tuple(options),
        evidence=tuple(evidence),
        cues=tuple(cues),
        rubric=rubric,
        status=status,
        schema_version=version,
    )


def _reject_duplicates(values: list[str], where: str, field_name: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise CaseError(f"{where}: duplicate {field_name} {value!r}")
        seen.add(value)


def load_case(path: str | Path) -> Case:
    """Read and validate one case document from disk."""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CaseError(f"{path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CaseError(f"{path}: invalid JSON: {exc}") from exc
    return validate_case(data, where=str(path))


def load_cases(directory: str | Path) -> tuple[Case, ...]:
    """Read every ``*.json`` case in a directory, sorted by filename."""
    directory = Path(directory)
    cases = tuple(load_case(path) for path in sorted(directory.glob("*.json")))
    _reject_duplicates([case.id for case in cases], str(directory), "case id")
    return cases


__all__ = [
    "CaseError", "Option", "EvidenceItem", "Cue", "Rubric", "Case",
    "validate_case", "load_case", "load_cases",
]
