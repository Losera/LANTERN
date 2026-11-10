# Current status and handoff

## Next session: resolve the compute-agnostic claim overlap

Three reviewed pull requests are open and green; see the handoff below. The
first action is not code. [Issue 17](https://github.com/Losera/LANTERN/issues/17)
and [issue 68](https://github.com/Losera/LANTERN/issues/68) describe the same
`execution_site` vocabulary decision, and issue 17 holds a claim the lead
granted on November 7, 2026. Until that overlap is resolved, the compute-agnostic
work in issues 69 and 70 cannot start without putting two writers on one
decision, which is the pattern
[issue 22](https://github.com/Losera/LANTERN/issues/22) tracks.

**Alpha cluster access is no longer standing.** The experiment is not blocked by
that, because Alpha never produced a decision: its four retained bundles are a
smoke test, an environment inventory, a `GPU inference ready.` generation, and a
capacity diagnostic, and no `option_id` appears in any of them. Losing Alpha
costs scale, not the experiment. Issues 10 and 33 can no longer reach their
remaining acceptance; issue 37's blocker is dissolved and that issue becomes
current rather than deferred.

A real measurement now exists, and the earlier statement here that every attempt
record was synthetic is superseded. The retained local pilot at
`evidence/local/pilot-2026-11-08/` holds 20 attempts with `synthetic_records: 0`
and `all_records_synthetic: false`, across five arms and four repetitions, and
reports `effect: none_measured`. `runner/cli.py` has a `run` command and
produced it, so issue 16's orchestration blocker is also superseded; what remains
open on issue 16 is named in the handoff below.

That pilot is one case, so it is a valid mechanical null result and **not** a
measurement of framing sensitivity: [evaluation](evaluation.md) is explicit that
repeated runs of one case are not independent new cases. Expanding the case set
and declaring a held-out split is
[issue 76](https://github.com/Losera/LANTERN/issues/76).

Grading is still out of scope and correctness is still `unknown` for every
record: `runner/analysis.py` derives the framing effect from option choices
alone, and `parsing.grade` remains a refusing seam because no frozen grading key
exists. See the [measurement handoff](measurement-handoff.md) for
non-negotiables, traps that have already cost time, and verification commands.

## Board reconciliation and three reviewed changes: November 9, 2026 UTC

**Objective:** reconcile the issue board against the repository
([issue 65](https://github.com/Losera/LANTERN/issues/65)), salvage uncommitted
work from volatile worktrees, and close the one acceptance gap the audit found
genuinely unmet.

**Branches and worktrees:** three task branches cut from `e5e7241`, each one
commit, each pushed, none merged. No worktree was created; work happened in the
primary checkout and `main` was left untouched at `e5e7241`.

| Branch | Head | Pull request |
| --- | --- | --- |
| `fix/alpha-smoke-account` | `6e9657f`, 2026-11-08 21:09 UTC | [PR 78](https://github.com/Losera/LANTERN/pull/78) |
| `salvage/frontend-run-harness` | `2f84fae`, 2026-11-08 21:08 UTC | [PR 79](https://github.com/Losera/LANTERN/pull/79) |
| `fix/dataset-model-identity` | `a5d2a53`, 2026-11-09 03:43 UTC | [PR 80](https://github.com/Losera/LANTERN/pull/80) |

**State:** all three await the lead's semantic review. None was merged. PR 80 is
a contract change and therefore not minimal under
[AGENTS.md](../AGENTS.md) section 7; PR 79 additionally needs a decision rather
than only a review, for the reason recorded under unresolved risks.

### Completed work

**Board reconciliation.** All 15 pre-existing open issues were audited against
the tree at `e5e7241` and 13 dated comments were posted. Nothing was closed, no
claim was granted or changed, and no issue body was edited, because closure,
claims, and scope belong to the lead under
[CONTRIBUTING](../CONTRIBUTING.md#claim-work). Findings:

| Disposition | Issues |
| --- | --- |
| Acceptance fully met; closure recommended | 18, 19 |
| Met with a residual item for the lead | 8, 27 |
| Genuinely not met; keep open | 16 |
| Premise no longer satisfiable after Alpha | 10, 33, 37 |
| Promoted from fallback to primary path | 17 |
| Audited and accurate; no change needed | 2, 3, 9, 11, 21, 22 |

Issue 17 changed meaning without its body changing. Its objective was a
contingency "even if the Alpha readiness gates in #10 do not clear"; with Alpha
access ended, the non-Alpha execution site is the only execution site. Its
stated risk also already resolved in the project's favour, because the pilot is
an off-cluster run and is correctly labelled `execution_site: 'local'`.

Issue 18's body still pointed at PR 45, which is **closed**; its acceptance was
met by PR 53 instead. Following that pointer leads nowhere, which is the specific
failure the reconciliation existed to fix.

**Salvage from volatile storage.** `/tmp` is `tmpfs` on this machine and held 18
of 22 worktrees, so uncommitted work there was one reboot from gone.
`docs/frontend-run-design.md` and `tools/test_frontend.cjs` existed nowhere in
`main` and are retained verbatim in PR 79. A one-line
`#SBATCH --account=rpicourse` addition is in PR 78;
`examples/alpha-smoke.sbatch` was the only sbatch file in `examples/` without
it. Four unretained Alpha probe directories and three sbatch scripts present in
no path in `main` were copied to `~/lantern-salvage-2026-11-08/` with a
provenance README, and their retention is deferred to
[issue 77](https://github.com/Losera/LANTERN/issues/77).

**The dataset identity guard (PR 80).** Issue 16 requires one model and one
runtime per dataset and that a run which would mix either must refuse. No such
guard existed: `cli.cmd_run` checked timeout, run id, label, path resolution,
duplicate attempt ids, and plan consistency, and none of those compared
provenance against the records already in the file.

The failure mode was silent. `runner/analysis.py` pairs attempts across arms and
computes a single `effect`, so two models' attempts in one file would be averaged
into an effect belonging to neither, while every individual record stayed well
formed and every unknown stayed honestly named. That is the same shape as
`e5cf45d`: a change that leaves the lane green while the dataset stops meaning
what it claims.

The guard is in `recording.append_many`, the single chokepoint every dataset
write passes through, so it also covers `alpha_import._record` and any later
compute backend. Placing it there rather than in the command also left
`runner/cli.py` untouched, which issue 16 assigns exclusively to Teammate B. The
rule is not new: `alpha_import` already refused an incompatible model/runtime
identity over five provenance fields, and that tuple now lives in
`recording.IDENTITY` which `alpha_import` re-exports, so the two paths cannot
drift into accepting what the other rejects. PR 80 proposes a matching
"One dataset holds one model and runtime" section for
[contracts](contracts.md); that section is not on `main` until the pull request
merges.

### Changed files

- PR 78: `examples/alpha-smoke.sbatch`.
- PR 79: `docs/frontend-run-design.md`, `tools/test_frontend.cjs`, both added.
- PR 80: `runner/recording.py`, `runner/alpha_import.py`, `tools/check_app.py`,
  `docs/contracts.md`.

### Verification performed

Local runs are recorded per branch rather than claimed for all three, because
the branches received different local coverage. CI ran all three jobs on all
three pull requests.

| Lane | Where run locally | Result |
| --- | --- | --- |
| `python3 tools/check_app.py --self-test` | all three branches | 29 tests OK on PR 80, up from 25; 25 OK on PRs 78 and 79 |
| `python3 tools/check_app.py` | all three branches | PASS, `2 seams refusing`; PR 80 adds `1 mixed dataset identity refused` |
| `python3 tools/check_bootstrap.py --self-test` | all three branches | 15 tests OK |
| `python3 tools/check_bootstrap.py` | all three branches | PASS; 30 documents, or 31 on PR 79 |
| `python3 tools/test_alpha_submit.py` | PRs 78 and 80 | 28 tests OK |
| `test_alpha_import`, `test_alpha_parsing`, `test_alpha_batch`, `test_alpha_executor`, `test_alpha_diagnostic` | PR 80 only | 43, 17, 29, 18 and 13 tests OK |
| `python3 tools/test_local_demo.py` | PR 80 only | 6 tests OK |
| `python3 -m runner.cli validate` | PR 80 only | PASS |
| `git diff --check` | all three branches | clean |
| CI at each pushed head | all three pull requests | `Application lane`, `Documentation lane and diff whitespace` and `Alpha offline suites` all green |

**PR 80's lane is shown to catch its regression rather than merely to pass.**
Neutralising `dataset_identity` in a scratch copy of the tree fails
`check_app.py` with both "a second model/runtime identity was appended to an
existing dataset" and "a refused append still changed the file", and fails the
self-test with four failures. This is the standard PR 50 set after `e5cf45d`.

Both retained datasets pass the new guard unchanged:
`fixtures/attempts/example.jsonl` holds `unapproved-placeholder` and the pilot
holds `qwen2.5:1.5b-instruct`.

### Verification still needed

- Lead semantic review of all three pull requests before any merge.
- PR 78's `--account` directive was never exercised against Slurm accounting;
  Alpha access has ended, so it cannot be. The claim rests on consistency with
  the three sbatch files already on `main`.
- PR 80's guard is exercised against constructed records and the two retained
  datasets. No live `runner.cli run` attempted a model switch mid-dataset,
  because that needs a second installed model.
- Issue 27's last acceptance clause, that a transport or generation failure
  surfaces as `outcome: "error"`, is covered by offline fixtures only. The pilot
  recorded zero failures, so no real failure has been observed.

### Failed approaches and important discoveries

- **A mechanical branch sweep would have destroyed work.**
  `feat/prompt-rendering-handoff` (`f22b89d`) is **not an ancestor of `main`**, so
  that branch ref is the only thing holding the commit; it has no pull request,
  is cited at `docs/measurement-handoff.md:37`, and backs issue 8.
  `wip/grader-draft-b` (`e5cf45d`) **is** an ancestor, so its commit survives
  deletion, but three tracked documents cite it by branch name. `git branch
  --merged` and pull-request state both report these as disposable and are
  actively misleading here. The reliable pair of checks is
  `git merge-base --is-ancestor` plus `git grep` for the branch name over
  `origin/main`. Tracked as [issue 67](https://github.com/Losera/LANTERN/issues/67).
- **Alpha never produced a decision**, established by grepping all four retained
  bundles for `option_id`. This reframes the loss of cluster access from a
  project-threatening event to a scale reduction.
- **Four issues were filed without first auditing the board**, and issues 68
  through 71 partly duplicate issues 17 and 37. Issue 17 already owns the
  `execution_site` vocabulary decision under a granted claim, and issue 37 is the
  design memo that issues 69 and 70 implement. Cross-reference comments are on
  all five. Auditing before filing would have avoided this.

### Unresolved risks

- **PR 79 adds a known-failing test file.** `tools/test_frontend.cjs` scores 2
  pass and 11 fail against the current `frontend/app.js` under node v22.23.2,
  because it was written against the pre-PR-61 internals. No lane runs it, so CI
  stays green, but merging means carrying a red file in the tree. The alternative
  is leaving PR 79 unmerged, in which case its branch is the only copy. This is a
  decision, not a review comment.
- **PR 80 treats an unobserved identity field as a distinct identity rather than
  a wildcard.** A dataset cannot claim one model when a record cannot say which
  model produced it. The consequence is that importing a bundle with unobserved
  provenance into a dataset with known provenance now refuses. This is the most
  contestable choice in the change.
- **Worktree placement is a standing hazard.** 18 of 22 worktrees were on
  `tmpfs`. Today opened with a salvage operation rather than with work because of
  it. The modified `frontend/app.js`, `index.html`, and `styles.css` in
  `/tmp/LANTERN-frontend-real-results` are deliberately preserved nowhere, being
  superseded by PR 61, and will not survive a reboot.
- **The direct-push gap on `main` is still open.** Branch protection requires
  three strict status checks but has `enforce_admins=false` and
  `required_approving_review_count=0`, so the path `e5cf45d` took remains
  available. Tracked as [issue 66](https://github.com/Losera/LANTERN/issues/66).

### Next recommended action

Resolve the issue 17 and issue 68 overlap before any Tier 1 implementation
starts, then act on issue 65's decision list: close issues 18 and 19 or state
their residual items, decide issues 8 and 27, close issues 10 and 33 as no longer
obtainable, and dissolve issue 37's blocker. Issue 16 stays open on the live
`runner.cli run` model-switch verification that PR 80's guard still lacks.

## Alpha batch implementation: November 8, 2026

The lead approved the twenty-attempt schedule, both EOS tokens, a Python
coordinator with a versioned progress journal, fresh per-attempt processes, and
one timed gate batch. Implemented on `feat/alpha-batch-resume`
in `/tmp/LANTERN-alpha-batch`, rebased onto `7c49b34` and merged through
[PR 44](https://github.com/Losera/LANTERN/pull/44) after the lead's semantic review.
See the [operator guide](alpha-batch.md) and [implementation handoff](alpha-batch-handoff.md).

No live job, authentication, model invocation or experiment was performed by
this implementation session. The existing Alpha diagnostics remain retained
observations, not completed decision or throughput gates. The local Lean source
commit `990d953` already exists; its publication destination remains deferred.

The malformed example fixture and the incomplete cue-format change that this
section originally reported were repaired by
[PR 49](https://github.com/Losera/LANTERN/pull/49); `docs/evaluation.md` still
contains committed conflict markers at lines 44-57. B's approved case and frozen
grading key, a condition-sensitive renderer, and an implemented grader remain
dependencies. `prepare` is gated twice over and no experiment can start: the
grading seam refuses first, so it reports "B's parser/grader is not ready", and the
condition-sensitive renderer check behind it would refuse next because
`prompts.render` still ignores its `condition`. These
B- and C-owned paths are unchanged by A's implementation. Do not infer readiness from
the new synthetic workflow tests or #26's closure.

The following sections are dated historical checkpoints. Their earlier pending
diagnostic/publication statements do not supersede the newer evidence or live
GitHub task state.

## Grading seam restored: November 8, 2026 UTC

Objective: return `main` to a green offline lane after `e5cf45d` removed the grading
seam. Committed as `f0324ec` on `fix/restore-grading-seam`, based on
`e5cf45d419a6ce2c5233fe500eb4e656939c6c24`, and merged through
[PR 50](https://github.com/Losera/LANTERN/pull/50) as `7c49b34`.

`e5cf45d` was pushed directly to `main` with no branch, pull request, or review. It
gave `parsing.grade` a body returning `CORRECT` for any in-rubric choice, which
contradicts [evaluation](evaluation.md)'s rule that correctness is requirement-level
satisfaction of a frozen grading key. Its outcome branch was unreachable, sitting
after the in-rubric test, and duplicated `outcomes.classify`.

The breakage was not visible from the diff. `alpha_import._record` and
`alpha_batch.interpretation_ready` both caught `NotImplementedError` from `grade` as
their readiness gate, so the refusal was the only thing keeping ungraded attempts out
of the append-only dataset. Removing it would have let the importer record a
correctness no approved rubric supports. The repair restores the refusal and names the
missing grading key as the blocker. B's draft is preserved on `wip/grader-draft-b` and
linked from issue 9; nothing was discarded.

No grading key, approval record, or rubric artifact exists in the repository, and
`grade(decision, case)` has no parameter that could reach one. Requirement-level
grading therefore remains blocked on a lead contract decision about key access, which
is recorded as the open question for issue 9.

| Lane | Status | Evidence or limitation |
| --- | --- | --- |
| Application self-tests | Passed | `python3 tools/check_app.py --self-test`: 24 tests |
| Application checks | Passed | `python3 tools/check_app.py`: PASS, `2 seams refusing`, 5 implemented callables, 15 modules; `oracle_conformance` still `NOT_RUN` |
| Parser/import integration | Passed | `python3 tools/test_alpha_parsing.py`: 17 tests OK, 2 skipped as `requires PR #44 in combined checkout`; `python3 tools/test_alpha_import.py`: 39 tests OK |
| Alpha helper and diagnostics | Passed | `python3 tools/test_alpha_submit.py` and `python3 tools/test_alpha_diagnostic.py`: OK |
| Case validation | Passed | `python3 -m runner.cli validate`: PASS |
| Documentation lane | Passed | `python3 tools/check_bootstrap.py --self-test` OK; `check_bootstrap.py`: 26 documents, 154 links; 56 external URLs not fetched |
| Whitespace | Passed | `git diff --check` clean |
| CI at the merged head | Passed | [Run 42483044032](https://github.com/Losera/LANTERN/actions/runs/42483044032): application, documentation/whitespace and Alpha helper lanes all green at `f0324ec` |
| Grading correctness | Not established | No frozen key exists; the seam refuses rather than grades |
| Renderer condition-sensitivity | Still broken | `prompts.render` ignores its `condition`; unchanged by this branch |
| `docs/evaluation.md` conflict markers | Still present | Lines 44-57 from `806deea`; a separate repair |

These lanes establish that the skeleton coheres and the seam refuses again. They
establish nothing about Alpha connectivity, model behaviour, rubric correctness,
design-oracle conformance, or reduced bias.

This is the sixth occurrence of the pattern [issue 22](https://github.com/Losera/LANTERN/issues/22)
tracks. The first four are recorded in this file; PR 46's zero-review merge is the
fifth and is recorded on that issue. The path claim
held; the branch-and-review step did not. Three of the suites that detect this class
of regression -- `test_alpha_parsing.py`, `test_alpha_import.py`, and
`test_alpha_diagnostic.py` -- are not in CI, which is why the push landed green at the
PR gate and red only on `main`. All three now run in CI, together with the two
coordinator suites PR 44 added, under the `Alpha offline suites` job. Reapplying
`e5cf45d`'s `grade` to a scratch copy of the merged tree fails
`test_alpha_parsing.py` and `test_alpha_import.py`, so the lane is shown to catch
this regression rather than merely to pass.

## Alpha runtime evidence: November 8, 2026 UTC

This dated observation supplements the historical checkpoints below; it does not
declare the Alpha readiness task complete. [Issue 10](https://github.com/Losera/LANTERN/issues/10)
remains open for decision-validity and throughput evidence.

- [Job 175757](../evidence/alpha/job-175757/README.md): native Python 3.12.3,
  PyTorch 2.9.1+cu126, CUDA tensor calculation on the allocated MIG slice returned
  14.0. NumPy absence was a warning rather than a failed calculation.
- [Job 175794](../evidence/alpha/job-175794/README.md): pinned
  Qwen/Qwen3-4B-Instruct-2507 at
  `cdbee75f17c01a7cc42f958dc650907174af0554`, BF16, batch 1, generated the exact
  phrase `GPU inference ready.` in 3.8306 seconds. Peak PyTorch reserved memory
  was 8,111,783,936 bytes on a slice reporting 10,468,982,784 bytes.
- Both jobs' `COMPLETED / 0:0` accounting was human-reported. Raw logs, receipts,
  package reports, and source hashes are retained; a separate raw accounting
  capture remains to be added.
- Important correction: the model log reports generation defaults changed to
  sampling, while the JSON records the requested greedy configuration. Preserve
  both unchanged and do not claim verified greedy decoding for this run.
- Next diagnostic: enforce and test effective greedy settings, repeat the smoke
  response, and measure the 1,024-input/128-output capacity boundary using the
  existing environment and weights. No new installation or download is needed.
- Ten decisions remain blocked on agreed cases and matching/refusal/truncation
  rules. Full-budget fit, task competence, sustained throughput, and Alpha
  runner integration remain untested.

Evidence and diagnostic preparation are on `docs/alpha-runtime-evidence` in
`/tmp/LANTERN-alpha-runtime-evidence`; semantic review is required before commit.
This work does not change the separately approved local Ollama model or Kai's
adapter claim.

## Integrated bootstrap: November 7, 2026

Objective: bootstrap LANTERN's context transfer and engineering collaboration.
The lead approved the semantic diff and requested commit and push in the
[approval record](https://github.com/Losera/LANTERN/issues/1#issuecomment-6712182230).
The bootstrap was committed on `docs/bootstrap` as
`da4df1eadc6bff3ad501e6a7cccedf12888bb420`, based on
`ff51b9f2e8542f44ab80774d462f8cc766fc358b`, then submitted through `gh stack`.
[PR 4](https://github.com/Losera/LANTERN/pull/4) merged into `main` on November 7,
2026 at 20:16:31 UTC as `79d7a4e1a3fce7f719cfeb3bc588e11e44b0f3e6`.
Git history and the live PR record confirm integration. This dated handoff
supersedes the pre-commit checkpoint; GitHub issues retain live task state.

Initial inspection found a clean local `main` at `ef077f3` and newer GitHub main
at `ff51b9f`. After fetching and inspecting history, main was fast-forwarded
safely. Both trees contained only `Init README`. No existing project orientation,
implementation, or test lane was present. The research checkout was clean at the
[pinned snapshot](research.md#source-manifest).

The integrated bootstrap contains policy, context, operational/evaluation boundaries, a
contributor walkthrough, issue/PR templates, two development skills, and an
offline checker. No application model, framework, service, schema, environment,
or tool contract is selected. See [approved and unresolved decisions](project.md).

## Verification record

This table retains implementation-session evidence. The
[PR verification record](https://github.com/Losera/LANTERN/pull/4) also records
offline checker, skill validation, and whitespace checks at committed head
`da4df1e`. Those records do not establish human or runtime acceptance.

| Lane | Status | Evidence or limitation |
| --- | --- | --- |
| Repository/research orientation | Observed | Git status/history/worktrees; source snapshot and local notes inspected |
| Local harness availability | Observed | Pi 0.81.1; Codex 0.163.0; Claude 2.1.241; gh 2.102.1; gh stack 0.1.0; version/help inspection only |
| Offline checker self-tests | Passed | `python3 tools/check_bootstrap.py --self-test`: ten temporary-fixture tests, including malformed data, broken links, snapshot omission, and nonexecution of examples |
| Bootstrap links/metadata/JSON/Bash syntax | Passed | `python3 tools/check_bootstrap.py`: 14 Markdown documents, 80 links, 21 shell examples, one JSON example; 38 external URLs not fetched |
| Skill package validation | Passed | skill-creator quick_validate.py run separately on both packages; structural validation only |
| Prose Unicode audit | Passed | 14 Markdown files inspected; zero suspicious characters; quoted policy/license retained |
| Pinned local source references | Passed | Nine unique research-file URLs matched actual files at snapshot 4ffd86b via git cat-file; this does not prove remote access |
| Recorded Lean summary | Matched stored report | 57/14 fixtures, 50,000 states, 282,411 transitions, truncation and application NOT_RUN checked; no Lean replay |
| Git command rehearsal | Passed in disposable fixture | Staged/unstaged/untracked files distinguished; dirty removal refused without data loss; clean removal succeeded; no human/harness/claim behavior established |
| Bootstrap semantic review | Approved by lead | Issue 1 records approval of the exact bootstrap diff before commit; separate teammate source review remains open in issue 2 |
| Diagram rendering | Passed local preview | Chromium 148 with pinned Mermaid 12.3.0 browser module produced SVG; screenshot inspected for readable labels and boundaries; GitHub's renderer not separately tested |
| Beginner walkthroughs | Not run | Both teammates must perform the contributor walkthrough |
| Docs-only versus skill task comparison | Not run | Requires observed task attempts and help/omission counts |
| Cross-harness skill behavior | Not run | Explicit reading is documented; no provider requests or interoperability test |
| External references | Partial | Planning inspected primary docs; private vault returned 404 and allocation page was inaccessible |
| Alpha access | User-reported | SSH/MFA report only; no connection attempted here |
| Alpha inference/serving/networking/Pi subject | Not tested | No allocation, GPU inference, endpoint, tunnel, or Pi experiment |
| Lean | Recorded evidence only | Stored offline model report inspected, not replayed; application conformance NOT_RUN |

Documentation validation does not prove Alpha connectivity, harness
interoperability, application correctness, or reduced bias.

## Application skeleton checkpoint: November 7, 2026

Objective: the initial backend and frontend structure for the application.
Branch: `feat/app-skeleton`; worktree: sibling `LANTERN-app`.
Base: `79d7a4e1a3fce7f719cfeb3bc588e11e44b0f3e6`.

The lead approved four gated decisions before implementation: a zero-dependency
static frontend, a generated file export rather than a service, contracts plus
deterministic parts rather than pure structure, and provisional version-0
formats. No model, revision, environment, rubric, or tool contract is approved,
and none is selected here. See [proposed formats](contracts.md).

Implemented because deterministic and architecture-free: condition expansion,
the failure taxonomy, append-only recording with explicit unknowns, oracle
trace emission with strict field sets, paired analysis, and the export
projection. Left as seams that raise rather than return: prompt rendering,
output parsing and grading, the model adapter, and tool execution.

The runner emits traces in the design oracle's vocabulary and never decides
acceptance. The oracle's handoff rules out a Python state machine written to
claim conformance, so `oracle_conformance` stays `NOT_RUN`.

| Lane | Status | Evidence or limitation |
| --- | --- | --- |
| Application checker self-tests | Passed | `python3 tools/check_app.py --self-test`: 15 tests; each deliberately breaks one rule and confirms the lane reports it |
| Application skeleton checks | Passed | `python3 tools/check_app.py`: 14 modules imported, 22 required files, 5 seams refusing, 5 malformed events rejected, 11 page fields cross-checked against the export |
| Bootstrap documentation checks | Passed | `python3 tools/check_bootstrap.py`: 15 documents, 87 links, 22 shell examples, 3 JSON examples; 38 external URLs not fetched |
| Emitted trace judged by the oracle | Observed, one trace | `python3 tools/check_app.py --oracle .../oracle` accepted one trace built from the synthetic fixture, and its coverage verdict matched the runner's independently computed pending attempt. No injected faults; the oracle is not an independent checker of this Python; this is not a conformance lane |
| Frontend rendering | Passed local preview | Chromium 148 headless rendered `frontend/index.html` from a `file://` URL; screenshots inspected in dark and light palettes, and a scratch copy driving one row click confirmed the attempt detail, provenance, and never-measured fields render. Other browsers not tested |
| Design-oracle conformance | Not run | No comparison of exported traces, receipts, and final simulated ledger against the oracle under dropped completions, late results, and retries |
| Prompt, model, parser, tool seams | Not run by design | Each raises `NotImplementedError`; no model was executed by any command |
| Alpha inference, serving, networking, Pi subject | Not tested | Unchanged by this branch |
| Rubric, case format, cue inventory | Not agreed | Team agreement still required before parallel product work |
| Semantic review of this branch | Pending human review | Required before commit and before any merge |

The example case is fictional and says so in its `status` field. Every record
in `fixtures/attempts/example.jsonl` carries `synthetic: true`, the checker
refuses a line that does not, and the export refuses to label an all-synthetic
dataset as anything else. No model produced any of it.

A coherent skeleton can still measure the wrong thing. These lanes establish
module coherence, seam refusal, the counting rules, export/page agreement, and
an offline frontend. They establish nothing about the experiment's conclusions.

## First bounded work and ownership

Teammate A is the lead/integrator and owns integration, instructions,
project/status decisions, shared contracts, skills, and check tooling.
Teammate B owns context, evidence, and evaluation review; Teammate C owns the
contributor walkthrough and collaboration checks. All three slots are filled;
see the roster for the mapping. Claims are still granted per issue.
See the [team roster](project.md#team-responsibility) and
[messageboard workflow](../CONTRIBUTING.md#teammate-ownership-and-messageboard).

One authorized implementation session prepared the bootstrap, followed by lead
semantic approval and integration. That does not imply either teammate performed
a walkthrough or completed the separate context review.
Issues track the remaining acceptance work.
The single dispatcher and approved path claims prevent simultaneous edits.

- [Issue 1: lead semantic review and integration](https://github.com/Losera/LANTERN/issues/1).
- [Issue 2: context/evidence review, Teammate B](https://github.com/Losera/LANTERN/issues/2).
- [Issue 3: beginner/harness walkthrough, Teammate C](https://github.com/Losera/LANTERN/issues/3).

Issue 1's review and integration objective is complete through PR 4. Its handoff
is reconciled to Done; the GitHub issue remains open for the lead's closure
decision. Issues 2 and 3 remain open, Ready, and unassigned with no claim granted.
No new teammate claim or acceptance result is established by this reconciliation.
At implementation, issue 2's title/body still used the old provisional teammate
A designation and issue 3 used B. Their migration to B/C and slot labels is
prepared for rollout after this reviewed documentation reaches `main`.

## Board reconciliation and merges: November 7, 2026

Objective: reconcile the issue board against the repository's actual state and
integrate the two reviewed documentation changes. `main` is `59b18e6`.

| PR | Head | Merge commit | Merged, UTC |
| --- | --- | --- | --- |
| [PR 14](https://github.com/Losera/LANTERN/pull/14), checker reads Git-tracked Markdown | `0eccc2a` | `f33d1e5` | 22:56:37 |
| [PR 23](https://github.com/Losera/LANTERN/pull/23), roster correction | `8498751` | `59b18e6` | 22:59:04 |

| Lane | Status | Evidence or limitation |
| --- | --- | --- |
| Documentation self-tests, merged tree | Passed | `python3 tools/check_bootstrap.py --self-test`: 13 tests, up from ten; PR 14's three new tests assert that an untracked file is skipped and named, a tracked file still errors, and a tree without Git data is scanned whole |
| Documentation checks, merged tree | Passed | `python3 tools/check_bootstrap.py`: 16 documents, 101 links, 27 shell examples, 3 JSON examples; 45 external URLs not fetched |
| Application self-tests | Passed | `python3 tools/check_app.py --self-test`: 15 tests |
| Application checks | Passed | `python3 tools/check_app.py`: PASS; `oracle_conformance` still `NOT_RUN` |
| Alpha helper offline tests | Passed | `python3 tools/test_alpha_submit.py`: 18 tests; no real transfer, MFA, allocation, or inference |
| Whitespace | Passed | `git diff --check` on the merged tree |
| Lean design oracle under version control | Observed | 16 sources committed in the separate `lantern-formal` repository as `990d953`; `source_digest()` recomputes to `20c0e66a...957588c1`, matching `HANDOFF.md` and the stored report, so the commit is the verified revision. No remote; no off-machine copy. Proofs not replayed |
| Semantic review of the merged documentation | Approved by lead | Both PRs were merged on the lead's explicit instruction |
| Experiment result | None | Every record in `fixtures/attempts/` remains `synthetic: true`; the export's `effect` reads `none_measured` |

These lanes were run on the merged tree rather than on either branch. They
establish that the documentation subset validates and the skeleton still coheres.
They establish nothing about Alpha connectivity, model behaviour, application
correctness, design-oracle conformance, or reduced bias.

Repository state recorded at the same time: the `main` checkout is clean, and an
uncommitted `shfmt` reformat of `tools/alpha_submit.sh` that sat in it was
reverted after a patch and a file copy were retained outside the repository. Two
scratch briefs were moved out of the repository root, which is what had been
failing the documentation lane before PR 14. Two worktrees remain in use:
`/home/losera/LANTERN-checker` and `/tmp/LANTERN-alpha-shared-ssh`, the second
holding uncommitted SSH connection-reuse work now tracked as issue 20.

### Decision rules landed outside the review path

`32c3938` added the "Decision Rules" section to [evaluation](evaluation.md),
committed directly to `main` without a branch, pull request, or semantic review.
It is inside issue 7's path claim and is its owner's own issue, so nothing was
disturbed and the merges above were applied on top of it.

This is the fourth concurrent-writer occurrence this day, after the three-way
rewrite of this file, PR 13 merging while issue 10 was unclaimed, and the
`tools/alpha_submit.sh` double edit. The path claim held each time; the
branch-and-review step did not. Issue 22 carries the path-exclusivity map and
this record.

The section supplies the rubric wording, which is the first of issue 7's three
parts. The option vocabulary and the declared-irrelevant cue inventory are not
written, and `fixtures/cases/example-campus-transport.json` is unchanged, so that
issue's acceptance is not met and its state is unchanged. Issue 8 moved to Ready
because its owner holds both issues; issue 9 remains blocked on the option
vocabulary alone, because a parser written against a guessed option set would
misclassify valid choices.


## Next actions and unresolved gates

The bootstrap no longer awaits its original commit, publication, or merge.
The lead can close issue 1 and agree actual owners and claims for issues 2 and 3.
The remaining acceptance work is source review, the beginner
task/claim/diff/verification/handoff walkthrough, and observed harness behavior.
This ownership and handoff update does not start those tasks.

Before product implementation, agree the rubric, case/result contracts,
model/environment, and first runtime slice. Verify Alpha allocation and inference
separately. Confirm organizer rules, source accessibility, and prepared-artifact
eligibility. No test claim should cross these evidence boundaries.

## Discoveries and recovery

Sandbox network requests could not resolve GitHub; an authorized outside-sandbox
fetch succeeded. A sandbox auth check falsely appeared invalid; the authorized
outside-sandbox check confirmed the configured account. No credential change was
needed. The connected integration could read GitHub but returned 403 for issue
creation; the authorized authenticated CLI created issues 1-3 instead. No tools
were installed or cluster state changed.

At reconciliation, `main` was clean at `79d7a4e` after fetching. The original
sibling `LANTERN-bootstrap` worktree was also clean at `da4df1e`; its tracked and
untracked status showed no unfinished draft. It remains in place. Ignored files
were not inspected, so this is not a cleanup or removal decision.

The merged bootstrap changed README, AGENTS/CLAUDE instructions, CONTRIBUTING, third-party
notices, context documents including this status note, two GitHub templates,
two skill entrypoints, and the checker. The original draft is retained in Git;
the earlier implementation and approval comments remain dated historical records.

The earlier handoff reconciliation changed `docs/status.md` and issue 1's handoff
metadata. Its uncommitted documentation edit was carried from
`docs/reconcile-handoff` in `/tmp/LANTERN-handoff` into the combined ownership
change below. The original worktree is retained unchanged as a superseded edit;
continue editing only in the new worktree.

Verification on that earlier reconciliation tree (HEAD `79d7a4e`, only `docs/status.md`
modified): `python3 tools/check_bootstrap.py --self-test` passed all ten tests;
`python3 tools/check_bootstrap.py` passed 14 documents, 83 links, 21 shell
examples, and one JSON example, without fetching 40 external URLs;
`git diff --check` passed. The Unicode pass found no characters to remove or
replace. The semantic diff was inspected. No runtime or behavioral acceptance
checks were added or performed.

## Teammate ownership implementation handoff

This is the dated preparation checkpoint before commit and rollout. Check Git
and live issues for later publication, migration, or session changes.

- Human owner: Teammate A - Losera.
- Agent/session: Codex; teammate-ownership session; stopped at the review handoff. Harness version not recorded in this session.
- State: implementation prepared; awaiting the lead's semantic review before commit or integration.
- Approved scope: task template, contributor guide, and project/status ownership sections, including the pending handoff edit, as requested by the lead.
- Branch/worktree: `docs/teammate-ownership` in `/tmp/LANTERN-teammate-ownership`.
- Base/HEAD: `79d7a4e1a3fce7f719cfeb3bc588e11e44b0f3e6`; the four documentation/template edits are uncommitted.
- Completed: separate owner/session fields, A/B/C roster, current-body versus dated-comment guidance, session replacement rules, and slot-label semantics.
- Rollout: proposed issue bodies and metadata are in `/tmp/lantern-teammate-rollout`; no ownership migration or teammate labels have been applied to GitHub yet.
- Verification: `python3 tools/check_bootstrap.py --self-test` passed ten tests; `python3 tools/check_bootstrap.py` passed 14 documents, 87 links, 21 shell examples, and one JSON example, without fetching 40 external URLs; `git diff --check` passed. Read-only assertions passed for all seven template fields, the A/B/C roster, all three proposed issue bodies, preserved states/assignees/labels, and pending B/C claims. Unicode inspection/cleanup found no changes across the four edited files and four rollout Markdown artifacts.
- Remaining acceptance: lead semantic review, approved commit/PR/main integration, then issue/label migration with readback. No runtime or beginner/harness behavior is established by documentation checks.
- Next action / blocker: Losera reviews the combined semantic diff. Preserve issue 1's open/Done state, issues 2/3's open/Ready/unassigned state, all claim gates, and historical comments during later rollout.

The original handoff worktree and Claude's `LANTERN-app` worktree remain in
place. Main's untracked `init.md` and the application skeleton are outside this
change. No paths in either have been edited by this session.

The checker deliberately supports a small Markdown subset. It rejects unsupported
reference/HTML links rather than promising full Markdown validation. Source
interpretation by teammates, teammate diagram comprehension, and the
teaching/task skill behavior still require the named human/behavioral checks.
No independent review or beginner result is implied by bootstrap integration.
