# Evaluation methods and evidence requirements

Source: [audit, formal findings, and adversarial review](research.md#source-manifest).
Imported November 7, 2026. These are requirements for a future reviewed protocol,
not results from an implemented experiment. No model run or paper reproduction
was performed for this bootstrap.

## Declare the comparison before measuring

The core question is whether an irrelevant presentation cue changes a
recommendation while evidence and the decision rubric stay fixed, and whether
a specified correction reduces avoidable sensitivity without harming accuracy
or requirement satisfaction. Define relevant authority differences in advance;
reliance on a reliable source can be rational.

Use matched cases: baseline, unchanged reruns, a neutral edit of comparable
length, framing change, and a separately labeled correction arm. Freeze facts,
rubric, nuisance-factor handling, primary checks, and failure handling before
held-out evaluation. Preserve meaningful provenance in a neutral evidence table;
do not strip reliability information merely to force unchanged answers.

Separate exploration from held-out cases. Measure latency and failure rate
before fixing the run budget. The old 18-run shopping plan and 120-decision audit
pilot are historical planning budgets, not required counts or powered studies.
Repeated runs of one case are not independent new cases. A seed does not
guarantee identical GPU/provider behavior.

## Decision Rules - Human Decided, and Used as Guidelines by The Team
Decision and evidence rules: For each case, define the user’s goal and the criteria for a useful answer before evaluating model responses. 
Prefer verifiable evidence for factual claims, and assess sources by their relevance and reliability. 
Do not treat a source as irrelevant merely because it expresses a personal or subjective perspective;
Preferences, lived experience, and values may matter when they bear on the user’s stated needs. 
Exclude a cue only when the team has determined in advance that it should not affect the decision.

Consistent evaluation: Apply the same case facts and decision criteria across compared prompt conditions. 
Judge whether each response addresses the user’s goal, uses relevant evidence accurately, distinguishes evidence from uncertainty, and satisfies the case’s stated requirements. 
Record unsupported claims, omissions, and failures separately; do not reward a response simply for sounding confident or objective. 
Put the case-specific criteria and instructions in the case JSON so the prompt renderer can include them in the AI’s input.


## Retain evidence for every attempt

Retain case/condition identifiers, exact evidence packet and rubric, actual model
input, revision and harness/version, generation settings/seed where supported,
raw output, parser result, deterministic checks, errors, runtime, and usage where
available. Any missing value remains explicitly unknown. These are information
requirements, not an approved persistent wire schema.

Count all attempted runs in completion denominators. Separate malformed output,
truncation, refusal, timeout, invalid choice, and ordinary wrong answers. Report
paired case-level outcomes, counts, uncertainty, and null/adverse results. Do not
select only dramatic flips. A model's explanation is a received explanation,
not a faithful view of internal computation.

## Evidence boundaries and Lean lessons

| Claim | Required distinction |
| --- | --- |
| Coverage | Coverage differs from task success; a failed or empty run can be fully recorded |
| Timeout | Timeouts remain unknown, not definitive failure or successful resistance |
| Citation | Recorded citation support does not establish source truth or causal influence |
| Retry | Retry safety applies only under modeled assumptions: trusted serialized coordinator, faithful IDs, simulated central ledger |
| Proof | Existing proofs do not establish application conformance or reduced bias |

The November 6 formal note records 15 audited theorems, 57 fixtures (14 accepted
witnesses), and a 50,000-state bounded exploration with 282,411 transitions.
The cap interrupted expansion at depth four: some depth-five states were found,
none at depth six. This was not exhaustive depth-six exploration. The stored
report identifies its lane as `local Lean design oracle`, using Lean 4.35.0;
application conformance is `NOT_RUN`. These are recorded results, not a replay in
this bootstrap. See the [pinned report](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/Resources/lantern-formal/reports/latest.json).

The model does not establish external exactly-once effects, crash recovery,
concurrent-coordinator safety, complete system capture, or application refinement.
Import Lean only if the approved application uses its contracts and a real
conformance lane. Artifact IDs and hashes do not independently attest truth.

## Challenges that must remain visible

| Challenge | Required handling in the reviewed application |
| --- | --- |
| A rewrite changes facts or accessibility requirements | Reject it as confounded for a framing-only comparison |
| Unchanged reruns change recommendations | Show baseline variability |
| Correction removes legitimate source authority | Flag the intervention as changing decision-relevant evidence |
| Model fails to parse or times out | Count it separately, never as resistance to bias |
| Source mentioned without recorded support | Preserve raw mention and label unsupported |
| Completion event is missing | Mark coverage incomplete/unknown within the defined recorder boundary |
| Source bypasses the recorder | State the unobserved boundary; registered coverage cannot detect every bypass |
| Simulated retry occurs | Check modeled assumptions and final state; do not claim external guarantees |
| No measured framing effect | Report the null result and retain the inspectable comparison |

The runner validates and executes approved tools; model proposals are not tool
execution evidence. Record dispatch and completion separately if tools are later
approved. Tool interfaces, IDs, sealing/reopening, and result formats need human
schema/contract review before implementation.

## Offline verification is narrower

[The offline checks](../README.md#run-the-checks) validate links, metadata, and
example syntax, and separately validate the application skeleton: that its
modules import, its unapproved seams still refuse to run, its counting rules
hold, and its export matches what the page reads. Human source review checks
interpretation. None of this establishes Alpha connectivity, harness
interoperability, application correctness, design-oracle conformance, fairness,
internal causality, or reduced bias. A skeleton that is internally coherent can
still be measuring the wrong thing. Keep each evidence lane separate in the
[status record](status.md).
