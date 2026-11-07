"""Paired comparison and counting, with the denominators the policy requires.

This is where a comparison can most easily flatter itself, so the rules are
stated as code rather than as convention:

Denominators include every attempt
    ``attempts`` counts all records. docs/evaluation.md: "Count all attempted
    runs in completion denominators." Failures are reported in their own
    buckets and never removed from the total.

A timeout is neither a flip nor stability
    An unresolved attempt yields :attr:`Verdict.UNRESOLVED`. docs/evaluation.md
    requires that a model which times out instead of resisting a cue be counted
    separately, "never as resistance to bias".

Coverage is not task success
    Coverage asks whether every registered attempt reached a definitive
    outcome. A fully recorded failure is covered; an empty run is vacuously
    covered. The Lean oracle proves the same separation and its README insists
    the UI keep them apart.

A null result is a result
    When every readable pair agrees, the effect is ``none_measured`` and the
    comparison is still complete. docs/project.md: "A useful comparison must
    remain useful when the experiment finds no effect."

Nothing here infers causality, fairness, or a reason for a flip. A flip is an
observed difference between two recorded choices, and that is all.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from runner.conditions import Arm, Condition
from runner.outcomes import FAILURES, Outcome, UNRESOLVED, is_definitive, is_usable


class Verdict(str, Enum):
    """The result of comparing one case's baseline against one contrast."""

    FLIP = "flip"
    STABLE = "stable"
    UNRESOLVED = "unresolved"


class Effect(str, Enum):
    """What the framing-only comparison supports overall."""

    MEASURED = "measured"
    NONE_MEASURED = "none_measured"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class ArmSummary:
    """Counts for one arm. ``attempts`` is the denominator for the rest."""

    arm: Arm
    attempts: int
    decisions: int
    unresolved: int
    failures: dict[str, int] = field(default_factory=dict)

    @property
    def failure_total(self) -> int:
        return sum(self.failures.values())

    def as_dict(self) -> dict[str, object]:
        return {
            "arm": self.arm.value,
            "attempts": self.attempts,
            "decisions": self.decisions,
            "unresolved": self.unresolved,
            "failures": dict(sorted(self.failures.items())),
            "failure_total": self.failure_total,
        }


@dataclass(frozen=True)
class Coverage:
    """Whether every registered attempt in a run reached a definitive outcome."""

    run_id: str
    registered: int
    definitive: int
    pending: tuple[str, ...]

    @property
    def covered(self) -> bool:
        """An empty run is vacuously covered, matching the oracle."""
        return not self.pending

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "registered": self.registered,
            "definitive": self.definitive,
            "pending": list(self.pending),
            "covered": self.covered,
        }


@dataclass(frozen=True)
class Pair:
    """One baseline-versus-contrast comparison for one case."""

    case_id: str
    contrast_arm: Arm
    baseline_option: str | None
    contrast_option: str | None
    verdict: Verdict
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "contrast_arm": self.contrast_arm.value,
            "baseline_option": self.baseline_option,
            "contrast_option": self.contrast_option,
            "verdict": self.verdict.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Analysis:
    """The whole comparison, including what it could not establish."""

    attempts: int
    arms: tuple[ArmSummary, ...]
    coverage: tuple[Coverage, ...]
    framing_pairs: tuple[Pair, ...]
    correction_pairs: tuple[Pair, ...]
    excluded: tuple[dict[str, object], ...]
    effect: Effect
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        flips = sum(1 for p in self.framing_pairs if p.verdict is Verdict.FLIP)
        stable = sum(1 for p in self.framing_pairs if p.verdict is Verdict.STABLE)
        unresolved = sum(1 for p in self.framing_pairs if p.verdict is Verdict.UNRESOLVED)
        return {
            "attempts": self.attempts,
            "arms": [a.as_dict() for a in self.arms],
            "coverage": [c.as_dict() for c in self.coverage],
            "framing_pairs": [p.as_dict() for p in self.framing_pairs],
            "correction_pairs": [p.as_dict() for p in self.correction_pairs],
            "excluded": [dict(e) for e in self.excluded],
            "effect": self.effect.value,
            "framing_counts": {
                "pairs": len(self.framing_pairs),
                "flip": flips,
                "stable": stable,
                "unresolved": unresolved,
            },
            "notes": list(self.notes),
        }


def _record_arm(record: dict) -> Arm:
    try:
        return Arm(record["arm"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"record has no usable arm: {record.get('arm')!r}") from exc


def _record_outcome(record: dict) -> Outcome:
    try:
        return Outcome(record["outcome"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"record has no usable outcome: {record.get('outcome')!r}") from exc


def _usable_choice(records: list[dict]) -> tuple[str | None, str]:
    """The single readable choice among an arm's records for one case.

    Returns the choice and a reason. Disagreeing readable choices within one
    arm are *not* averaged or majority-voted: that would hide the variability
    the rerun arm exists to expose, so the pair is left unresolved.
    """
    readable = [r for r in records if is_usable(_record_outcome(r))]
    if not readable:
        if not records:
            return None, "no attempt recorded"
        kinds = sorted({_record_outcome(r).value for r in records})
        return None, f"no readable decision ({', '.join(kinds)})"
    options = sorted({str(r.get("option_id")) for r in readable})
    if len(options) > 1:
        return None, f"readable decisions disagree within the arm ({', '.join(options)})"
    return options[0], "readable"


def _pair(case_id: str, arm: Arm, baseline: list[dict], contrast: list[dict]) -> Pair:
    base_option, base_reason = _usable_choice(baseline)
    contrast_option, contrast_reason = _usable_choice(contrast)
    if base_option is None or contrast_option is None:
        side = "baseline" if base_option is None else arm.value
        reason = base_reason if base_option is None else contrast_reason
        return Pair(
            case_id=case_id,
            contrast_arm=arm,
            baseline_option=base_option,
            contrast_option=contrast_option,
            verdict=Verdict.UNRESOLVED,
            reason=f"{side}: {reason}",
        )
    flipped = base_option != contrast_option
    return Pair(
        case_id=case_id,
        contrast_arm=arm,
        baseline_option=base_option,
        contrast_option=contrast_option,
        verdict=Verdict.FLIP if flipped else Verdict.STABLE,
        reason="observed difference between recorded choices" if flipped
        else "recorded choices agree",
    )


def summarize(
    records: list[dict] | tuple[dict, ...],
    conditions: tuple[Condition, ...] = (),
) -> Analysis:
    """Build the full comparison from attempt records.

    ``conditions`` supplies confound flags. A condition marked confounded is
    excluded from the framing-only comparison and listed in ``excluded`` with
    its stated reason, so an exclusion is always visible and explained.
    """
    records = list(records)
    by_condition = {c.id: c for c in conditions}

    arm_records: dict[Arm, list[dict]] = {arm: [] for arm in Arm}
    excluded: list[dict[str, object]] = []
    for record in records:
        arm = _record_arm(record)
        arm_records[arm].append(record)

    arms: list[ArmSummary] = []
    for arm in Arm:
        rows = arm_records[arm]
        failures = Counter(
            _record_outcome(r).value for r in rows if _record_outcome(r) in FAILURES
        )
        arms.append(ArmSummary(
            arm=arm,
            attempts=len(rows),
            decisions=sum(1 for r in rows if is_usable(_record_outcome(r))),
            unresolved=sum(1 for r in rows if _record_outcome(r) in UNRESOLVED),
            failures=dict(failures),
        ))

    coverage: list[Coverage] = []
    runs: dict[str, list[dict]] = {}
    for record in records:
        runs.setdefault(str(record.get("run_id", "")), []).append(record)
    for run_id, rows in sorted(runs.items()):
        pending = tuple(
            str(r.get("attempt_id"))
            for r in rows
            if not is_definitive(_record_outcome(r))
        )
        coverage.append(Coverage(
            run_id=run_id,
            registered=len(rows),
            definitive=len(rows) - len(pending),
            pending=pending,
        ))

    def rows_for(case_id: str, arm: Arm, *, framing_only: bool) -> list[dict]:
        kept: list[dict] = []
        for record in arm_records[arm]:
            if str(record.get("case_id")) != case_id:
                continue
            condition = by_condition.get(str(record.get("condition_id")))
            if framing_only and condition is not None and not condition.framing_only_eligible:
                excluded.append({
                    "condition_id": condition.id,
                    "arm": condition.arm.value,
                    "reason": condition.confound_reason or
                    "arm changes decision-relevant evidence by design",
                })
                continue
            kept.append(record)
        return kept

    case_ids = sorted({str(r.get("case_id")) for r in records})
    framing_pairs: list[Pair] = []
    correction_pairs: list[Pair] = []
    for case_id in case_ids:
        baseline = rows_for(case_id, Arm.BASELINE, framing_only=True)
        framing = rows_for(case_id, Arm.FRAMING, framing_only=True)
        if baseline or framing:
            framing_pairs.append(_pair(case_id, Arm.FRAMING, baseline, framing))
        correction = rows_for(case_id, Arm.CORRECTION, framing_only=False)
        if correction:
            correction_pairs.append(
                _pair(case_id, Arm.CORRECTION,
                      rows_for(case_id, Arm.BASELINE, framing_only=False), correction)
            )

    resolved = [p for p in framing_pairs if p.verdict is not Verdict.UNRESOLVED]
    if not resolved:
        effect = Effect.INSUFFICIENT
    elif any(p.verdict is Verdict.FLIP for p in resolved):
        effect = Effect.MEASURED
    else:
        effect = Effect.NONE_MEASURED

    notes = [
        "Denominators include every attempted run, failures included.",
        "A timeout is unresolved: neither a flip nor resistance to a cue.",
        "Coverage records whether attempts reached a definitive outcome; it is "
        "not task success. An empty run is vacuously covered.",
        "A flip is an observed difference between recorded choices. No "
        "causal, fairness, or internal-mechanism claim follows from it.",
    ]
    if effect is Effect.NONE_MEASURED:
        notes.append(
            "No framing effect was measured in these records. That is a "
            "reportable result, not a missing one."
        )
    if effect is Effect.INSUFFICIENT:
        notes.append(
            "No pair had a readable decision on both sides, so this dataset "
            "supports no statement about framing either way."
        )

    # Deduplicate exclusions while preserving first-seen order.
    seen: set[str] = set()
    unique_excluded: list[dict[str, object]] = []
    for entry in excluded:
        key = str(entry["condition_id"])
        if key not in seen:
            seen.add(key)
            unique_excluded.append(entry)

    return Analysis(
        attempts=len(records),
        arms=tuple(arms),
        coverage=tuple(coverage),
        framing_pairs=tuple(framing_pairs),
        correction_pairs=tuple(correction_pairs),
        excluded=tuple(unique_excluded),
        effect=effect,
        notes=tuple(notes),
    )


__all__ = [
    "Verdict", "Effect", "ArmSummary", "Coverage", "Pair", "Analysis", "summarize",
]
