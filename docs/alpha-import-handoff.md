# Alpha importer handoff

The first sections preserve the initial implementation checkpoint. The
structured-response revision and its current state are recorded below.

## Objective and authorization

Implement the importer-only milestone of issue 33 for Teammate A / Losera.
The lead approved the presented plan with "Implement the plan" in this session.
This covers the new importer, offline tests, contract/usage documentation, and
this handoff. It does not transfer ownership of any existing implementation
path. No issue comments or board changes were made; issue 33's body still holds
the earlier pending claim text and needs lead reconciliation.

Session: Codex, Alpha importer implementation; stopped for semantic review.
Branch: `feat/alpha-import`. Worktree: `/tmp/LANTERN-alpha-import`.
Base and HEAD: `6aa11a6234e37d5172e50c1779725092ce3f5889`.
All four additions are untracked and uncommitted; nothing is staged.
The original main checkout's modification to `tools/alpha_submit.sh` is untouched.

## Completed work

- `runner/alpha_import.py`: module command and Python interface for validating
  complete fetched bundles, preserving evidence, converting failures or approved
  interpreted responses, checking dataset compatibility, and skipping duplicates.
- `tools/test_alpha_import.py`: 35 standard-library tests using temporary,
  explicitly synthetic evidence and mocked interpretation where needed.
- [Contract and usage](alpha-import.md): exact version-0 fields, source retention,
  recovery behavior, command, and a runnable synthetic failure example.
- This handoff: evidence, limitations, and next action.

The importer does not edit existing runner types or paths owned by B or C.
All source files stay in the supplied directory. The returned report contains
evidence hashes and source location; callers must retain it with their dataset.
Only inventoried supporting files are hash-checked. An inventory is not an
authenticity attestation, and case-file hashes are not bound by this contract.

## Verification performed

Working directory for all new-work checks: `/tmp/LANTERN-alpha-import`.
Evidence describes the uncommitted additions at the base above.

- `python3 tools/test_alpha_import.py`: passed 35 tests in approximately half
  a second. Covers conversion/export, failures, duplicate and interrupted import,
  complete-bundle refusal, compatibility, path checks, and source preservation.
- `python3 tools/check_app.py --self-test`: passed 15 checker self-tests.
- `python3 tools/check_app.py`: failed because `runner.prompts.render` returns
  a value while the checker still lists it as a refusing seam. The same failure
  reproduced on an untouched `git archive HEAD` in
  `/tmp/lantern-import-base-gtqlnduc`. No checker promotion was attempted.
- `python3 tools/check_bootstrap.py --self-test`: passed 13 checker self-tests.
- `python3 tools/check_bootstrap.py`: passed the tracked base documents. New
  untracked documentation also passed through a temporary export: 23 documents,
  33 shell examples, five JSON examples, and 138 links. The 51 external URLs
  were not fetched.
- The documented JSON pair was extracted into a temporary directory and run
  twice through the real module command: one synthetic error record appended,
  then skipped on repeat. No parser mock was needed for this failure example.
- Both new Python files parsed with `ast.parse(..., feature_version=(3, 10))`.
- `git diff --check` and whitespace checks against each new file passed.

## Limits and next action

Parser and grader remain unimplemented at this base. Completed EOS responses
therefore refuse real import until their separately owned dependencies land.
The successful response/export tests use mocks and establish importer behavior
only. No Alpha connection, job, GPU inference, real experimental dataset,
authentication, external reference access, or oracle conformance was tested.

The destination requires one coordinated writer. Multi-record append is not
transactional: complete partial writes can resume; truncated lines require human
inspection. Stable evidence is a precondition; hash rechecking does not provide
filesystem locking against concurrent or adversarial mutation.

Next: review the semantic diff and contract, reconcile the issue's scope record,
and approve any substantive commit separately. Coordinate parser/grade readiness
and shared CLI work with their existing owners. Full issue 33 remains unfinished:
submission, monitoring, fetch recovery, and live integration are later milestones.

## Structured-response revision: November 8, 2026

The initial importer was committed as
`639b7c47c342798d433e97bb8099cf0ffb54b3db` and published in draft PR 34.
The lead then approved a plan to revise the response contract and handoff,
keeping implementation of prompts and parsing with their existing owners.
This is a contract/docs/test revision, not an implemented JSON parser.

Human owner: Teammate A / Losera. Agent/session: Codex, structured-response
revision, stopped for semantic review. Branch/worktree remain
`feat/alpha-import` and `/tmp/LANTERN-alpha-import`. Revision base and HEAD:
`639b7c47c342798d433e97bb8099cf0ffb54b3db`.

Three tracked files have unstaged changes: this handoff, `docs/alpha-import.md`,
and `tools/test_alpha_import.py`. No runtime implementation, shared contract,
case fixture, prompt/parser path, or issue was edited. The revision is not yet
committed or pushed; draft PR 34 still points to the initial importer commit.

Completed changes:

- Defined a proposed exact three-field model response: `option_id`,
  `evidence_ids`, and `explanation`, carried verbatim inside `raw_output`.
- Documented exact-ID matching, malformed structure, unsupported unknown evidence
  references, received-explanation semantics, and execution-status precedence.
- Added a complete synthetic returned-response wire example with visible IDs and
  format instructions, a matching escaped result, and expected imported fields.
  Retained the runnable failure example; both prompt hashes were recomputed.
- Added explicit parser-result mocks and four importer tests for structured raw
  text/fields, unknown evidence, malformed/invalid outcomes, and valid JSON cut
  off at the token limit. The mock maps fixed fixtures to fixed results; it does
  not parse JSON or implement option-matching rules.

Verification in this worktree on the unstaged revision:

- `python3 tools/test_alpha_import.py`: passed 39 tests.
- `python3 tools/check_app.py --self-test`: passed 15 tests.
- `python3 tools/check_bootstrap.py`: passed 23 documents, 33 shell examples,
  eight JSON examples, and 138 links; 51 external URLs were not fetched.
- `git diff --check`: passed.
- Documentation examples were extracted and checked: both manifest/result pairs
  match recomputed prompt hashes. The failure example imported and skipped on
  retry through the real CLI. The returned-response example refused with the
  real parser, then converted and skipped on retry with an explicit mocked
  parser result. All source bytes stayed unchanged.
- `python3 tools/check_app.py`: retains the known baseline renderer/seam mismatch.
  No checker promotion was made. JSON parser behavior and live Alpha execution
  remain unverified.

### Coordination text for the lead and PR

- **B, #8/#25:** show exact option IDs and evidence IDs in rendered prompts,
  and use the same response-format instructions across compared conditions.
  Reconcile existing bare-option-ID case instructions before running a batch;
  do not silently override or edit the rubric to make JSON work. Reconcile the
  structured contract with the agreed refusal rules and any legacy matching.
- **Kai, #9:** implement strict JSON interpretation in the existing parser,
  preserve raw text and received explanations, retain unknown references as
  unsupported mentions, and apply the agreed refusal/grading rules. A matching
  evidence ID alone must not become a supported tool citation.
- **A, #33:** integrate those separately reviewed dependencies and prepare one
  bounded demonstration with approved cases, a fixed schedule, effective
  generation settings, and EOS policy. Coordinate all shared CLI edits with B
  under #16. Existing ownership remains intact; no coordination messages have
  been posted to other issues by this session.

### Readiness and publication gate

Keep the format provisional until the approved prompt/parser dependencies and
one separately approved, human-authenticated Alpha batch demonstrate preparation,
execution, fetching, real parsing/import, export, and duplicate-free reimport.
Keep every attempted response in the denominator, including failed or malformed
ones; do not rerun until only successes remain. That demonstration, its exact
payload approval, and submission automation are later milestones.

Next: lead semantic review of this revision before another substantive commit.
After approval, append a commit to the existing branch and update draft PR 34
through its current stack, with current head/base SHAs and verification evidence.
Keep issue 33 open and do not rewrite history, change PR bases, or merge.
