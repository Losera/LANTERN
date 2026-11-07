"""Rendering a case and condition into the exact text sent to a model. A seam.

This is the most consequential unapproved decision in the experiment. The
prompt *is* the independent variable: how evidence is ordered, which cue is
inserted, and how the rubric is phrased determine what the comparison measures.
docs/project.md records that the team has not agreed the rubric, the relevant
versus irrelevant cues, or the case format, and that the campus-transport
packet and the neutral evidence-table correction are research recommendations
rather than approved fixtures.

Two constraints are already settled and must survive implementation:

Length-matched neutral edits
    A neutral edit must be of comparable length to the framing change, or the
    contrast measures edit size instead of framing.

Preserved provenance
    docs/evaluation.md forbids stripping reliability information merely to
    force unchanged answers. A correction presents a neutral evidence table;
    it does not delete source authority silently.

:func:`render` must also return the digest of the text it produced, so an
attempt record can be tied to the exact input rather than to a template name.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from runner.models import PromptPayload

if TYPE_CHECKING:
    from runner.cases import Case
    from runner.conditions import Condition


def digest(text: str) -> str:
    """SHA-256 of the exact prompt text, as recorded with every attempt.

    Implemented because it is deterministic and because a record without it
    cannot be tied back to what was actually sent. This identifies an input;
    as the Lean oracle's README notes, a digest does not attest to its truth.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(case: Case, condition: Condition) -> PromptPayload:
    """SEAM: build the exact text for one case under one condition.

    Raises:
        NotImplementedError: always. The rubric wording, the cue inventory, and
            the evidence-ordering policy are unapproved; see docs/project.md
            "Decisions still required".
    """
    raise NotImplementedError(
        "prompt rendering is a seam: the rubric wording, the relevant versus "
        "irrelevant cue inventory, and the evidence-ordering policy are not "
        "agreed. See docs/project.md and docs/evaluation.md 'Declare the "
        "comparison before measuring'."
    )


__all__ = ["digest", "render", "PromptPayload"]
