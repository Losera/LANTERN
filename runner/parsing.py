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
import math

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


"""def parseOUTDATED(output_id: str, case: Case) -> Decision:
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
        signal = ParseSignal(transport_error=True)
        #really gotta return an invalid Decision
        return None
        
    try: #this is for the diagnostic
        with open((filepath + "diagnostic-result.json"), 'r', encoding='utf-8') as file:
            diagnostic = json.load(file)
    except FileNotFoundError:
        print(" PARSER COULD NOT FIND DIAGNOSTIC FILE ")
        signal = ParseSignal(transport_error=True)
        #return invalid Decision
        return None
        
    try: #this is for inference-result
        with open((filepath + "inference-result.json"), 'r', encoding='utf-8') as file:
            filepath = json.load(file)
    except FileNotFoundError:
        print(" PARSER COULD NOT FIND INFERENCE RESULT FILE ")
        signal = ParseSignal(transport_error=True)
        #return invalid Decision
        return None
        
    status = diagnostic.get("status")
    diagnostic = None #deallocate cuz oh my god this thing is huge
    if status == ParseSignal.timed_out:
        signal = ParseSignal(timed_out=True)
        return None
    elif status == ParseSignal.transport_error:
        signal = ParseSignal(transport_error=True)
        return None
    elif status == ParseSignal.truncated:
        signal = ParseSignal(truncated=True)
        return None
    #if none of these pass, then signal is good!
    
    
    attempts = output.get("attempts")
    if len(attempts) == 0:
        signal = ParseSignal(transport_error=True)
        #return invalid decision
        return None
        
    #for now use first attempt
    #mostSignificantAttempt
    msAttempt = attempts[0]
    option_id = msAttempt.get("operation_id")
    case_id = msAttempt.get("case_id")
    if case_id != case.id:
        print(" MALFORMED CASE ID, DOESN'T MATCH ")
        signal = ParseSignal(transport_error=True)
        #really gotta return an invalid Decision
        return None
    options = case.options
    found_case = False
    for option in options:
        if option.id == option_id:
            signal = ParseSignal(choice_in_rubric=True)
            found_case = True
            break
    if not found_case: signal = ParseSignal(choice_not_in_rubric=True)
            
    reasoning = reasoning.get("raw_output")
    evidence = tuple(output.get("evidence"))
    #if we reached this point then signal good
    if signal is None:
        signal = ParseSignal(decodable=True)
    return Decision(
        option_id = option_id,
        signal = signal,
        correctness = Correctness.UNKNOWN, #this gets fixed later
        mentions = evidence,
        received_explanation = reasoning
    )"""
    
def parse(raw_output: str, case: Case) -> Decision:
    def malformed() -> Decision:
        return Decision(
            option_id="",
            signal=ParseSignal(refused=False),
            correctness=Correctness.UNKNOWN,
            mentions=(),
            received_explanation=None,
        )
    if not isinstance(raw_output, str):
        return malformed()
        
    def reject_constant(value: str):
        raise ValueError(f"non-finite JSON number: {value}")
        
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
        
    try:
        payload = json.loads(
            raw_output,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (ValueError, json.JSONDecodeError):
        return malformed()
        
    required = {"option_id", "evidence_ids", "explanation"}
    if not isinstance(payload, dict) or set(payload) != required:
        return malformed()
        
    option_id = payload["option_id"]
    evidence_ids = payload["evidence_ids"]
    explanation = payload["explanation"]
    
    if (
        not isinstance(option_id, str)
        or not option_id
        or not isinstance(evidence_ids, list)
        or any(not isinstance(item, str) or not item for item in evidence_ids)
        or not isinstance(explanation, str)
    ):
        return malformed()
        
    known_options = {option.id for option in case.options}
    mentions = []
    for evidence_id in evidence_ids:
        item = case.evidence_by_id(evidence_id)
        mentions.append(
            Mention(
                source=evidence_id,
                supported=False,
                evidence_id=item.id if item is not None else None,
            )
        )
        
    return Decision(
        option_id=option_id,
        signal=ParseSignal(
            decodable=True,
            choice_in_rubric=option_id in known_options,
            refused=False,
        ),
        correctness=Correctness.UNKNOWN,
        mentions=tuple(mentions),
        received_explanation=explanation,
    )
            


def grade(decision: Decision, case: Case) -> Correctness:
    """SEAM: score a readable decision against the frozen grading key.

    docs/evaluation.md requires requirement-level grading: each rubric
    requirement is assessed as satisfied, violated, or indeterminate against a
    frozen key that states an observable pass condition, a failure condition,
    and the evidence making it decidable. No such key exists in this
    repository, and this signature cannot reach one, so there is nothing to
    grade against.

    Agreement with a user, baseline, or in-rubric choice is explicitly *not* a
    substitute: docs/evaluation.md records that it "cannot substitute for
    requirement-level grading". Returning a value here would let
    :func:`runner.alpha_import.import_bundle` stamp a correctness onto an
    append-only record that no approved rubric supports, which is exactly the
    failure the offline lane's seam check guards.

    Raises:
        NotImplementedError: always, until a frozen grading key is approved.
    """
    raise NotImplementedError(
        "grading is a seam: no frozen grading key is approved. "
        "See docs/evaluation.md 'Reproducible correctness grading'."
    )


__all__ = ["ParseSignal", "Mention", "Decision", "parse", "grade"]
