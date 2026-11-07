"""Reading a model's raw output. The reader itself is a seam.

Deciding whether text expresses a refusal, which option it selected, or whether
it was cut off requires the agreed rubric and option set. docs/project.md
records that the team has not agreed the rubric, the relevant versus irrelevant
cues, or the case format, so :func:`parse` raises rather than guessing.

What *is* settled and lives here: the shape of the signal a parser must
produce, and the rule that a model's own explanation is a received explanation
rather than a faithful account of its computation (docs/evaluation.md). Raw
text is therefore always retained alongside whatever was extracted from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from runner.outcomes import Correctness

if TYPE_CHECKING:
    from runner.cases import Case


@dataclass(frozen=True)
class ParseSignal:
    """The facts about one attempt that decide its outcome bucket.

    Every field defaults to the benign reading so a partially populated signal
    classifies as ``MALFORMED`` rather than silently as a decision: both
    ``decodable`` and ``choice_in_rubric`` must be set to True deliberately.
    """

    timed_out: bool = False
    transport_error: bool = False
    truncated: bool = False
    refused: bool = False
    decodable: bool = False
    choice_in_rubric: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "timed_out": self.timed_out,
            "transport_error": self.transport_error,
            "truncated": self.truncated,
            "refused": self.refused,
            "decodable": self.decodable,
            "choice_in_rubric": self.choice_in_rubric,
        }


@dataclass(frozen=True)
class Mention:
    """A source named in the output, and whether the record supports it.

    The Lean oracle is explicit that ``cite`` admits observed evidence only,
    and that a raw mention must stay visible without being promoted to an
    observed edge. This type is how a mention stays visible: unsupported
    mentions are recorded with ``supported=False`` and are refused by
    :func:`runner.trace.cite`.
    """

    source: str
    supported: bool
    evidence_id: str | None = None


@dataclass(frozen=True)
class Decision:
    """A readable choice plus everything needed to audit how it was read."""

    option_id: str
    signal: ParseSignal
    correctness: Correctness = Correctness.UNKNOWN
    mentions: tuple[Mention, ...] = field(default_factory=tuple)
    received_explanation: str | None = None


def parse(raw: str, case: Case) -> Decision:
    """SEAM: read one raw output against a case's options and rubric.

    Raises:
        NotImplementedError: always. The rubric, the option vocabulary, and the
            refusal and truncation criteria are unapproved; see
            docs/project.md "Decisions still required".
    """
    raise NotImplementedError(
        "parsing is a seam: the rubric, option vocabulary, and refusal and "
        "truncation criteria are not agreed. See docs/project.md and "
        "docs/contracts.md before implementing."
    )


def grade(decision: Decision, case: Case) -> Correctness:
    """SEAM: score a readable decision against the rubric.

    Raises:
        NotImplementedError: always. Correctness is rubric-defined and the
            rubric is unapproved.
    """
    raise NotImplementedError(
        "grading is a seam: no rubric is approved. See docs/project.md."
    )


__all__ = ["ParseSignal", "Mention", "Decision", "parse", "grade"]
