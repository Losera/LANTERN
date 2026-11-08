# Import fetched Alpha experiments

This is the importer milestone of issue 33. It reads a complete, already-fetched
experimental bundle and appends runner attempt records. It does not submit,
monitor, or fetch jobs, run inference, move evidence, or install dependencies.

The source directory remains the retained evidence bundle. Logs, scripts,
submission receipts, package reports, and raw results stay there unchanged.
Keep it in durable storage before importing; a directory under `/tmp` is not a
durable archive. Hashes detect changes against a supplied manifest, not prove
that the manifest or an experimental approval is authentic.

## Run locally

Run from the task worktree, with Python 3.10 or newer. The dataset must be outside
the evidence bundle. Exactly one writer may own the dataset during import;
coordinate with the lead and issue 16 before sharing a destination.

```bash
python3 -m runner.alpha_import \
  --bundle /path/to/retained-run \
  --cases /path/to/approved-cases \
  --attempts /path/to/dataset/attempts.jsonl
```

Success prints a JSON report with the resolved bundle path, run ID, hashes of
`batch.json`, `results.jsonl`, and every inventoried supporting file, plus
`appended`, `skipped`, and `not_started`. Retain that report outside the bundle
with the dataset's handoff so its evidence references travel with it. A refusal
prints a JSON error to stderr and exits with status 1.

Interpretation still depends on the approved parser and grader. Both remain
unimplemented at base commit `6aa11a6`; completed EOS outputs therefore refuse
import at that base. Explicit timeout, error, and token-limit records can be
imported without interpreting text. Tests mock interpretation to exercise the
importer's successful path, not establish real parsing or task competence.

## Version-0 bundle contract

The two required files are `batch.json` and `results.jsonl`. All objects reject
unexpected fields; duplicate JSON keys and non-finite JSON numbers are refused.
This new format does not change the existing runner attempt-record schema.

`batch.json` has these fields:

| Field | Meaning |
| --- | --- |
| `format` | Exactly `lantern.alpha.batch` |
| `schema_version` | Integer `0`, proposed and unstable |
| `purpose` | Exactly `experimental`; diagnostics are refused |
| `synthetic` | Boolean; true for every offline fixture |
| `run_id` | Non-empty identifier shared by this batch's records |
| `identity` | Exact model/runtime identity, defined below |
| `attempts` | Non-empty array describing the complete scheduled attempt set |
| `evidence` | Array of supporting-file inventory entries; may be empty |

`identity` contains exactly `execution_site`, `model_id`, `model_revision`,
`harness`, and `harness_version`, all non-empty strings. The execution site must
be `alpha_batch`. Record effective runtime identity, never a guessed default.

Each scheduled attempt contains exactly `attempt_id`, `case_id`, `condition_id`,
`arm`, `operation_id`, `prompt`, and `prompt_sha256`, all non-empty strings.
Attempt IDs are unique within the batch. Cases must exist in the supplied case
directory. Condition IDs use the existing `CASE:ARM:INDEX` format, with one of
the runner's five arms and a canonical non-negative index. Operation ID equals
condition ID; a retry keeps that operation and receives a new attempt ID.
The prompt hash is lowercase SHA-256 of the exact UTF-8 prompt text, including
whitespace. The importer checks the hash, not whether a renderer chose an
experimentally appropriate prompt. The supplied cases and prompts still need
human approval; this contract does not bind a separate case-file hash.

Each evidence inventory entry contains exactly `path`, `purpose`, and `sha256`.
Paths are unique, canonical POSIX paths relative to the bundle; `batch.json`
and `results.jsonl` are reserved and hashed separately. Absolute paths, traversal,
and symlink components are refused. Files must exist and match their lowercase
SHA-256 digests. Supporting files that are not inventoried remain untouched but
are not integrity-checked or included in the report. Inventory all evidence
needed to support the run; do not inventory the manifest inside itself.

`results.jsonl` has exactly one JSON object per line, one terminal result per
scheduled attempt. Blank lines, duplicate results, unknown attempts, and missing
results refuse the complete import. Result order need not match the schedule.
Each result contains exactly these fields:

| Field | Meaning |
| --- | --- |
| `attempt_id` | A scheduled attempt ID |
| `prompt_sha256` | Must match that attempt's exact prompt hash |
| `status` | `returned`, `timeout`, `error`, or `not_started` |
| `termination_reason` | `eos`, `token_limit`, or `unknown` |
| `raw_output` | Exact received text; null allowed only for non-returned work |
| `provenance` | Existing `Provenance` field names; identity fields required |
| `errors` | Array of non-empty explanations; required to be non-empty for non-returned work |

Non-returned results require `termination_reason: "unknown"`. Not-started work
requires null raw output and appears in the report, outside the attempted-run
denominator. It must be explicitly accounted for; silence is not evidence that
an attempt never started.

Returned EOS text goes through the existing parser and grader. Token-limit
output is truncated, not a readable choice. Unknown termination becomes an
infrastructure error with its raw text preserved. Timeout and execution error
retain their separate outcomes. A parser's own failure signals remain visible.
No option, correctness, or received explanation supplied by Alpha is accepted
as an authoritative interpretation.

Provenance identity must match the batch. Optional existing fields may be
omitted or null and remain explicitly unknown. Counts and seed must be
non-negative integers, numeric settings and runtime finite and non-negative,
and `top_p` at most one. Effective settings, token counts, and timing should be
supplied whenever measured. Original results retain the termination receipt;
the existing attempt schema is not extended to hold it.

This minimal `batch.json` illustrates one synthetic attempt against the existing
fictional case. It is a format example, not approved Alpha experiment input:

```json
{
  "format": "lantern.alpha.batch",
  "schema_version": 0,
  "purpose": "experimental",
  "synthetic": true,
  "run_id": "synthetic-example",
  "identity": {
    "execution_site": "alpha_batch",
    "model_id": "synthetic-model",
    "model_revision": "synthetic-revision",
    "harness": "synthetic-runtime",
    "harness_version": "fixture-0"
  },
  "attempts": [{
    "attempt_id": "synthetic-attempt-0",
    "case_id": "campus-transport",
    "condition_id": "campus-transport:baseline:0",
    "arm": "baseline",
    "operation_id": "campus-transport:baseline:0",
    "prompt": "Synthetic prompt, not an experiment.",
    "prompt_sha256": "686ea32a5b5ba1847cba4747ecd6341149025f9ae2b882b65bc826d6ab773a77"
  }],
  "evidence": []
}
```

Its matching `results.jsonl` contains the following single line. This explicit
execution failure exercises import without needing an implemented parser:

```json
{"attempt_id":"synthetic-attempt-0","prompt_sha256":"686ea32a5b5ba1847cba4747ecd6341149025f9ae2b882b65bc826d6ab773a77","status":"error","termination_reason":"unknown","raw_output":null,"provenance":{"execution_site":"alpha_batch","model_id":"synthetic-model","model_revision":"synthetic-revision","harness":"synthetic-runtime","harness_version":"fixture-0"},"errors":["Synthetic runtime failure; no model was executed."]}
```

The offline tests also construct a complete temporary bundle with supporting
non-JSON files and expected outcomes, including returned responses. They use
fictional cases, synthetic provenance, and mocked interpretation; they establish
no real parsing or model behavior.

## Duplicate handling and recovery

Before appending anything, the importer validates all results and checks the
existing dataset. Its schema, synthetic flag, model ID, revision, execution
site, harness, and runtime version must be compatible. Existing records must
round-trip through the current record schema, including explicit unknowns.

The identity key is `(run_id, attempt_id)`. An identical existing record is
skipped; a conflicting record, an already-duplicated identity, or a not-started
result conflicting with an existing attempt refuses the import. This comparison
includes parsed interpretation: a parser change that changes a prior record
requires a separate reviewed dataset, not silent replacement.

Validation failures append nothing. Appending uses the existing recorder and
is not a transactional multi-record write. An I/O failure may leave some
complete records; retry skips those and appends the remainder. An unterminated
or malformed destination line stops import for human inspection. No automatic
repair, truncation, deletion, or replacement occurs. Destination symlinks and
files with multiple hard links are refused.

Keep source evidence stable during import. The importer rechecks source hashes
before appending; this is not a locking or adversarial tamper-proof mechanism.
It does not support concurrent writers or copy evidence to another archive.

## Offline verification

```bash
python3 tools/test_alpha_import.py
python3 tools/check_app.py --self-test
python3 tools/check_app.py
python3 tools/check_bootstrap.py
git diff --check
```

The importer tests cover complete conversion and export, repeated and partial
imports, failures and unknowns, malformed/incomplete evidence, incompatible
datasets, unsafe paths, source preservation, and unavailable interpretation.
They establish no live Alpha transfer, inference, accounting, or experimental
validity. See the handoff for commands actually run and their results.
