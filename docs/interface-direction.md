# Terminal interface direction

Dated November 16, 2026. Records a design review of LANTERN's terminal output: the
proposal that stood before it, the direction now recommended, and every finding raised
against all three candidate forms.

Read this before proposing terminal or CLI output work. The findings carry stable IDs
so a later review can cite, contest, or close one by name.

> This document records a recommendation. **Nothing in it is approved.** Choosing
> between these forms is interface architecture under
> [engineering policy](../AGENTS.md) section 4, and one of the proposed changes
> touches `cmd_run`'s control flow. No code in `runner/` or `frontend/` was modified
> by this review.

## Decision status

| Field | Value |
| --- | --- |
| Reviewed at | `main` @ `e5e7241`, clean working tree |
| Recommended | Direction C — the streaming ledger |
| Approval | **Not approved.** Awaiting the lead's decision under policy section 4 |
| Supersedes | Nothing yet. The standing proposal remains as written in the vault |
| Blocks on | Three blocking findings against C itself; see [Blockers](#blockers) |
| Artifact | <https://claude.ai/code/artifact/701ec1da-3492-4675-b393-7c8af63c2b1d> |
| Artifact source | [interface-direction.html](interface-direction.html) |

The vault carries the decision record and the navigation; this file is canonical for
the findings and the evidence, matching the rule that the repository's own `docs/`
remain canonical for decisions and dated verification records.

## What was reviewed

The vault note `Reference/LANTERN Interface.md` proposes two delivery lanes. Its Lane 1
is a terminal-first design that prints **after** a run finishes: a static
`lantern report` block, `--format csv|json|tsv` taps, and documented `jq` one-liners
as the path from reading a number to using the data.

The lead then proposed a different direction: a terminal view native to an agentic
harness such as Claude Code, visually strong, using UX and human psychology, with
progress indicators that are load-bearing rather than decorative, on a crimson / gold
/ black / violet base palette — and simpler than the browser view while equally
refined.

Those two disagree about something structural: whether the terminal lane exists
**during** a run or **after** it. The review treated that as the decidable question.

## The three directions

**A — static report.** The standing proposal. One block print at exit. Honest and
cheap; silent for the entire time the user waits.

**B — dashboard TUI.** The new direction's implied form: a full-screen view with live
panels, redrawn as attempts land. Makes the wait visible; breaks on two counts, one of
them fatal to its own premise.

**C — streaming ledger.** Recommended. Line-oriented, append-only, no alternate
screen. Three phases print in order — plan, run, report — and nothing above the
current rule is ever rewritten. One determinate progress bar over a schedule frozen
before the first model call. Panels that are present but **masked with a stated
reason** rather than showing a number on a partial denominator. Degrades to plain
lines when stdout is not a terminal, so the same command serves the person watching
and the harness reading scrollback.

C is not a compromise between A and B. It follows from taking the new direction's
"harness-native" premise literally, which rules out the dashboard form that premise
seemed to imply.

## Facts read from the code

Every row was read from the repository at `e5e7241`, not from documentation.

| Fact | Consequence | Evidence |
| --- | --- | --- |
| Exactly one command is slow: `cmd_run` loops conditions sequentially, and the retained pilot took 25.1 s for 20 attempts | Progress has one honest home. `validate`, `expand`, `analyze`, `export` and `trace` read files and print | `runner/cli.py:243`, [pilot execution record](../evidence/local/pilot-2026-11-08/execution.json) |
| The schedule is frozen before the first model call | A determinate bar here has a real denominator | `runner/cli.py:185`, [conditions](../runner/conditions.py) |
| Expansion is arm-major: baseline, unchanged rerun, neutral edit, framing, correction, four reruns each | The noise-floor arm completes at attempt 8 and the framing arm at 16, so **execution order already enforces "floor before effect"** | `runner/conditions.py` `ARM_ORDER` |
| A run emits `RUN_ID=` to stderr, then nothing until one JSON object at exit | 25 seconds of silence is the current worst moment in the CLI | `runner/cli.py:191`, `runner/cli.py:363` |
| Resume skips recorded attempts without calling the model | A single-quantity bar reports work that never happened | `runner/cli.py:270` |
| Crimson and gold are already assigned to flip and unresolved | Two of the four requested base colours are spoken for | [frontend styles](../frontend/styles.css) |
| Standard library only, no build step, declared a distribution advantage | A TUI framework spends that property | [project brief](project.md) |
| `_usable_choice` returns unresolved when readable choices disagree inside one arm | A view that collapses an arm to one cell re-averages what the code refuses to average | `runner/analysis.py:177` |
| `Effect` is a closed three-state enum: `measured`, `none_measured`, `insufficient` | There is no state for a flip that fails to clear its noise floor | `runner/analysis.py:49` |
| `Effect` is decided from framing-pair verdicts alone; the rerun arm is never consulted | **The noise floor has no mechanical influence on the reported effect** | `runner/analysis.py:304` |
| `Coverage` is built by iterating records, and `covered` is `not pending` | Called mid-run, it reports complete accounting of an incomplete run | `runner/analysis.py:256` |
| No scalar variance or delta exists anywhere in `runner/` | Any numeric noise-floor axis is a statistic the renderer would be inventing | [analysis](../runner/analysis.py) |

## Findings register

Severity is the effect on what can be built, not on how wrong the idea is. Status
values: `open` needs a decision or work; `resolved by choice` was answered by
recommending C; `carried` survives into C unchanged.

### Against direction A, the standing proposal

| ID | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| A·1 | serious | Silent for the entire time the user waits. A static report exists only after the fact, and the proposal does not address the gap | `runner/cli.py:191` to `runner/cli.py:363` | resolved by choice |
| A·2 | blocking | The arms table hides within-arm disagreement. `route-west x4` becomes `route-west x3, route-east x1` with no cue that the pair is therefore unresolved, re-averaging in the renderer what `_usable_choice` refuses to average | `runner/analysis.py:177` | resolved by choice |
| A·3 | serious | The terminal lane gets no noise-floor visual, while the browser lane's variance band is described as the single highest-value visual in the whole design | vault `Reference/LANTERN Interface.md`, Lane 2 | open — see C·1 and C·2 |
| A·4 | keep | Four of its rules are right and survive: the source footer, the `--format` taps, the header label that cannot be cropped out of a screenshot, and `unknown` rendered as the word with its reason attached | vault `Reference/LANTERN Interface.md`, Lane 1 | carried |

### Against direction B, the dashboard form

| ID | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| B·1 | blocking | A full-screen TUI is invisible to the harness it was designed for. An alternate-screen view writes escape sequences, repaints over its own history and captures stdin; scrollback retains nothing and `grep` has nothing to match. "Harness-native" and "dashboard" are in direct conflict | terminal capability, not repository state | resolved by choice |
| B·2 | blocking | A live effect panel breaks the project's one non-negotiable rule. Counting flips as attempts land shows a number on a denominator that is still growing | vault Lane 1 design rules; append-only records in `runner/recording.py` | resolved by choice |
| B·3 | serious | A resumed run's progress bar is theatrical by accident: twelve skipped attempts move a single-quantity bar to 60% in milliseconds with no model call | `runner/cli.py:270` | resolved by choice |
| B·4 | serious | Geass crimson collides with semantic crimson. Promote crimson to chrome and a crimson flip marker stops meaning that something moved | [frontend styles](../frontend/styles.css) | resolved by choice |
| B·5 | serious | A TUI framework spends the property that makes LANTERN trivially installable. A determinate bar, a carriage return and an ANSI table are standard library | [project brief](project.md), policy section 12 | resolved by choice |
| B·6 | serious | A live view risks becoming a third place where `flip` is defined, after `analysis.summarize` and `frontend/app.js` | [export](../runner/export.py) | resolved by choice |
| B·7 | minor | The view wants an effect state the analysis layer cannot produce | `runner/analysis.py:49` | open — folded into C·1 |

### Against direction C, the recommended form

Written against the code after C was chosen. The first three change what can be
built.

| ID | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| C·1 | blocking | The noise floor has no mechanical influence on the reported effect. `Effect` is decided from framing-pair verdicts alone and the rerun arm is never consulted, so a band drawn to make the floor appear to gate the verdict implies a dependency the code does not have | `runner/analysis.py:304` | open |
| C·2 | blocking | The band's axis is a statistic that does not exist. Defining a delta as the proportion of reruns differing from the baseline's modal choice would be the renderer inventing a statistic — finding B·6 — and would require a modal choice that `_usable_choice` deliberately refuses to compute | `runner/analysis.py:49`, `runner/analysis.py:177` | open |
| C·3 | blocking | `summarize` called mid-run reports complete accounting of an incomplete run. At 12 of 20 attempts `Coverage` returns twelve registered, twelve definitive, nothing pending, and `covered` is true | `runner/analysis.py:256` | open |
| C·4 | serious | The mask is an honesty claim with no enforcement. The project's precedent is that a refusal must be tested to still refuse; "this panel will not show a number early" has no check behind it | seam assertions in [check_app](../tools/check_app.py) | open |
| C·5 | serious | "Only the last block repaints" holds only on the happy path. Three cases are unspecified: an attempt failing after the floor block is already final above it; an interrupted run, which leaves a torn live block and no report phase; and a resumed run whose floor arm is already complete on disk, firing the checkpoint before any work | `runner/cli.py:270` | open |
| C·6 | moderate | Progress and report land on different streams. Progress must go to stderr or it corrupts `--format json` on stdout, so "the same bytes serve human and agent" is really the same bytes on two streams, and redirecting stdout to a file loses the run | `runner/cli.py:191`, `runner/cli.py:40` | open |
| C·7 | minor | The three-phase simplicity claim is measured on one case's happy path. Confounded conditions with their reasons, multi-case runs, and the boundaries block all need somewhere to print | `excluded` in [analysis](../runner/analysis.py), `BOUNDARIES` in [export](../runner/export.py) | open |
| C·8 | minor | C advances none of the four development gates. It makes existing measurement legible; it must not preempt the grading contract decision | [status record](status.md) | open |

## Blockers

What must be settled before Direction C can be built, in order.

1. **Approval of the direction itself**, under policy section 4.
2. **The noise-floor band cannot be built as drawn** (C·1 and C·2). Either it waits
   for the statistics work, or it is redrawn categorically — distinct choices observed
   under byte-identical input, with no numeric axis and no implied threshold. This is
   the lead's call, and it decides whether the view's best visual exists at all.
3. **Masking must derive from the condition set**, never from analysis output, and
   coverage must not render until the run exits (C·3).
4. **The mask's refusal test lands in the same change as the mask** (C·4).
5. **A stream contract decision**: progress and phase lines to stderr, data to stdout
   (C·6).
6. **Interrupted, failing, and resumed-floor behaviour specified before code** (C·5).
7. Pre-existing, and not caused by this review: no `report` subcommand exists, and
   `analyze` prints indented JSON.

## Reusing this review

- **Cite findings by ID.** `A·2`, `B·5`, `C·3` are stable. A later review should close
  or contest one by name rather than restating it.
- **The mockups and the workflow simulation are in
  [interface-direction.html](interface-direction.html).** It is a single
  self-contained page: three rendered terminal forms, a palette comparison, and a
  27-frame replay of a run under two outcomes. Open it directly in a browser; it needs
  no server and no build.
- **Treat `variance` and `delta` in those mockups as proposed display fields, not
  schema.** They exist nowhere in `runner/`. That is finding C·2, and the page labels
  it.
- **Re-verify before building.** Every evidence reference is a path and a line at
  `e5e7241`. Line numbers move; the named callables do not.
- **The illustrative pass of the simulation is constructed.** It corresponds to no
  recorded run and is labelled on every frame. Only the pilot pass carries real
  values, from
  [the retained pilot](../evidence/local/pilot-2026-11-08/summary.json).

## Boundaries

What this review does and does not establish.

- It establishes **what the current code permits**, from paths and line numbers at one
  revision.
- It establishes **a recommendation**, not a decision, and not approval to implement.
- It does **not** establish that any form is easier to use. No user was observed. The
  psychology arguments — a mask teaches a rule better than a footnote, a reserved
  colour keeps its alarm value — are design reasoning, not measurement.
- It does **not** close the grading seam, add a case, or produce statistics. Those
  remain ahead of interface work in the project's own ordering.
- The retained pilot it draws on remains one fictional case, one small local model and
  one run, with correctness `unknown` on every record.
