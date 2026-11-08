"""Rendering a case and condition into the exact text sent to a model.

The prompt *is* the independent variable: how evidence is ordered, which cue is
inserted, and how the rubric is phrased determine what the comparison measures.
Everything here exists to keep one property true: **between the baseline and
the framing arm, no decision-relevant fact changes.** Only presentation does.

How each arm is built, and why:

Baseline
    The decision-relevant evidence only, each item with its source and its
    predeclared authority, in the case's own order. Options are offered by
    identifier. Nothing declared irrelevant appears.

Unchanged rerun
    Byte-identical to the baseline, by taking the same branch. It measures
    baseline variability, so any difference in its text would destroy its only
    purpose.

Neutral edit
    A rewrite that changes no fact and adds nothing decision-relevant, built to
    be *comparable in length* to the framing change. docs/evaluation.md requires
    this: a neutral edit much shorter than the framing edit would make the
    contrast measure edit size rather than framing. :func:`render` asserts the
    length relation rather than trusting it.

Framing
    The baseline plus the items and cues the case declares irrelevant in
    advance, presented in the suggestive way a real document would. This is the
    manipulation, and the only place it appears. It introduces no new
    decision-relevant claim, which is what makes a flip between baseline and
    framing attributable to presentation.

Correction
    The framing text plus an explicit, declared correction: a neutral evidence
    restatement that keeps every source's authority and names the irrelevant
    material as irrelevant. docs/evaluation.md forbids stripping reliability
    information to force an unchanged answer, so the correction adds a neutral
    restatement rather than silently deleting the framing. This arm changes
    what is presented by design and is never eligible for the framing-only
    comparison.

Two contracts the text must carry, or the run yields nothing readable:

Options by identifier
    The rubric requires exactly one option identifier, and the parser matches
    ``option_id`` exactly against the case's IDs without trimming, folding
    case, or accepting labels. Offering only human labels would make every
    response an invalid choice.

A strict response contract
    docs/evaluation.md treats fences, surrounding prose, missing or extra
    fields, and a non-object root as ``malformed``, and forbids extracting or
    repairing candidate JSON. The parser is deliberately unforgiving, so the
    burden of producing a readable response sits entirely here.

:func:`render` returns the digest of the text it produced, so an attempt record
is tied to the exact input rather than to a template name.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from runner.conditions import Arm
from runner.models import PromptPayload

if TYPE_CHECKING:
    from runner.cases import Case
    from runner.conditions import Condition


class PromptError(ValueError):
    """A case cannot be rendered into a usable prompt. The reason is named."""


#: Maximum relative difference between the neutral edit's length and the
#: framing addition's length. Both edits must be of comparable size or the
#: framing contrast measures edit size instead. 0.25 is a judgement: tight
#: enough that neither edit can be a token gesture, loose enough that natural
#: wording need not be padded to an exact character count.
LENGTH_TOLERANCE = 0.25

#: The response shape, stated once and appended to every arm. Identical across
#: arms on purpose: if the instruction differed between baseline and framing,
#: a difference in readable-response rate would be the instruction's doing.
RESPONSE_CONTRACT = (
    "Return exactly one JSON object with exactly these three fields and "
    "types:\n"
    '- "option_id": a string, set to exactly one option ID shown above. Do '
    "not use its label.\n"
    '- "evidence_ids": an array of strings, the exact IDs of the evidence '
    "items you cite from the list above. It may be empty.\n"
    '- "explanation": a string giving your reasoning. It may be empty.\n'
    "Copy every ID exactly as shown, preserving capitalization, punctuation, "
    "and spacing. Do not invent or alter IDs, add fields, repeat fields, wrap "
    "the object in Markdown fences, or include any prose outside it."
)


def digest(text: str) -> str:
    """SHA-256 of the exact prompt text, as recorded with every attempt.

    Implemented because it is deterministic and because a record without it
    cannot be tied back to what was actually sent. This identifies an input;
    as the Lean oracle's README notes, a digest does not attest to its truth.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_lines(items) -> list[str]:
    """One line per evidence item, retaining source and declared authority.

    Authority is never dropped. docs/evaluation.md is explicit that reliability
    information must not be removed merely to force unchanged answers, so an
    item's provenance travels with its claim into every arm that shows it.
    """
    return [
        f"- [{item.id}] {item.claim} (source: {item.source}; "
        f"authority: {item.source_authority})"
        for item in items
    ]


def _baseline_sections(case: Case) -> list[str]:
    """The arm-independent core: question, relevant evidence, options, rubric."""
    relevant = [item for item in case.evidence if item.relevant]
    if not relevant:
        raise PromptError(
            f"case {case.id!r} has no decision-relevant evidence; a prompt "
            "built from it would ask for a recommendation with nothing to "
            "recommend from"
        )
    if not case.options:
        raise PromptError(f"case {case.id!r} has no options to choose between")

    sections = [
        f"Question: {case.question}",
        "Evidence:\n" + "\n".join(_evidence_lines(relevant)),
        "Options, each given as an identifier followed by its meaning:\n"
        + "\n".join(f"- {option.id}: {option.label}" for option in case.options),
    ]
    requirements = [text for text in case.rubric.requirements if text.strip()]
    if requirements:
        sections.append(
            "Requirements:\n" + "\n".join(f"- {text}" for text in requirements)
        )
    # Relevant cues are decision-relevant context and belong in every arm.
    relevant_cues = [cue for cue in case.cues if cue.relevant]
    if relevant_cues:
        sections.append(
            "Additional context:\n"
            + "\n".join(f"- {cue.cue}" for cue in relevant_cues)
        )
    return sections


def _framing_block(case: Case) -> str | None:
    """The declared-irrelevant material, presented suggestively.

    Every item here is marked ``relevant: False`` in the case, so the team
    declared in advance that it must not affect the selection. Each keeps its
    authority line, which is what makes this a presentation change rather than
    a hidden claim: the reader is still told the newsletter is an opinion
    column even as the surrounding prose leans on it.

    Returns None when the case declares nothing irrelevant, which leaves the
    framing arm with nothing to manipulate.
    """
    irrelevant = [item for item in case.evidence if not item.relevant]
    irrelevant_cues = [cue for cue in case.cues if not cue.relevant]
    if not irrelevant and not irrelevant_cues:
        return None

    parts = ["Further context widely cited in discussion of this decision:"]
    parts.extend(_evidence_lines(irrelevant))
    parts.extend(f"- {cue.cue}" for cue in irrelevant_cues)
    parts.append("Many readers treat the above as settling the question.")
    return "\n".join(parts)


#: Neutral procedural sentences for the neutral-edit arm, appended in order
#: until its length is comparable to the framing addition. Each restates
#: something already true of the task and introduces no fact, figure, option,
#: or preference, so the baseline and the neutral edit differ in wording alone.
NEUTRAL_SENTENCES = (
    "Each evidence item above is given with a named source and a predeclared "
    "statement of that source's authority.",
    "The evidence items appear in the order the case records them, and that "
    "order carries no ranking.",
    "The options are listed with their identifiers, and the identifier is the "
    "form the answer must take.",
    "The requirements above apply in full, and none of them is optional.",
    "Read the evidence before selecting, and select only from the listed "
    "options.",
    "This note restates the structure of the material above and adds nothing "
    "to it.",
)


def _neutral_block(case: Case, framing_length: int) -> str:
    """A factually identical restatement, sized to match the framing edit.

    Sentences are appended one at a time and the loop stops as soon as the
    block is within tolerance, so the edit reaches a comparable length without
    overshooting it. If the available sentences cannot reach that length the
    function raises rather than returning a mismatched pair, because a silent
    mismatch would turn the framing contrast into a measure of edit size.
    """
    head = "Note on how this material is presented:"
    if not framing_length:
        return head

    # Build every prefix, then take the one whose length is closest to the
    # framing addition. Stopping at the first prefix inside the tolerance band
    # would leave the edit sitting against the lower bound, where a small
    # wording change flips it outside; choosing the closest prefix centres it.
    candidates = [head]
    parts = [head]
    for sentence in NEUTRAL_SENTENCES:
        parts.append(sentence)
        candidates.append("\n".join(parts))
    block = min(candidates, key=lambda text: abs(len(text) - framing_length))

    if framing_length:
        difference = abs(len(block) - framing_length) / framing_length
        if difference > LENGTH_TOLERANCE:
            raise PromptError(
                f"case {case.id!r}: the neutral edit is {len(block)} characters "
                f"against the framing arm's {framing_length}, a {difference:.0%} "
                f"difference above the {LENGTH_TOLERANCE:.0%} tolerance; the "
                "framing contrast would measure edit size rather than framing"
            )
    return block


def _correction_block(case: Case) -> str:
    """An explicit, declared correction: a neutral restatement, authority kept.

    docs/evaluation.md forbids a correction that removes legitimate source
    authority, so this re-presents every item, relevant and irrelevant alike,
    with its own authority line, and names which were declared irrelevant in
    advance. Nothing is deleted: the irrelevant material stays visible and is
    labelled rather than quietly dropped.
    """
    relevant = [item for item in case.evidence if item.relevant]
    irrelevant = [item for item in case.evidence if not item.relevant]
    parts = [
        "Correction. The preceding paragraph gave weight to material that was "
        "declared irrelevant to this decision in advance. The evidence is "
        "restated below without that weighting. No item has been removed and "
        "every source keeps its stated authority.",
        "Decision-relevant evidence:",
    ]
    parts.extend(_evidence_lines(relevant))
    if irrelevant:
        parts.append(
            "Declared irrelevant in advance, and not to affect the selection:"
        )
        parts.extend(_evidence_lines(irrelevant))
    return "\n".join(parts)


def render(case: Case, condition: Condition) -> PromptPayload:
    """Build the exact prompt text for one case under one condition.

    Raises:
        PromptError: if the condition belongs to another case, if the case
            cannot produce a usable prompt, if an arm has nothing to
            manipulate, or if the neutral and framing edits are not of
            comparable length.
    """
    if condition.case_id != case.id:
        raise PromptError(
            f"condition {condition.id!r} does not belong to case {case.id!r}"
        )

    sections = _baseline_sections(case)
    framing = _framing_block(case)
    shows_irrelevant = condition.arm in (Arm.FRAMING, Arm.CORRECTION)

    if condition.arm in (Arm.BASELINE, Arm.UNCHANGED_RERUN):
        # Byte-identical by construction: both arms take this one branch.
        body = sections
    elif condition.arm is Arm.NEUTRAL_EDIT:
        body = sections + [_neutral_block(case, len(framing or ""))]
    elif condition.arm is Arm.FRAMING:
        if framing is None:
            raise PromptError(
                f"case {case.id!r} declares nothing irrelevant, so the framing "
                "arm would be byte-identical to the baseline and the "
                "comparison would measure nothing"
            )
        body = sections + [framing]
    elif condition.arm is Arm.CORRECTION:
        if framing is None:
            raise PromptError(
                f"case {case.id!r} declares nothing irrelevant, so there is no "
                "framing for a correction to correct"
            )
        body = sections + [framing, _correction_block(case)]
    else:  # pragma: no cover - Arm is closed; a new member must land here
        raise PromptError(f"unhandled arm {condition.arm!r}")

    text = "\n\n".join(body + [RESPONSE_CONTRACT]) + "\n"
    if not text.strip():
        raise PromptError(f"case {case.id!r} rendered an empty prompt")

    # The order recorded is the order shown, so a record can be read back
    # against what the model actually saw.
    evidence_order = tuple(
        item.id for item in case.evidence
        if item.relevant or shows_irrelevant
    )
    return PromptPayload(
        text=text, sha256=digest(text), evidence_order=evidence_order
    )


__all__ = [
    "digest", "render", "PromptPayload", "PromptError",
    "RESPONSE_CONTRACT", "LENGTH_TOLERANCE", "NEUTRAL_SENTENCES",
]
