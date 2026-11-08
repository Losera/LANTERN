# Proposed formats and module boundaries

Status: **PROPOSED, not approved.** Every document described here carries
`schema_version: 0`, which means unstable: these formats may change without a
migration path until the lead approves them as contracts. Build against them,
but do not treat a field as settled.

Source: this document records the structure implemented on the application
skeleton branch. The experiment requirements it serves are in
[evaluation](evaluation.md); the approved and unresolved decisions are in
[project decisions](project.md). Where the two disagree, those documents win.

## What is implemented and what is a seam

The split is deliberate. Deterministic work that needs no approval is
implemented and checked. Work that depends on an unapproved decision raises
`NotImplementedError` naming the missing approval, because a stub that returns
plausible data is indistinguishable from a result once it reaches the export.

| Module | State | Responsibility |
| --- | --- | --- |
| `runner/unknown.py` | Implemented | The explicit-unknown sentinel |
| `runner/cases.py` | Implemented | Case loading and structural validation |
| `runner/conditions.py` | Implemented | The five arms and their eligibility |
| `runner/outcomes.py` | Implemented | Failure taxonomy and bucket precedence |
| `runner/recording.py` | Implemented | Append-only attempt records |
| `runner/trace.py` | Implemented | Oracle event emission and field discipline |
| `runner/analysis.py` | Implemented | Paired comparison and counting |
| `runner/export.py` | Implemented | The presentation projection |
| `runner/models.py` | Implemented | Provenance and the approved local Ollama adapter; no Alpha adapter |
| `runner/tools.py` | Mixed | Proposal recording implemented; execution is a seam |
| `runner/prompts.py` | Implemented | Prompt rendering and the prompt digest |
| `runner/parsing.py` | Mixed | Reading output implemented; grading is a seam |
| `runner/alpha_batch.py` | Implementation awaiting semantic review | Frozen preparation, submission recovery, import and export; depends on B's case/rendering/interpretation work |

The lead approved the bounded Alpha coordinator design on November 8, 2026.
Its local progress journal has independent format `lantern.alpha.progress`,
version `1`; it is not an attempt-schema extension. It binds a run to its host,
frozen input hashes, submission intent, job receipt, transport logs, fetched
evidence hashes and completion state. Updates replace the journal atomically
under an exclusive advisory lock. Unsupported versions refuse recovery;
there is no automatic journal migration. Preserve the directory and use the
matching reviewed implementation to recover an older run.

The [batch operator guide](alpha-batch.md) defines `prepare`, `submit`, and
`resume`. The existing batch/result envelopes and attempt records are unchanged.
The standalone GPU executor emits those envelopes; it does not implement an
Alpha `ModelAdapter` or change the local Ollama adapter. Removing the new
coordinator leaves existing helper/import commands usable. Preserve completed
bundles and journals when rolling back; do not resubmit an uncertain run with
an older helper.

The seams and what each one waits on:

| Seam | Blocked on |
| --- | --- |
| `parsing.grade` | A frozen grading key for every rubric requirement |
| `tools.ToolRegistry.execute` | Tool contract, result format, identifier scheme |

Promoting a seam is a separate, lead-applied change to `tools/check_app.py`: its
`check_seams` asserts that a seam refuses and that implemented code does not, so an
implementation that lands without its promotion leaves the lane asserting the
opposite of the truth. A seam issue stays open until that promotion is on `main`; see
the [contributor guide](../CONTRIBUTING.md#claim-work).

`prompts.render` is no longer a seam: it returns a `PromptPayload` and the
offline lane now checks that it does. Implemented is not the same as correct.
At `6aa11a6` the function does not read its `condition` argument, so all five
arms of a case render byte-identical text under one digest, and the options are
rendered by label while the rubric asks for an option identifier. The lane does
not detect either, because its seam check only establishes that implemented code
does not refuse. Treat the independent variable as unimplemented until the
rendering issue lands.

`parsing.parse` is no longer a seam: it landed in PR 46 and PR 49, and the offline
lane exercises the real reader against a decision, malformed text, and an
out-of-rubric choice.

`parsing.grade` was briefly not a seam. Commit `e5cf45d`, pushed directly to `main`
without a branch, pull request, or semantic review, replaced its refusal with a body
that returned `CORRECT` for any in-rubric choice. That is the substitution
[evaluation](evaluation.md) forbids: correctness is requirement-level satisfaction of
a frozen grading key, and agreement with a choice "cannot substitute for
requirement-level grading". The consequence was not local. Both
`alpha_import._record` and `alpha_batch.interpretation_ready` caught
`NotImplementedError` from `grade` as their readiness gate, so the refusal was the
single tripwire keeping ungraded attempts out of the append-only dataset. With it
removed, the importer would have stamped a correctness no approved rubric supports,
and the offline lane went red for one commit. The seam is restored, and its refusal
now names the missing grading key rather than the rubric. The draft is retained on
`wip/grader-draft-b` for issue 9.

The local Ollama adapter landed in PR 35 and is no longer a refusing seam,
despite retaining the class name `UnapprovedAdapter`. The offline lane calls its
real generation method with synthetic HTTP responses, checking request settings,
raw output, local provenance, truncation, and explicit API/transport failures.
It makes no daemon connection and performs no model inference. Passing fixtures
does not verify installed model identity, real runtime behavior, or Alpha
execution; the two remaining seams are grading and tool execution.

## Case document

One JSON object per file under `fixtures/cases/`. Unknown fields are rejected,
following the oracle's strict-field discipline: `relevent: false` must fail
loudly rather than default to relevant.

A rubric carries two separate lists. `requirements` are instructions to the
decision-maker and are rendered into the prompt. `predeclarations` are optional
statements the team fixes in advance for its own interpretation and are **never
rendered**.

The split is a measurement requirement, not presentation. A predeclaration such
as "timetable position and newsletter tone must not affect the selection" names
exactly the material the framing arm manipulates, so rendering it would instruct
the subject to resist the manipulation and an unchanged answer would show only
that an instruction was obeyed. The irrelevance is already carried structurally
by each evidence item's and cue's `relevant` flag, so keeping the prose out of
the prompt loses nothing. The offline lane fails if a predeclaration reaches the
rendered text.

```json
{
  "schema_version": 0,
  "id": "campus-transport",
  "status": "FICTIONAL_EXAMPLE",
  "question": "Which shuttle route should be the primary evening service?",
  "options": [
    {"id": "route-north", "label": "Route North"},
    {"id": "insufficient", "label": "Evidence is insufficient to recommend either"}
  ],
  "evidence": [{
    "id": "ev-ridership",
    "claim": "Route North carries 1,840 evening riders per week.",
    "source": "Fictional campus transit survey",
    "source_authority": "Primary operator record",
    "relevant": true
  }],
  "cues": [{
    "id": "cue-newsletter-tone",
    "cue": "A student newsletter calls Route North the obvious choice.",
    "relevant": false
  }],
  "rubric": {"id": "campus-transport-v0", "requirements": ["Answer with one option id."]}
}
```

`relevant` must be present as a boolean on every evidence item. The loader
refuses a packet that leaves relevance implicit, because
[evaluation](evaluation.md) requires relevant authority differences to be
declared before measuring. `source_authority` is retained rather than stripped.

`cues` is a required array and may be empty. Each cue has a unique `id`,
non-empty `cue` text, and a declared boolean `relevant` value. Cues describe
presentation or context; they are separate from evidence claims. This structural
field does not approve a cue class or an experimental fixture. The example case
remains fictional, and the version-0 format remains proposed and unstable.

## Attempt record

One JSON object per line under `fixtures/attempts/`, append-only. Every
attempted run is written, failures included, so a denominator computed later
cannot silently shrink. Two conventions carry most of the weight:

An unmeasured value is `null` **and** is named in `unknown`. A reader never has
to guess whether a null meant "missing" or "measured as nothing", and no field
is ever defaulted to `0` or `""`.

`outcome` and `correctness` are separate axes. An ordinary wrong answer is
`outcome: "decision"` with `correctness: "incorrect"`, not an outcome of its
own. `correctness` is only meaningful for a readable decision.

| Field | Meaning |
| --- | --- |
| `run_id`, `case_id`, `condition_id`, `arm` | What was attempted |
| `attempt_id`, `operation_id` | Oracle identifiers; a retry reuses the operation |
| `outcome` | `decision`, `malformed`, `truncated`, `refusal`, `timeout`, `invalid_choice`, or `error` |
| `correctness` | `correct`, `incorrect`, or `unknown` |
| `option_id` | The chosen option; required when `outcome` is `decision` |
| `raw_output`, `received_explanation` | Retained verbatim; an explanation is received text |
| `parse_signal` | The booleans that decided the outcome bucket |
| `mentions` | Sources named in output, each with `supported` |
| `provenance` | Execution site, model, harness, settings, timing, usage |
| `unknown` | Every field above that was not observed |
| `synthetic` | True for placeholder records |

`provenance.execution_site` has no default. A permitted local or API fallback
is never presentable as an Alpha run; see [Alpha constraints](alpha.md).

## Trace document

The input format of the Lean design oracle, reproduced exactly. Field sets per
event kind are transcribed in `runner/trace.py` and independently again in
`tools/check_app.py`, so a drift in either is caught.

```json
{"events": [
  {"kind": "dispatch", "run": 0, "operation": 0, "attempt": 0, "payload": 0},
  {"kind": "succeed", "run": 0, "attempt": 0, "artifact": 0},
  {"kind": "finalize", "run": 0, "complete": true}
]}
```

The runner **emits** traces and never decides whether one is acceptable. That
verdict belongs to the oracle. Reimplementing its transition system in Python
would produce a second, unproved implementation that agrees with itself, and
the oracle's handoff explicitly rules it out. `oracle_conformance` is therefore
`NOT_RUN` until a real comparison lane exists.

Application identifiers are interned as the oracle's natural numbers by
`trace.IdSpace`, which exports its mapping so a trace stays interpretable. An
identifier records what was named, not that the name was truthful.

## Export document

One generated file, `frontend/data/export.json`, read by the static page. It is
a projection: the page adds no numbers of its own.

| Field | Meaning |
| --- | --- |
| `schema_version`, `lane`, `generated_utc` | Provenance of the export itself |
| `label` | Required; an unlabelled export is what gets mistaken for a result |
| `oracle_conformance` | `NOT_RUN` |
| `synthetic_records`, `all_records_synthetic` | Placeholder accounting |
| `cases` | Each case with its evidence and condition matrix |
| `attempts` | Every attempt record |
| `analysis` | Arm counts, coverage, pairs, exclusions, effect, counting notes |
| `boundaries` | The evidence boundaries, shipped with the data |

`boundaries` is part of the document rather than page copy, so the caveats
travel with the file into any screenshot or hand-off.

A second generated file, `frontend/data/export.js`, wraps the identical bytes
as a `window.LANTERN_EXPORT` assignment. It exists only because browsers block
`fetch` on a `file://` page, so a JSON-only export cannot be opened by
double-clicking `index.html`. The JSON file stays canonical; the checker
verifies the two agree so they cannot drift.

## Analysis rules

These are the formats' reason for existing, so they are stated here too:

* Denominators include every attempted run.
* A timeout is unresolved: never a flip, never stability, never resistance.
* Coverage asks whether registered attempts reached a definitive outcome. A
  fully recorded failure is covered; an empty run is vacuously covered. It is
  not task success.
* Readable decisions that disagree within one arm leave the pair unresolved
  rather than being majority-voted, which would hide the variability the rerun
  arm exists to expose.
* An excluded condition is always listed with a stated reason.
* When every readable pair agrees, the effect is `none_measured` and the
  comparison is still complete.

## Changing any of this

While `schema_version` is 0, change a format by changing it and regenerating
the export. Once the lead approves these as contracts, a change needs an
approved migration and rollback plan; see [AGENTS.md](../AGENTS.md).
