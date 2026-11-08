# Handoff: the first real measurement

Dated November 8, 2026 UTC. Written for whoever continues this — Codex, another
Claude session, or a teammate — because the session that did the work may stop
on usage limits before the run happens. Prefer this file and Git over
reconstructing a transcript.

## Objective

Produce LANTERN's first real measurement: does presenting the same evidence
differently change the model's recommendation? Every record in
`fixtures/attempts/` is still `synthetic: true` and the export still reads
`effect: none_measured` off synthetic data. The project has never run its own
thesis.

## State

`main` is `fda933c`, green, with zero open pull requests. Branch protection is
on: a pull request is required, the three offline jobs must pass, and a branch
must be up to date before merge. Admins bypass; `KaiGonz` and `aachenheimer`
have write and do not.

Landed this session, newest first:

| PR | What it did |
| --- | --- |
| 56 | Ollama `format` JSON schema, so generation is shape-constrained |
| 55 | condition-sensitive renderer, plus `check_renderer` in the offline lane |
| 54 | a seam issue is not Done until its `check_app.py` promotion is merged |
| 53 | three uncovered Alpha suites added to CI |
| 52 | frontend design implementation |
| 51 | `docs/evaluation.md` conflict markers resolved, marker check added |
| 50 | the `parsing.grade` seam restored after a direct push broke `main` |
| 44 | resumable Alpha batch workflow, merged and deliberately inert |

Closed as superseded by 49: PRs 45 and 48. B's grader draft is preserved on
`wip/grader-draft-b`. Kai's renderer handoff is preserved on
`feat/prompt-rendering-handoff`; its response contract was adopted into `main`.

## What works, demonstrated

The render → generate → parse path runs end to end. One probe call against the
local daemon, recorded in PR 56:

```
Ollama 0.40.7, pinned qwen2.5:1.5b-instruct, greedy (temperature 0.0, seed 1)
raw: bare JSON, no fences
outcome=decision  option_id='route-west'  three evidence ids resolved
```

The five arms render 4 distinct digests across 20 conditions, the rerun arm is
byte-identical to the baseline, and the neutral and framing additions are within
3 percent of each other.

**That is a contract check, not an experiment.** It is one call, one arm, one
case. No framing effect has been measured and no repeated sampling has happened.

Also worth carrying forward: in that single probe the model chose the
accessibility-favouring option while **misattributing the evidence** — it
claimed Route West has "the highest ridership (1,840 riders per week)", but
1,840 is Route North's figure, and it misread the reliability percentages too.
A plausible choice with wrong reasoning is exactly what `correctness` exists to
separate from `outcome`. Record it; do not treat the choice as validation.

## The one remaining blocker

**There is no orchestration command.** `runner/cli.py` offers `validate`,
`expand`, `analyze`, `trace`, `export`, and `synthesize`. Nothing executes the
experiment. That is issue 16, owned by Teammate B (Andrew), and no branch for it
had been pushed when this was written. Check for one before building anything.

Without it the loop has to be driven by hand. It is the last piece.

### What the command must do

Load the case, `conditions.expand(case.id, reruns=N)`, `prompts.render`,
generate through the adapter, `parsing.parse`, then append through
`runner.recording`, then `analyze` and `export`.

Reuse `runner/alpha_import.py`'s `_record` shape rather than reimplementing it.
It already maps a parse signal to an outcome through `outcomes.classify` and
fills provenance, `prompt_sha256`, mentions, and explicit unknowns. Copying its
structure keeps a local run's records identical in shape to an imported Alpha
run's.

### Non-negotiables, each with its reason

- **Append-only and resumable.** A crash must not lose completed attempts or
  duplicate them on re-run.
- **Record every failure.** A timeout, a transport error, or malformed output is
  a recorded attempt with its outcome, never a skipped one.
  `outcomes.classify` owns which bucket applies; do not write a parallel `if`
  chain. `docs/evaluation.md` requires these be counted separately rather than
  collapsed.
- **Retain `raw_output` verbatim** as a string. Replacing it with a decoded
  object is explicitly forbidden.
- **Do not call `parsing.grade`.** It is a refusing seam and must stay one. See
  the grading section below.
- **Do not touch `runner/prompts.py` or the parser.** Both are now correct and
  both are load-bearing for the measurement.

## Grading is deliberately out of scope

The headline result does not need it. `runner/analysis.py` derives
`Verdict.FLIP` / `STABLE` / `UNRESOLVED` and `effect` purely from `option_id`
comparisons between a baseline and its framing pair. Correctness is a separate
axis and stays `unknown` throughout.

`parsing.grade` raises, and that refusal is load-bearing:
`alpha_import._record` and `alpha_batch.interpretation_ready` both catch
`NotImplementedError` from it as their readiness gate. A direct push that
implemented it removed that gate and turned `main` red — see PR 50 and
`docs/status.md`.

The decisions for when grading does resume are on issue 9: the signature becomes
`grade(decision, case, *, key: GradingKey)`, grading runs as a separate pass
after import rather than inline, and the frozen key lives at
`fixtures/keys/<rubric-id>.json` and is copied into the run's `inputs/` and
hashed. **No grading key exists yet**, and none can be written until the rubric
is revised — see below.

## Traps, each of which has already cost time

**The parser is strict on purpose.** Fences, surrounding prose, missing or extra
fields, duplicate keys, and a non-object root are all `malformed`, and
`docs/evaluation.md` forbids extracting or repairing candidate JSON. If a run
produces malformed output, **do not loosen the parser** — that reverses an
explicit decision of November 8. Fix the prompt or the decoding constraint.

**Predeclarations must never be rendered.** `rubric.predeclarations` holds
statements the team fixed in advance for its own interpretation. The example
case's entry names timetable position and newsletter tone — exactly what the
framing arm manipulates. Rendering it instructs the subject to resist the
manipulation, so an unchanged answer would show only that an instruction was
obeyed. `check_renderer` fails if one reaches the prompt.

**A seam issue is not Done until its `check_app.py` promotion is merged.**
`check_seams` asserts that a seam refuses and that implemented code does not, so
an implementation landing without its promotion leaves the lane asserting the
opposite of the truth while still passing. `tools/check_app.py` is lead-owned.

**`effect: insufficient` and `none_measured` are results, not failures.** The
frontend already says so. Report whichever occurs rather than retrying until a
flip appears; repeated runs selected for an interesting outcome are not a
measurement.

**The case is fictional.** `fixtures/cases/example-campus-transport.json` has
`status: FICTIONAL_EXAMPLE`. Any run on it is a pilot that demonstrates the
pipeline measures something end to end. It does not support a claim about the
thesis. `alpha_batch.prepare` refuses a fictional case by design; a local run
does not go through `prepare`.

## Verification

Before and after any change:

```bash
python3 tools/check_app.py --self-test && python3 tools/check_app.py
python3 tools/check_bootstrap.py --self-test && python3 tools/check_bootstrap.py
python3 tools/test_alpha_parsing.py
python3 tools/test_alpha_import.py
python3 tools/test_alpha_diagnostic.py
python3 tools/test_alpha_batch.py
python3 tools/test_alpha_executor.py
python3 tools/test_alpha_submit.py
python3 -m runner.cli validate
git diff --check
```

`check_app.py` must report `2 seams refusing` and `1 renderer arm checks`. If
`seams refusing` drops to 1, someone implemented `grade` without promoting it.

After a run:

```bash
python3 -m runner.cli analyze
python3 -m runner.cli export
python3 tools/check_app.py
```

A real run flips `all_records_synthetic` to false and moves the export label
away from `SYNTHETIC EXAMPLE — not experiment results`. If it does not, the
records did not land.

## Open, and owned by a human

- **Issue 9, Teammate B.** The rubric must be revised before any grading key can
  be written. Requirement 3 moved to `predeclarations` because it is a
  between-condition property, not a per-attempt one; requirement 2
  ("accessibility must be weighed, not treated as a tie-breaker of last resort")
  is hard to state as an observable pass condition. `docs/evaluation.md` is
  explicit: if a case cannot state those conditions without inspecting
  responses, do not grade that case.
- **Issue 26, Teammate B.** Closed, but the case fixture is still
  `FICTIONAL_EXAMPLE` and the lead's own comment records the issue as deferred.
  An approved case needs the missing evidence the lead identified: counts of
  affected students and evidence about usable alternatives.
- **Issue 16, Teammate B.** The orchestration command above.
- **Branch protection does not bind admins.** `enforce_admins` is false, leaving
  the lead an escape hatch for a red `main`. Four direct pushes reached `main`
  before protection existed; all were by a write-level collaborator and would be
  blocked now.

## Scope discipline

Out of scope and to be left alone: Alpha execution of any kind (SSH, Slurm,
GPU), the design-oracle conformance lane (issue 11), the tool-execution seam
(issue 21), and the frontend. Do not introduce infrastructure. Do not convert an
implementation task into a redesign. Architecture, schema, and environment
changes need the lead's explicit approval.
