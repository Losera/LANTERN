# Alpha importer handoff

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
