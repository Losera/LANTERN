"""Tool proposals (recorded) and tool execution (a seam).

One sentence from docs/evaluation.md defines this module: "The runner validates
and executes approved tools; model proposals are not tool execution evidence."

That distinction is the whole design. A model emitting text that looks like a
tool call has proposed something and nothing more. Recording a proposal is
therefore implemented -- it is just honest bookkeeping -- while executing one
raises, because docs/project.md lists tool contracts among the decisions the
lead must approve, and docs/evaluation.md adds that "tool interfaces, IDs,
sealing/reopening, and result formats need human schema/contract review before
implementation".

The Lean oracle reinforces the shape: dispatch and completion are separate
events, so a proposal that is executed later must be recorded twice, once at
each boundary, never collapsed into a single "the model used a tool" fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProposalStatus(str, Enum):
    """What became of a proposed call.

    ``PROPOSED`` is the terminal state today: with no approved registry,
    nothing can advance past it. ``REJECTED`` records a proposal the runner
    declined, which must stay visible rather than being dropped.
    """

    PROPOSED = "proposed"
    REJECTED = "rejected"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ToolProposal:
    """Something a model's output asked for. Not an execution.

    ``raw`` keeps the model's own wording, because a proposal the runner could
    not even parse is still a proposal worth recording.
    """

    tool_name: str
    raw: str
    status: ProposalStatus = ProposalStatus.PROPOSED
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "tool_name": self.tool_name,
            "raw": self.raw,
            "status": self.status.value,
            "reason": self.reason,
            "executed": False if self.status in {
                ProposalStatus.PROPOSED, ProposalStatus.REJECTED
            } else None,
        }


@dataclass(frozen=True)
class ToolResult:
    """The outcome of an execution the runner actually performed."""

    tool_name: str
    artifact_id: str
    succeeded: bool
    detail: str | None = None


def record_proposal(tool_name: str, raw: str, *, reason: str | None = None) -> ToolProposal:
    """Note that a model proposed a call, without executing anything.

    With no approved registry every proposal is rejected, and the reason says
    so explicitly rather than leaving an unexplained refusal in the record.
    """
    if not tool_name.strip():
        raise ValueError("a proposal must name a tool, even an unrecognised one")
    return ToolProposal(
        tool_name=tool_name,
        raw=raw,
        status=ProposalStatus.REJECTED,
        reason=reason or "no tool contract is approved; proposal recorded, not executed",
    )


@dataclass
class ToolRegistry:
    """SEAM: the allowlist of tools the runner would be permitted to execute.

    Empty by construction. An allowlist is not a sandbox (docs/alpha.md), so
    populating this needs both an approved contract and a decision about what
    the runner is actually permitted to touch.
    """

    allowed: dict[str, object] = field(default_factory=dict)

    def execute(self, proposal: ToolProposal) -> ToolResult:
        """Raises:
            NotImplementedError: always.
        """
        raise NotImplementedError(
            "tool execution is a seam: no tool contract, result format, or "
            "identifier scheme is approved. A model proposal is not execution "
            "evidence. See docs/evaluation.md and docs/project.md."
        )


__all__ = [
    "ProposalStatus", "ToolProposal", "ToolResult", "record_proposal", "ToolRegistry",
]
