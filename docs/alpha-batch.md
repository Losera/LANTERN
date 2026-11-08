# Frozen Alpha batches and recovery

Teammate A approved this design on November 8, 2026. The implementation requires
semantic diff review before commit or integration. No live run is established
by the offline tests. B retains the case, grading key, renderer, parser, grader
and CLI claims; C retains the local model adapter and CI claims.

## Prepare and review

### Explicit fictional-case pilot

The lead approved an ungraded Alpha pilot on November 8, 2026. Use `--pilot`
to run the fictional transport case without a grading key. A pilot retains
real model responses with `synthetic: false`, but it does not establish a
result on an approved real-world case. Correctness remains `unknown`.

```bash
python3 -m runner.alpha_batch prepare --pilot \
  --cases fixtures/cases \
  --approval /path/to/pilot-approval.md \
  --host YOUR_USERNAME@alpha1.empireai.edu \
  --out /path/to/durable/new-pilot
```

Pilot mode requires a non-empty written approval and refuses `--grading-key`.
It freezes `purpose: "pilot"` in the existing version-0 batch envelope. The
executor keeps the same pinned model, twenty-attempt schedule and resource
bounds. The coordinator imports the matching pilot bundle without calling
grading and labels its export as a fictional-case pilot. Standalone import
requires its own explicit `--pilot` flag. Each pilot dataset accepts only its
own run identity; do not combine it with local Ollama or experimental data.

Submission still requires review of the exact frozen preflight and its hash.
Use the existing `submit` and `resume` commands below. Preserve malformed or
truncated output instead of changing the parser or replacing attempts. Unlike
the local Ollama path, this Alpha executor has no JSON decoding constraint.
The 128-token output budget may prevent complete JSON responses.

### Default experimental mode

Use Python 3.10 or newer on Linux or macOS, Bash, and existing SSH access.
The coordinator uses `fcntl` advisory locks and is not supported by native
Windows Python. Authentication remains human-operated. Keep the run directory
in durable storage, outside this checkout and outside `/tmp`.

Prepare only after B's baseline repairs and experimental inputs are reviewed.
The case directory must contain one approved case, not the fictional example.
Supply the frozen requirement-level grading key and the lead's written
approval record. These files retain human decisions; their presence and hashes
do not independently prove approval or the correctness of a grading key.
Review that the integrated grader applies that key unchanged.

```bash
python3 -m runner.alpha_batch prepare \
  --cases /path/to/approved-cases \
  --grading-key /path/to/grading-key.md \
  --approval /path/to/approval.md \
  --host YOUR_USERNAME@alpha1.empireai.edu \
  --out /path/to/durable/new-run
```

Preparation performs no network or model operation. It checks the owned
interfaces with a synthetic parser/grader probe and checks basic condition
differences, then retains the case, key, approval, exact prompts, SHA-256 hashes,
executor/job sources, local runner/helper source hashes and policy. Submission
and recovery refuse a changed local implementation; preserve the matching
reviewed checkout for this run. These checks do not establish experimental
validity: inspect all five prompt variants for unchanged facts, preserved source
authority, appropriate framing, and comparable neutral-edit length.

Review `inputs/preflight.md`, `inputs/batch.json`, and every copied input.
Preparation prints the preflight hash. Use that exact value after review:

```bash
python3 -m runner.alpha_batch submit \
  --run /path/to/durable/new-run \
  --approved-preflight-sha256 REVIEWED_PREFLIGHT_SHA256
```

This is a human-operated live command. It uploads only the frozen inputs and
submits once through the existing helper. The host is retained in the journal;
`ALPHA_CONTROL_PATH` can reuse a connection the human authenticated as described
in the [transport guide](alpha-automation.md#reuse-an-authenticated-connection).
The job script retains the previously observed environment/model paths and
event allocation settings. Review their current applicability before submitting.
There are no installations, downloads, fallback models or automatic retries.

## Fixed experiment and measurements

One case runs baseline, unchanged rerun, neutral edit, framing and correction,
four repetitions of each, in that order. The schedule is twenty attempts, never
an adaptive search for ten successes. All twenty must start and at least ten
must yield readable decisions to pass. Non-decisions and timeouts remain visible;
correctness is a separate rubric result. An incomplete schedule fails the gate.

The pinned Qwen3 model/tokenizer uses BF16, greedy decoding with model defaults
disabled, seed 1, and explicit EOS `[151645, 151643]`. Each prompt must fit 1,024
tokens after the chat template is applied. Oversized inputs refuse the whole
batch before dispatch; none is truncated silently. Output is bounded at 128
tokens. EOS at the final token counts as completion, even at that boundary.

The supervisor launches one process per attempt and allows sixty seconds for
loading and generation combined. On timeout it kills and reaps the worker
process group before proceeding to the next scheduled attempt. It never retries
the same attempt. The job requests thirty minutes on one existing 10 GB slice.

Package versions and snapshot hashes are checked before dispatch. Retained
receipts include tokenized inputs, effective generation configuration, generated
token IDs, raw text, loading/generation times and observed device information.
The immutable importer envelope still hashes the rendered user prompt; the
tokenized receipt separately preserves the exact model input after chat framing.

Throughput includes preflight, process startup and repeated model loading.
Per-attempt loading and generation times are available separately. Reserved and
allocated PyTorch memory are observations, not total device-memory use. No
minimum throughput or framing effect is promised.

## Resume without resubmitting

Run the following command when ready to inspect progress. Each invocation makes
one observation; it does not background-poll or resubmit:

```bash
python3 -m runner.alpha_batch resume --run /path/to/durable/new-run
```

`progress.json` records submission intent before any transfer. If submission
disconnects, resume reads the existing remote `submission.txt`; an absent or
invalid receipt leaves the submission uncertain. Inspect that run and your
queue manually. Never remove the journal to force a second submission.

Queue disappearance does not establish completion. Resume requires terminal
root-job accounting and no queue entry for that job. The helper queries the
user's queue rather than a possibly purged job ID. Missing records, query
failures or contradictory observations stop progress without changing the job.
Transport stdout/stderr and return codes are retained per operation.

Once terminal, fetch uses a new directory. A failed or interrupted transfer
leaves its partial directory untouched; the next resume selects another.
After a complete fetch, every regular file is hashed and subsequent recovery
refuses changed retained evidence. Symlinks are refused. No source evidence is
rewritten by import or export.

The importer requires one terminal result for every scheduled attempt.
Catchable supervisor termination records current failure and undispatched work.
A node crash or uncatchable kill may leave only a prefix: preserve it and report
the incomplete bundle. Recovery does not infer missing attempts, synthesize
results, or submit replacements.

Valid results import into this run's dedicated `dataset/attempts.jsonl`.
Repeated import skips identical records and refuses conflicting records or
incompatible model/runtime identities. An interrupted append may leave complete
records that resume can skip; a partial final line requires human inspection.
No dataset repair is automatic. One run lock excludes competing coordinators;
do not run standalone importers against that dataset concurrently.

`dataset/` holds the import report, summary, source hashes and `export.json` plus
`export.js`. Completion means conversion finished; inspect `gate_passed`, errors,
correctness and throughput separately. A failed experiment is retained evidence.
New settings, prompts, cases or schedules require a new reviewed run directory.

## Offline acceptance

```bash
python3 tools/test_alpha_batch.py
python3 tools/test_alpha_executor.py
python3 tools/test_alpha_submit.py
python3 tools/test_alpha_import.py
python3 tools/check_app.py --self-test
python3 tools/check_app.py
python3 tools/check_bootstrap.py --self-test
python3 tools/check_bootstrap.py
git diff --check
```

Coordinator tests use fake SSH/SCP/Slurm and explicitly mocked B-owned case,
renderer and interpretation interfaces. Executor tests exercise supervision and
termination rules without importing CUDA/model libraries. Those tests do not
establish GPU generation, the actual Transformers resolver, allocation access,
MFA behavior, rubric correctness, framing effects or oracle conformance.

Real acceptance needs the reviewed frozen batch, retained raw allocation and
accounting observations, twenty accounted-for attempts, measured timings, and
an import/export that agrees with that evidence. Authentication and submission
remain the human's steps after review.
