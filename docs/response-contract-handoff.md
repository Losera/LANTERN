# Response contract and teammate handoff

Subsequent checkpoint: PRs 38 and 39 merged. The lead requested corrective
review and explicitly selected JSON-only refusal handling. See the
[PR 39 review and corrections](evaluation-rule-review.md) and
[operative evaluation rules](evaluation.md#reading-and-grading-model-choices).
The launch packet and pending-refusal statements below record the earlier
checkpoint; do not use them to launch a duplicate #25 session.

## Decision and boundaries

On November 8, 2026, Teammate A approved the strict JSON response contract and
renderer acceptance target in the assisting session, then requested this plan's
implementation. The [response contract](alpha-import.md#proposed-structured-model-response)
is approved; explicit refusal rules await B's proposal and A's review.

This delivery records that decision and prepares coordination material. It does
not launch a teammate, grant a new claim, change GitHub issues, implement runner
code, or approve an experiment. Tasks 1-3 remain incomplete until B's rules have
been reviewed and integrated and the coordinated target has been communicated.

Strict JSON governs this protocol. Historical free-text suggestions in
[issue 25](https://github.com/Losera/LANTERN/issues/25) remain evidence and history;
they do not authorize label aliases or prose extraction for this response
format. The earlier `North.` smoke response is malformed under this contract.
It does not establish behavior under a future JSON-directed prompt.

The response contains exactly `option_id`, `evidence_ids`, and `explanation`.
The importer still receives the exact response string through `raw_output`.
There is no change to the batch/result envelope, attempt schema, or public
function signatures. Parser and grader implementation remains C's work under
[issue 9](https://github.com/Losera/LANTERN/issues/9).

## Renderer acceptance for existing issue 8

This is the approved target for B's existing renderer work, not a new issue or
permission to edit B's code from this session:

- Show each option's exact ID alongside its label and each evidence item's ID
  alongside its claim. Preserve decision-relevant source and reliability
  information. Do not expose evaluator-only relevance labels as answer hints.
- State the approved JSON shape, exact option matching, field types, and absence
  of fences or surrounding prose. Explain that evidence references use evidence
  IDs. Keep response-format instructions identical across compared conditions.
- Make baseline and unchanged-rerun prompt text byte-for-byte identical for the
  same case, including across rerun indices. Their prompt hashes must agree;
  distinct condition/attempt identities remain in the records.
- Render the approved condition's actual intervention. Identical prompts for
  every arm do not satisfy acceptance. Preserve fixed facts and rubric in a
  framing-only comparison, and retain relevant provenance in any correction.
- Review neutral/framing edits for comparable length using retained prompt text
  and reported lengths. The bounded-case review must approve the wording and
  length criterion before experiment acceptance; this handoff selects neither
  an arbitrary tolerance nor a new cue.
- Return the SHA-256 of the exact UTF-8 prompt text and an `evidence_order`
  matching its displayed evidence order.

Use [issue 8](https://github.com/Losera/LANTERN/issues/8); do not create a duplicate.
Its historical scope fields conflict with its later claim/reconciliation text.
Issue 9 has a similar conflict. A must reconcile the current approved scope
before their later launches, preserving B/C ownership and historical comments.
No GitHub reconciliation has been performed here. Checker ownership stays with
A; rendering is already listed as implemented, so no new promotion is needed.

Renderer acceptance requires deterministic examples covering visible IDs,
identical baseline/rerun inputs, actual interventions, preserved facts and
provenance, displayed evidence order, and exact hashes. Approving synthetic
test examples does not approve the fictional fixture as an experiment. Case
selection and intervention wording remain part of the later bounded-case review.

## Prepared launch packet for B's issue 25

Status: prepared, not sent or launched. Before delivery, A must refresh the issue
and comments, confirm the previous writer/session state, and arrange the lead's
Ready-to-Doing/session record. This session has no authorization to post those
updates. Keep the existing human owner and single-writer scope.

Copy the following only after those launch prerequisites are satisfied:

```text
Read AGENTS.md, README.md, CONTRIBUTING.md, and docs/status.md. Run README
orientation. Read the current issue 25 body and comments and the approved
response contract in docs/alpha-import.md, plus this handoff.

Human owner: Teammate B.
Issue: https://github.com/Losera/LANTERN/issues/25
Approved scope: docs/evaluation.md only, under the existing lead-granted claim.
Branch: docs/answer-matching.
Worktree: A must confirm an available sibling path and current base before
launch. Do not reuse an existing branch/worktree without checking its owner
and retained work. Record the actual path, base/head, and harness/version.
State/session: use the lead's refreshed launch record; do not set it yourself.

Objective: document the approved strict JSON option-matching rule and propose
precise refusal-versus-malformed/truncation rules for A's semantic review.

Transcribe the approved shape and validation rules. Distinguish the historical
free-text suggestions from this operative JSON protocol. Preserve those
historical observations; do not describe JSON-directed compliance as tested.

Propose explicit refusal criteria with expected classifications for standalone
refusal text, ambiguous non-answers, refusal language in explanations, and a
response combining refusal language with a valid option. JSON failure alone
is not refusal. Selecting the valid insufficient option is a decision.
Name any proposed departure from the approved contract rather than silently
adding a sentinel option, field, alias, or new response format.

Document runtime-based truncation: use reported termination, not equality of
completion tokens and the token budget. Preserve timeout > error > truncated
> refusal > malformed > invalid_choice > decision. Alpha token_limit means
truncated; returned output with unknown termination cannot establish a completed
decision and the current importer records it as error. Distinguish these Alpha
envelope rules from local adapter termination signals. Runtime metadata is
supplied by the caller/import path; it is not inferred by parse(raw, case).

Include the classification matrix below. For refusal examples, return proposed
outcomes and reasons for A to approve; do not claim they are already approved.
State that choice readability, rubric correctness, and baseline agreement are
separate measurements. Preserve every attempt and its original raw output.

Run python3 tools/check_bootstrap.py and git diff --check. Return the exact
commands, results, directory, base/head, dirty/untracked state, semantic diff,
classification examples, and unresolved questions.

Do not edit runner/parsing.py, runner/prompts.py, check tooling, or shared
schemas. Do not run a model or submit a job. Do not post messages or issue
comments under this packet. Stop for A's semantic review before committing
substantive work or merging. Leave a handoff in your worktree.
```

## Classification and review checklist

The structural rows below are approved contract expectations. Refusal rows
are B's required proposal, not permission to invent a detector during parsing.

| Scenario | Required expectation or review |
| --- | --- |
| Correct shape, exact known option ID, completed runtime | Readable decision; correctness is separately rubric-defined |
| Correct shape, unknown option ID | `invalid_choice` |
| Valid case-specific insufficient-evidence option | Decision, not refusal |
| Plain `North.`, fenced JSON, or surrounding prose | `malformed`; do not repair or extract |
| Missing/extra fields, duplicate keys, wrong types, non-finite numbers, array root | `malformed` |
| Empty option ID or empty evidence-ID element | `malformed` |
| Case-changed, padded, or label-valued option string | `invalid_choice` if otherwise structurally valid |
| Empty evidence array or empty explanation | Shape remains valid; grading decides adequacy |
| Unknown evidence ID with a known option | Choice remains readable; retain unsupported mention with literal ID as source and null evidence ID |
| Known evidence ID without recorded support | Resolve the evidence item but keep the mention unsupported |
| Supplied evidence order and repeated references | Preserve raw references; do not silently deduplicate the raw output |
| Standalone refusal, ambiguous non-answer, mixed refusal/choice | B proposes exact criteria and expected outcomes; A reviews before implementation |
| Valid-looking JSON with runtime timeout, error, or token limit | Runtime outcome wins; never promote it to a decision |
| Returned Alpha output with unknown termination | Current importer records `error`; preserve raw output and diagnostic |

A reviews B's semantic diff for agreement with the contract, runtime boundaries,
and the matrix. If B proposes new fields, option sentinels, or API changes, bring
the proposal back to A before implementation. General rubric prose is not a
complete deterministic grading algorithm; any remaining grading ambiguity must
stay visible in the later C handoff.

After A approves the rules and the relevant checks pass, integrate them through
the reviewed branch/PR workflow. Only then prepare C's separate parser handoff.
Real parser/import integration and model compliance require later evidence;
this document does not establish either.

## Delivery evidence and next action

Human owner: Teammate A / Losera. Agent/session: Codex, response-contract handoff.
Branch: `docs/response-contract-handoff` in `/home/losera/LANTERN`.
Base/head before edits: `62fa97b0bcc0e6b2fcaa49212c14ee60dcc8b12e`.
The checkout was clean before this documentation work.

Changed files: `docs/alpha-import.md` and this handoff. B's evaluation document,
all runner code, fixtures, and check tooling are unchanged. Issues 8, 9, 22, and
25 were refreshed read-only on November 8, 2026; no issues were changed and no
teammates were contacted.

Verification on the uncommitted documentation tree:

- `python3 tools/check_bootstrap.py`: passed for 24 tracked documents and 139
  links; explicitly skipped this untracked handoff.
- The same checker with `--root` pointing to a temporary export of tracked files
  plus this handoff: passed for 25 documents, 143 links, 33 shell examples, and
  eight JSON examples. All 54 external URLs remained unfetched by that checker.
- `git diff --check` and an explicit whitespace check on both changed documents:
  passed. No files are staged.
- Deterministic Unicode inspection/cleanup of both documents found no changes.
  No style rewrite was needed.

No model, Alpha operation, parser behavior, or renderer experiment was tested.
Application-checker and runtime tests were not rerun for these documentation
changes. The earlier re-entry application check passed at the unchanged base,
with three refusing seams and oracle conformance `NOT_RUN`.

Next action: A reviews this semantic diff before commit or publication. Then A
can arrange B's launch separately. B's refusal proposal, its semantic review and
integration, later case acceptance, and real parser/import verification remain
outstanding. The approval record is prepared locally and is not integrated into
main yet.
