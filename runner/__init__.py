"""LANTERN experiment runner: contracts, deterministic parts, and explicit seams.

LANTERN asks whether an irrelevant presentation cue changes a recommendation
while the evidence and the decision rubric stay fixed, and whether a declared
correction reduces avoidable sensitivity. This package is the runner side of
that experiment. It is a reviewed skeleton, not a finished application.

Two kinds of module live here and the distinction is load-bearing:

Implemented
    Deterministic work that needs no architectural approval: condition
    expansion, the failure taxonomy, append-only recording with explicit
    unknowns, oracle trace emission, paired analysis, and the export
    projection. These have behavior and are checked by ``tools/check_app.py``.

Seams
    Work that is gated on the lead's approval and on the team agreeing a
    rubric: prompt rendering, model adapters, tool execution, and output
    parsing. These raise ``NotImplementedError`` with the missing approval
    named. A seam must never return fabricated data, because a plausible stub
    is indistinguishable from a result once it reaches the export.

Nothing in this package establishes Alpha connectivity, model behavior,
conformance to the Lean design oracle, or reduced bias. See docs/evaluation.md
for the evidence boundaries and docs/contracts.md for the proposed formats.
"""

from __future__ import annotations

#: Version tag on every persisted document. Zero means PROPOSED and unstable:
#: the formats may change without a migration path until the lead approves
#: them as contracts. See docs/contracts.md.
SCHEMA_VERSION = 0

#: The lane name recorded in exports, mirroring the Lean oracle's habit of
#: naming the lane that produced a verdict. This lane proves the skeleton is
#: coherent; it proves nothing about the experiment's conclusions.
LANE = "local application skeleton"

__all__ = ["SCHEMA_VERSION", "LANE"]
