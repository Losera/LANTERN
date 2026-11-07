"""The failure taxonomy, and the one place that decides which bucket applies.

docs/evaluation.md requires that malformed output, truncation, refusal,
timeout, invalid choice, and an ordinary wrong answer be separated rather than
collapsed into one failure count. It also requires that a timeout stay
*unknown* instead of being read as either definitive failure or as the model
successfully resisting a cue.

Two axes are deliberately kept apart:

``Outcome``
    Did the attempt yield a decision we can read at all? A wrong answer is a
    readable decision; a truncated one is not.

``Correctness``
    Was a readable decision right, by the rubric? This needs the rubric, so
    grading lives behind a seam and defaults to ``UNKNOWN`` here.

"Ordinary wrong answer" is therefore ``Outcome.DECISION`` plus
``Correctness.INCORRECT``, not an outcome of its own.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Annotations are strings, so no runtime import is needed.
    from runner.parsing import ParseSignal


class Outcome(str, Enum):
    """What an attempt produced. String-valued so records stay readable."""

    DECISION = "decision"
    MALFORMED = "malformed"
    TRUNCATED = "truncated"
    REFUSAL = "refusal"
    TIMEOUT = "timeout"
    INVALID_CHOICE = "invalid_choice"
    ERROR = "error"


class Correctness(str, Enum):
    """Whether a readable decision satisfied the rubric."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"


#: Outcomes that leave the attempt's fate genuinely unresolved. A timeout is
#: the whole reason this set exists: it is not a failure and it is not
#: resistance to bias.
UNRESOLVED = frozenset({Outcome.TIMEOUT})

#: Definitive non-decisions. Each is recorded and counted on its own.
FAILURES = frozenset({
    Outcome.MALFORMED,
    Outcome.TRUNCATED,
    Outcome.REFUSAL,
    Outcome.INVALID_CHOICE,
    Outcome.ERROR,
})

#: Outcomes a paired comparison can actually read.
USABLE = frozenset({Outcome.DECISION})

#: Precedence used by :func:`classify`, most to least decisive. Order is a
#: judgement, not an accident: a timeout wins because nothing later can be
#: trusted about an attempt that never returned, and truncation outranks
#: refusal because a cut-off answer cannot be read as a declined one.
PRECEDENCE = (
    Outcome.TIMEOUT,
    Outcome.ERROR,
    Outcome.TRUNCATED,
    Outcome.REFUSAL,
    Outcome.MALFORMED,
    Outcome.INVALID_CHOICE,
    Outcome.DECISION,
)


def is_definitive(outcome: Outcome) -> bool:
    """True when the attempt's fate is settled either way.

    The Lean oracle draws the same line: ``timeout_does_not_create_outcome``
    keeps an unanswered attempt out of the outcome list entirely.
    """
    return outcome not in UNRESOLVED


def is_usable(outcome: Outcome) -> bool:
    """True when a paired comparison may read this attempt's choice."""
    return outcome in USABLE


def classify(signal: ParseSignal) -> Outcome:
    """Map a parse signal to exactly one outcome, by :data:`PRECEDENCE`.

    The signal is produced by the parsing seam; turning it into a bucket is
    deterministic and lives here so there is one auditable rule rather than
    scattered ``if`` chains at each call site.
    """
    flags = {
        Outcome.TIMEOUT: signal.timed_out,
        Outcome.ERROR: signal.transport_error,
        Outcome.TRUNCATED: signal.truncated,
        Outcome.REFUSAL: signal.refused,
        Outcome.MALFORMED: not signal.decodable,
        Outcome.INVALID_CHOICE: not signal.choice_in_rubric,
        Outcome.DECISION: True,
    }
    for outcome in PRECEDENCE:
        if flags[outcome]:
            return outcome
    raise AssertionError("PRECEDENCE must end in an unconditional outcome")


__all__ = [
    "Outcome", "Correctness", "UNRESOLVED", "FAILURES", "USABLE",
    "PRECEDENCE", "is_definitive", "is_usable", "classify",
]
