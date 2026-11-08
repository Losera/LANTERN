# PR 36 adapter-check revision

## Objective and state

Human owner: Teammate A / Losera. Session: Codex, PR 36 offline adapter check,
stopped for semantic review. The lead requested this update after review found
that the checker still expected the merged local adapter to refuse execution.
Scope: `tools/check_app.py`, `docs/contracts.md`, and this verification handoff.
No runner implementation is changed by this revision.

Worktree: `/tmp/LANTERN-checker-adapter-offline`.
Branch: `fix/checker-adapter-offline`, based on PR 36 head
`b3430b876b3e957e1d45af8e8f818a83297180c4`.
The original `/home/losera/LANTERN-render-promotion` checkout is untouched.

An uncommitted, conflict-free merge of main at
`e5712ba0f68d31a11946b08b5da201948b3490ab` brings in the already-merged adapter
and PR 34 importer. Those five upstream files are staged by the merge; this
revision's checker and contract changes are unstaged, and this handoff is new.
The two parent commits are retained; no history was rewritten. PR 36 still
points to its original head until semantic approval and publication.

## Changes to review

- Remove `UnapprovedAdapter.generate` from the refusing seams and check its real
  implementation with synthetic HTTP responses instead. Three seams remain:
  parsing, grading, and tool execution. Four implemented callables are checked.
- Exercise success, output-limit truncation, API-declared error, and transport
  failure without a daemon. Validate approved request settings, raw output,
  local provenance, token counts, unknown memory usage, and retained errors.
- Add mutation tests that catch a stubbed adapter, restored refusal, lost
  truncation, and lost error body. Add a whole-lane regression proving no socket
  or connection is opened; retain the existing no-subprocess check.
- Update the contract table and describe the mocked adapter lane. Preserve the
  warning that prompt rendering still ignores conditions and omits option IDs.

## Verification on the uncommitted combined tree

Working directory: `/tmp/LANTERN-checker-adapter-offline`.

- `python3 tools/check_app.py --self-test`: passed 21 tests.
- `python3 tools/check_app.py`: passed; three seams refusing, four implemented
  callables, 15 imported modules, oracle lane `NOT_RUN`.
- `python3 tools/test_alpha_import.py`: passed 39 tests against the combined
  importer, adapter, and checker tree.
- `python3 tools/check_bootstrap.py --self-test`: passed 13 tests.
- `python3 tools/check_bootstrap.py`: passed the tracked documents. A temporary
  export including this untracked handoff passed 24 documents, 33 shell examples,
  eight JSON examples, and 138 links; 51 external URLs were not fetched.
- `git diff --check` and `git diff --cached --check`: passed.
- New-file whitespace, documentation Unicode audit, and Python 3.10 grammar
  parsing passed. This is not a Python 3.10 runtime execution.

No real HTTP connection, model generation, Alpha operation, oracle conformance,
or experiment was performed. Synthetic response checks establish adapter wiring
and failure preservation, not installed model identity or runtime competence.
Unchanged renderer defects and unimplemented parser/grader still block a real
comparison; a passing checker is not experimental readiness.

## Next action

Review the semantic diff before committing the merge and revision. After
approval, publish the resulting descendant to PR 36's existing remote branch
without force-pushing, changing its base, converting its standalone PR into a
stack, or merging into main. Refresh its title, current SHAs, verification, and
limitations. The original PR description's four-seam/16-test claims are obsolete
for this revision; the revision has three refusing seams and 21 self-tests.
