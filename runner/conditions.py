"""The condition arms, and which of them a framing-only comparison may use.

docs/evaluation.md requires matched cases: a baseline, unchanged reruns, a
neutral edit of comparable length, a framing change, and a *separately
labelled* correction arm. Two of those exist mainly to keep the comparison
honest rather than to produce a headline:

Unchanged rerun
    Shows baseline variability. If reruns of identical input already change
    the recommendation, a framing "effect" of the same size means nothing.

Neutral edit
    A length-matched rewrite that changes no facts. If a rewrite does change
    facts or accessibility requirements it is *confounded* and must leave the
    framing-only comparison instead of quietly widening it.

The correction arm deliberately changes decision-relevant evidence, so it is
never eligible for a framing-only comparison. That is not a defect: it is the
distinction docs/evaluation.md demands when a correction removes legitimate
source authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class Arm(str, Enum):
    """The five matched conditions."""

    BASELINE = "baseline"
    UNCHANGED_RERUN = "unchanged_rerun"
    NEUTRAL_EDIT = "neutral_edit"
    FRAMING = "framing"
    CORRECTION = "correction"


#: Deterministic order used by :func:`expand`. Fixed so two expansions of the
#: same case are comparable and so an export's column order is stable.
ARM_ORDER = (
    Arm.BASELINE,
    Arm.UNCHANGED_RERUN,
    Arm.NEUTRAL_EDIT,
    Arm.FRAMING,
    Arm.CORRECTION,
)

#: Arms that change decision-relevant evidence by design.
EVIDENCE_CHANGING = frozenset({Arm.CORRECTION})

#: Arms a framing-only comparison reads, when neither confounded nor
#: evidence-changing. The baseline is the reference; the framing arm is the
#: contrast. The others inform interpretation without entering the contrast.
FRAMING_ONLY_ARMS = frozenset({Arm.BASELINE, Arm.FRAMING})


@dataclass(frozen=True)
class Condition:
    """One arm of one case, at one rerun index."""

    case_id: str
    arm: Arm
    index: int
    confounded: bool = False
    confound_reason: str | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"rerun index must be non-negative, got {self.index}")
        if self.confounded and not self.confound_reason:
            raise ValueError(
                "a confounded condition must record why; an unexplained "
                "exclusion is indistinguishable from dropping inconvenient data"
            )
        if self.confound_reason and not self.confounded:
            raise ValueError("confound_reason set without confounded=True")

    @property
    def id(self) -> str:
        """Stable identifier, used as the trace operation key and in exports."""
        return f"{self.case_id}:{self.arm.value}:{self.index}"

    @property
    def changes_evidence(self) -> bool:
        """True when this arm alters decision-relevant evidence.

        A confounded edit counts: the whole point of flagging it is that its
        evidence no longer matches the baseline's.
        """
        return self.arm in EVIDENCE_CHANGING or self.confounded

    @property
    def framing_only_eligible(self) -> bool:
        """True when a framing-only comparison may read this condition."""
        return self.arm in FRAMING_ONLY_ARMS and not self.changes_evidence

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "arm": self.arm.value,
            "index": self.index,
            "confounded": self.confounded,
            "confound_reason": self.confound_reason,
            "changes_evidence": self.changes_evidence,
            "framing_only_eligible": self.framing_only_eligible,
        }


def expand(case_id: str, *, reruns: int = 1) -> tuple[Condition, ...]:
    """Build the full matched set for one case, in :data:`ARM_ORDER`.

    ``reruns`` replicates every arm, not just the rerun arm: baseline
    variability is only interpretable against equally replicated contrasts.
    The result is deterministic, so repeated expansion is comparable.

    Raises:
        ValueError: if ``reruns`` is below 1, which would silently drop arms.
    """
    if reruns < 1:
        raise ValueError(f"reruns must be at least 1, got {reruns}")
    if not case_id.strip():
        raise ValueError("case_id must not be empty")
    return tuple(
        Condition(case_id=case_id, arm=arm, index=index)
        for arm in ARM_ORDER
        for index in range(reruns)
    )


def mark_confounded(condition: Condition, reason: str) -> Condition:
    """Return a copy excluded from the framing-only comparison, with a reason.

    Use this when a rewrite turns out to change facts or accessibility
    requirements. The original condition is unchanged; the record keeps both.
    """
    if not reason.strip():
        raise ValueError("a confound must be explained")
    return replace(condition, confounded=True, confound_reason=reason)


def framing_only(conditions: tuple[Condition, ...]) -> tuple[Condition, ...]:
    """Filter to the conditions a framing-only comparison may read."""
    return tuple(c for c in conditions if c.framing_only_eligible)


__all__ = [
    "Arm", "ARM_ORDER", "EVIDENCE_CHANGING", "FRAMING_ONLY_ARMS",
    "Condition", "expand", "mark_confounded", "framing_only",
]
