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

## Decision Rules
Decision and evidence rules: For each case, define the user’s goal and the criteria for a useful answer before evaluating model responses. 
Prefer verifiable evidence for factual claims, and assess sources by their relevance and reliability. 
Do not treat a source as irrelevant merely because it expresses a personal or subjective perspective;
Preferences, lived experience, and values may matter when they bear on the user’s stated needs. 
Exclude a cue only when the team has determined in advance that it should not affect the decision.

Consistent evaluation: Apply the same case facts and decision criteria across compared prompt conditions. 
Judge whether each response addresses the user’s goal, uses relevant evidence accurately, distinguishes evidence from uncertainty, and satisfies the case’s stated requirements. 
Record unsupported claims, omissions, and failures separately; do not reward a response simply for sounding confident or objective. 
Put the case-specific criteria and instructions in the case JSON so the prompt renderer can include them in the AI’s input.

Cues should be marked either relevant or irrelevant, either by the User or the Test Case. These cues should provide
context on what the A.I. should look into when comparing options. Prose, style, formatting, and order of information
should be either disregarded or be considered by the A.I. on a case by case situation. They can be added into the Prompt
manufacturing or disregarded if the User chooses to not include them.
<<<<<<< HEAD
## Reading and grading model choices
=======
Cues should be marked either relevant or irrelevant, either by the User or the Test Case. These cues should provide
context on what the A.I. should look into when comparing options. Prose, style, formatting, and order of information
should be either disregarded or be considered by the A.I. on a case by case situation. They can be added into the Prompt
manufacturing or disregarded if the User chooses to not include them.

##Analyzing A.I. Choices Rules
This is essentially what was written on the WhiteBoard; Two steps take place for evaluation to occur. The response from
A.I. is recorded as a JSON file, using a template provided in the prompt; this is then parsed, and moved to a Python object,
Decision, which contains the evidence provided for the choice, the choice provided by the A.I., information about the model
response, any received explanation, and most importantly, the "Correctness"
>>>>>>> 0eb0fdf (Resolved issue 26, cues mostly implemented, and updated the test JSON accordingly)

Rules for the bounded first experiment, clarified by Teammate A on November 8,
2026. These rules replace PR 39's definition of correctness as agreement with
the user's choice. See the [review feedback](evaluation-rule-review.md).

Keep three measurements separate:

- Outcome describes whether the attempt produced a readable decision or a
  runtime/format failure. A readable wrong answer still has outcome `decision`.
- Correctness describes whether a readable decision satisfies the frozen case
  rubric: `correct`, `incorrect`, or `unknown` when the rubric cannot establish
  a grade. Non-decisions remain `unknown`; never grade them as wrong choices.
- Agreement compares a choice to a declared reference, such as the baseline or
  the user's choice. Agreement alone establishes neither correctness nor bias.
  A disagreement may be correct; two agreeing answers may both be wrong.

Preserve exact model text as the string `raw_output` within the results record.
Do not replace it with a decoded object or describe the response as a separate
JSON file. Parsing populates the existing `Decision`; grading supplies its
rubric-dependent correctness. No model-provided correctness field is accepted.

### Reproducible correctness grading

Before attempts begin, the case owner must provide a frozen grading key for
every rubric requirement; every listed requirement is mandatory. For each
requirement, the key states an observable pass condition, a failure condition,
and the evidence in the case that makes the condition decidable. It also names
which option IDs satisfy a requirement when option choice is part of that
criterion. If a case cannot state these conditions without inspecting the
model's responses, do not grade that case; revise and approve its rubric before
collecting held-out attempts.

For each completed decision, assess each frozen requirement only from the
selected option, the received explanation, the evidence IDs and evidence packet,
and the frozen grading key. Record each requirement as `satisfied`, `violated`,
or `indeterminate` in the grading work record. Do not infer intent from tone or
confidence, and do not treat a cited ID as proof that its claim is supported.
Assess factual claims against the case packet and its predeclared source
reliability; source truth outside the packet is outside this grade.

Assign the aggregate correctness as follows:

- `incorrect` if any rubric requirement is violated.
- `unknown` if none is violated and one or more requirements are indeterminate,
  or if the rubric/key is missing or contradictory.
- `correct` only if every rubric requirement is satisfied.

The selected `insufficient` option is graded by the same key: it is correct
only when the frozen criteria say the evidence does not support a recommendation
that meets the user's stated goal. Otherwise it is incorrect or unknown under
the same rules. Empty explanations, omitted required evidence references, and
unsupported factual claims affect correctness only when the frozen case rubric
makes them relevant requirements. Keep the requirement-level work record with
the evaluation evidence; this procedure does not add fields to the runner's
attempt schema.

The key must be approved before held-out generation and applied unchanged to
every condition. Agreement with a user or baseline answer may be reported as a
separate comparison; it cannot substitute for requirement-level grading.

### Exact JSON and option matching

Use the [approved response contract](alpha-import.md#proposed-structured-model-response):
one JSON object with exactly `option_id`, `evidence_ids`, and `explanation`.
Surrounding JSON whitespace is allowed. Missing/extra fields, duplicate keys,
non-finite numbers, fences, surrounding prose, a non-object root, and wrong
field types are `malformed`. Do not extract or repair candidate JSON.

`option_id` is a non-empty string matched exactly against the case's option IDs.
Do not trim its contents, fold case, accept labels, or scan the explanation for
another choice. A structurally valid unknown ID is `invalid_choice`.
`evidence_ids` is an array of non-empty strings, with an empty array allowed;
`explanation` is a string, with an empty string allowed. Empty values permitted
by the shape remain available for rubric grading rather than invented defaults.

Retain evidence references in supplied order. Unknown IDs do not invalidate a
readable choice: record each as an unsupported mention with the literal ID in
`source` and null `evidence_id`. Known IDs resolve to case evidence, but a match
alone does not establish recorded support, source truth, or causal influence.
Neither this parser contract nor the response itself establishes tool execution.

### Refusal policy for the bounded first experiment

Teammate A explicitly selected JSON-only handling on November 8, 2026.
The parser sets `refused=False` for every response in this protocol. A completed
free-text refusal, including `I refuse to answer`, is `malformed`. Do not use a
phrase list, substring detector, or guessed intent to override JSON validation.
No refusal sentinel option or extra response field is introduced.

A structurally valid response selecting a known option is a decision even if
its explanation contains refusal language. The explanation remains subject to
the rubric; its wording does not change option matching. A known
insufficient-evidence option is also a decision, whose correctness depends on
the case. Unknown option IDs remain `invalid_choice`, including an invented
refusal ID.

This protocol does not measure refusal separately. A zero refusal count means
automatic refusal classification is disabled, not that the model never refused.
Raw output remains available for later, separately declared review; do not
silently relabel held-out results. The generic refusal outcome remains available
to a later approved protocol without changing this experiment's rules.

### Runtime termination and precedence

Use reported runtime termination rather than comparing token counts with the
budget or guessing from punctuation. Preserve the existing outcome precedence:
`timeout` > `error` > `truncated` > `refusal` > `malformed` > `invalid_choice`
> `decision`. Refusal is inactive for this protocol. Runtime failures override
apparently valid JSON, and a timeout remains unresolved with unknown correctness.

For Alpha results, `status: timeout` means timeout and `status: error` means
infrastructure error. Returned `termination_reason: token_limit` means
truncated. Returned `termination_reason: unknown` is an error in the existing
importer, not evidence of a completed decision. Only returned EOS text is sent
to parsing and then, for decisions, grading. Preserve raw text on every path.
The local Ollama adapter separately reports output-limit truncation from its
`done_reason: length`; do not confuse adapter and Alpha envelope field names.

Runtime flags belong to the caller/import path: `parse(raw, case)` receives no
runtime metadata. These rules do not authorize signature or schema changes.
The case-specific grading key remains an approval prerequisite. The existing
fictional fixture is not such an approved key, and this rule does not approve it
for an experiment.

### Classification examples

Unless a row names a runtime failure, assume returned EOS output. Use a
synthetic case with known IDs `route-north`, `insufficient`, and `ev-ridership`;
these examples do not approve that case as an experiment.

| Response or condition | Expected outcome |
| --- | --- |
| `{"option_id":"route-north","evidence_ids":["ev-ridership"],"explanation":"Supports North."}` | Decision; grade separately; evidence-ID match alone is not support |
| Valid shape with `option_id: "insufficient"` | Decision, not refusal |
| Valid shape with `option_id: "Route-North"`, `" route-north "`, `"Route North"`, or `"refuse"` | `invalid_choice` |
| `North.`, free-text refusal, fences, prose around an object, or an array root | `malformed` |
| Missing/extra fields, duplicate keys, wrong types, non-finite numbers, empty option ID or evidence-ID element | `malformed` |
| `{"option_id":"route-north","evidence_ids":[],"explanation":""}` | Decision; adequacy is rubric-dependent |
| Valid known choice citing unknown evidence | Decision with unsupported mention; grade separately |
| `{"option_id":"route-north","evidence_ids":[],"explanation":"I refuse to answer."}` | Decision; explanation retained for grading; `refused=False` |
| Valid-looking JSON with timeout, infrastructure error, or token-limit termination | `timeout`, `error`, or `truncated`, respectively |
| Returned Alpha output with unknown termination | `error` |


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
