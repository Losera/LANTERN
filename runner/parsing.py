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

import json

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
    choice_not_in_rubric: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "timed_out": self.timed_out,
            "transport_error": self.transport_error,
            "truncated": self.truncated,
            "refused": self.refused,
            "decodable": self.decodable,
            "choice_in_rubric": self.choice_in_rubric,
            "choice_not_in_rubric": self.choice_not_in_rubric,
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


def parse(output_id: str, case: Case) -> Decision:
    signal: ParseSignal | None = None
    output = {}
    diagnostic = {}
    reasoning = {}
    filepath = "../../evidence/alpha/job-" + output_id + "/"
    #only valid if runner script is in runner
    try: #this is for the output
        with open((filepath + output_id + ".json"), 'r', encoding='utf-8') as file:
            output = json.load(file)
    except FileNotFoundError:
        print(" PARSER COULD NOT FIND JSON FILE ")
        signal = ParseSignal.transport_error
        #really gotta return an invalid Decision
        return None
        
    try: #this is for the diagnostic
        with open((filepath + "diagnostic-result.json"), 'r', encoding='utf-8') as file:
            diagnostic = json.load(file)
    except FileNotFoundError:
        print(" PARSER COULD NOT FIND DIAGNOSTIC FILE ")
        signal = ParseSignal.transport_error
        #return invalid Decision
        return None
        
    try: #this is for inference-result
        with open((filepath + "inference-result.json"), 'r', encoding='utf-8') as file:
            filepath = json.load(file)
    except FileNotFoundError:
        print(" PARSER COULD NOT FIND INFERENCE RESULT FILE ")
        signal = ParseSignal.transport_error
        #return invalid Decision
        return None
        
    status = diagnostic.get("status")
    diagnostic = None #deallocate cuz oh my god this thing is huge
    if status == ParseSignal.timed_out.value:
        signal = ParseSignal.timed_out
        return None
    elif status == ParseSignal.transport_error.value:
        signal = ParseSignal.transport_error
        return None
    elif status == ParseSignal.truncated.value:
        signal = ParseSignal.truncated
        return None
    #if none of these pass, then signal is good!
    
    
    attempts = output.get("attempts")
    if len(attempts) == 0:
        signal = ParseSignal.transport_error
        #return invalid decision
        return None
        
    #for now use first attempt
    #mostSignificantAttempt
    msAttempt = attempts[0]
    option_id = msAttempt.get("operation_id")
    case_id = msAttempt.get("case_id")
    if case_id != case.id:
        print(" MALFORMED CASE ID, DOESN'T MATCH ")
        signal = ParseSignal.transport_error
        #really gotta return an invalid Decision
        return None
    options = case.options
    found_case = False
    for option in options:
        if option.id = option_id:
            signal = ParseSignal.choice_in_rubric
            found_case = True
            break
    if not found_case: signal = ParseSignal.choice_not_in_rubric
            
    reasoning = reasoning.get("raw_output")
    evidence = tuple(output.get("evidence"))
    #if we reached this point then signal good
    if signal is None:
        signal = ParseSignal.decodable
    return Decision(
        option_id = option_id
        signal = signal
        correctness = Correctness.UNKNOWN #this gets fixed later
        mentions = evidence
        received_explanation = reasoning
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
