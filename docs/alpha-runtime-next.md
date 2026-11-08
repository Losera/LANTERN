# Alpha runtime handoff: evidence and next diagnostic

Human owner: Teammate A / Losera. Session: Codex CLI 0.163.0, Alpha evidence and
diagnostic preparation. Branch: `docs/alpha-runtime-evidence`, worktree
`/tmp/LANTERN-alpha-runtime-evidence`, base
`c6e1808c7242cd3bfa3d01c1901ca880bafd76b4`.

## Evidence and publication

Original files from [tensor job 175757](../evidence/alpha/job-175757/README.md)
and [model job 175794](../evidence/alpha/job-175794/README.md) are retained with
hash manifests. Original source worktrees remain unchanged. These additions
and the dated gate rows need semantic review before commit, push, and a PR.
No model weights or environment binaries belong in Git. Earlier failed-run
snapshots remain in the shared-SSH worktree and must not be removed.

A verified evidence-only local archive is also saved outside `/tmp` at
`/home/losera/LANTERN-alpha-runtime-backup-20261108.tar.gz`, SHA-256
`a8ad53355b210e4f82ac4777c3d6af15ff453dc81512afc528fef045269dcd7f`.
It contains both retained run directories and annotations, with no environment
or weights. This is local recovery protection; off-machine publication remains
pending semantic review.

Verification in this worktree: `python3 tools/test_alpha_diagnostic.py` passed
13 offline tests; the merged helper's 25 tests, application checks and 15
self-tests, bootstrap's 13 self-tests, Bash syntax, Python 3.12 grammar, and
whitespace checks passed. A temporary export included new untracked Markdown
in documentation validation. All 21 copied original files
matched their retention hashes. No actual GPU or installed-library resolver
execution occurred during these local checks.

Issue progress records were updated under the approved plan:
[issue 10 runtime checkpoint](https://github.com/Losera/LANTERN/issues/10#issuecomment-6716175329)
and [issue 20 merge reconciliation](https://github.com/Losera/LANTERN/issues/20#issuecomment-6716174832).
Both issues remain open; no closure was inferred from PR 29's merge.

The model job passed GPU inference, but its log changed requested greedy
generation to sampling. Its original JSON is not an effective-settings receipt.
Do not overwrite either file or present this as a verified greedy observation.

PR 29 merged the shared-SSH helper. Issue 20 needs the merged evidence and a lead
closure decision; issue 10 stays open for the remaining gates. The local main
checkout may lag remote main; do not reset or rebase retained worktrees.

## Diagnostic payload for human review

Review `examples/alpha-inference-diagnostic.sbatch`,
`examples/alpha-inference-diagnostic.py`, and their offline tests. This is a new
ten-minute maximum allocation, one CPU, 32G host RAM, and one MIG 1g.10gb slice.
It reuses the existing job-175794 environment and model without pip, downloads,
quantization, CPU offloading, or model substitution.

Preflight checks every recorded package version and hashes the local model
files against the retained result. The installed Transformers resolver must
reproduce the old override, then resolve explicit greedy settings correctly.
This actual-library check has not run during local mocked testing.

The job then generates twice: the original short smoke prompt, followed by a
synthetic capacity input of exactly 1,024 templated tokens and exactly 128 new
tokens. Forced output length applies only to the capacity probe. It is not a
task answer and cannot count toward the ten-decision gate. The full receipt
records effective settings, token IDs, EOS/cap observations, timings, and
PyTorch allocator peaks. On a failure, previous successful observations and the
current traceback remain in the result. A hard kill or disk failure may leave
only a checkpoint and the Slurm log.

After exact-payload review and human submission approval, run from the local
terminal with an authenticated shared connection:

```bash
cd /tmp/LANTERN-alpha-runtime-evidence
ssh -S "$ALPHA_CONTROL_PATH" -O check -- "$ALPHA_HOST"
bash tools/alpha_submit.sh submit \
  examples/alpha-inference-diagnostic.sbatch \
  examples/alpha-inference-diagnostic.py \
  evidence/alpha/job-175794/inference-result.json \
  evidence/alpha/job-175794/installed-packages.txt
```

Submit once, retain both IDs, monitor every two minutes until a terminal state
or connection failure, then fetch into a new local directory. This preparation
does not submit a job. Do not blindly retry uncertain submission.

Success requires final Slurm `COMPLETED / 0:0` plus `diagnostic-result.json`
showing passed resolver checks and both probes passed. Exact smoke-phrase
matching is a separate observation. Capacity success requires both requested
token boundaries and measured memory. These are diagnostics, not throughput or
task-competence claims.

## Ten-decision gate: waiting for inputs

The lead chose to wait for agreed cases and issue 25's matching/refusal/truncation
rules. The existing fictional fixture is not approved by this handoff. Do not
invent a parser or modify B's fixtures, Kai's adapter, or the runner contracts.

Before implementation/execution, freeze the agreed inputs and their hashes and
declare a ten-attempt schedule, including any repetitions. Every attempted
response stays in the denominator. Do not replace failures until ten successes
appear. Record valid choices, invalid choices, refusals, truncation, and runtime
failures separately; correctness needs the agreed rubric. EOS termination and
budget exhaustion must be distinguished for this Transformers backend.

The future harness will load this same model once and generate sequentially,
with BF16, batch 1, no silent input truncation, at most 1,024 input and 128 output
tokens, and explicit greedy controls. No Alpha runner integration is included.

## Parallel workflow

| Lane | Owner and next action |
| --- | --- |
| Evidence and diagnostic | A: review the evidence, publish after approval, then operate the reviewed diagnostic |
| Cases and matching rules | B: finalize issue 25 and supply the agreed frozen inputs; broader issue 26 remains deferred |
| Local adapter and parser | C / Kai: continue issue 27; implement issue 9 when its matching-rule dependency is settled |

**Correction, 2026-11-08:** the lead transferred #9 and `runner/parsing.py` to
Teammate B; no branch or worktree exists for it yet. Kai retains #27. The lane
table above records the earlier assignment.

Use separate worktrees with one writer per path. Keep evidence-row edits and B's
fallback wording coordinated in `docs/alpha.md`. While the GPU job runs, A can
review already-prepared work; do not create another writer for an occupied
path. Lean publication remains a separate decision, after evidence retention.
