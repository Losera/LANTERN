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

## Bootstrap verification is narrower

[Documentation checks](../README.md#check-bootstrap-materials) validate links,
metadata, and example syntax. Human source review checks interpretation. Neither
establishes Alpha connectivity, harness interoperability, application correctness,
fairness, internal causality, or reduced bias. Keep each evidence lane separate
in the [status record](status.md).
