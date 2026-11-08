# Alpha batch implementation handoff

Objective / human owner: implement the approved bounded Alpha workflow;
Teammate A, lead/integrator. Issues: #10 readiness, #33 automation, #22 coordination.

Agent/session: Codex, Alpha batch implementation. No live execution session is
assigned. No GitHub messages, issue transitions or ownership transfers were made.

Branch/worktree: `feat/alpha-batch-resume`, `/tmp/LANTERN-alpha-batch`.
Base and current committed head: `806deea0faf82eef7884ce705bc171aaa7880884`.
Changes are unstaged/uncommitted. Semantic diff review is required before commit
or integration. The original main checkout and other worktrees were not edited.

## Implemented behavior

- Local preparation freezes one case, grading key, approval, twenty prompts,
  exact schedule, settings, input hashes and local implementation hashes.
- Submission persists uncertainty before transport and uses a fixed run ID.
  Recovery reads the existing receipt and never blindly submits again.
- Terminal accounting precedes fetching; partial fetches remain preserved.
  Import/export use the existing interfaces and duplicate protections.
- A standalone supervisor uses fresh bounded worker processes, explicit greedy
  settings and EOS `[151645, 151643]`. Tokenized prompts are checked before
  dispatch. Timeouts kill/reap the worker; undispatched work stays explicit.
- Documentation records the approved twenty-attempt, ten-readable-decision
  threshold and separates correctness from usability and throughput.

Main additions are `runner/alpha_batch.py`, `examples/alpha-batch-executor.py`,
`examples/alpha-batch.sbatch`, their two new test files, this handoff and the
operator guide. Existing edits are limited to the transport helper/tests,
README, gate/status records and shared-contract documentation. No B/C-owned
implementation or fixture was changed, and no existing seam was promoted.

## Verification

Commands and per-command logs are retained locally under
`/tmp/LANTERN-alpha-batch/reports/`. This directory is ignored generated output,
not committed evidence. The new tests mock B-owned case loading, rendering and
interpretation explicitly; they do not claim those dependencies work.

The transport tests use fake SSH/SCP/Slurm. Executor tests import no model/CUDA
libraries and include an actual local subprocess timeout/kill/reap check.
The coordinator exercises the real importer, recorder, analysis and export
against synthetic inputs, with interrupted and repeated imports.

Recorded checks in this worktree:

- `python3 tools/test_alpha_batch.py`: 18 tests passed, about eleven seconds.
- `python3 tools/test_alpha_executor.py`: 12 tests passed, under one second.
- `python3 tools/test_alpha_submit.py`: 28 tests passed, about ten seconds.
- `python3 tools/test_alpha_diagnostic.py`: 13 tests passed.
- `python3 tools/check_bootstrap.py --self-test`: 13 tests passed.
- `python3 tools/check_bootstrap.py`: passed for tracked documents; new
  documents were explicitly reported skipped. A complete exported-tree check
  also passed: 28 documents, 37 shell examples, 8 JSON examples, 159 links;
  55 external URLs were not fetched.
- Bash syntax, Python compilation, CLI help and tracked whitespace checks passed.

The broader importer suite and application checks currently fail on the
inherited malformed example fixture: importer suite 39 tests, with 26 failures
and 17 errors including subtests; application checker self-tests 21 tests with
5 errors. The application lane and case validation also fail there.
Documentation checks alone do not detect the committed conflict markers or
establish an approved grading key.

## Dependencies and next action

For B, preserve the existing claims and address:

- `docs/evaluation.md`: committed conflict markers and duplicated cue prose.
- `fixtures/cases/example-campus-transport.json`: trailing comma and unapproved
  fixture; supply the approved case and requirement-level frozen grading key.
- `runner/cases.py`: cue validation/construction mismatch, including a required
  `Case.cues` field not supplied by the loader. A persistent format change still
  requires lead approval.
- #8 and #9: complete condition-sensitive prompts, exact visible IDs/response
  instructions, strict JSON parsing and the approved grading behavior.

These observations do not transfer ownership or reopen #26. A human launch to B
must carry the corrections; no message was sent on B's behalf. C's adapter
generation evidence and CI work remain separate.

After semantic review, integrate only approved changes, then use a matching
reviewed checkout to prepare actual inputs. Review the generated preflight and
all prompts. Authentication and live submission remain human-operated. Retain
raw allocation/accounting, responses, failures, measurements, import reports
and exports. Do not rerun the already-completed diagnostic or replace failures
to make this gate pass.

## Risks and limits

No real Transformers resolver, CUDA execution, SSH/MFA, Slurm signal/accounting
behavior, task response budget, rubric correctness or framing effect was tested.
The 128-output-token budget may yield truncations on real prompts. SIGKILL or a
node crash can leave an incomplete bundle; preserve it rather than infer missing
attempts. Advisory locks require cooperating local writers; no distributed
concurrency guarantee is claimed. The importer remains a recoverable append
workflow rather than a multi-record transaction.

The run guide requires durable storage outside `/tmp`; this task worktree is
retained here only for implementation review. Preserve it until the reviewed
work has been committed and retained remotely. Lean remote publication and
second-environment design remain deferred.
