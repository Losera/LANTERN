# LANTERN

LANTERN will test whether presenting the same evidence differently changes an
AI recommendation, then test whether a declared correction helps. Markets &
Networks is the required track. This repository provides engineering and
collaboration setup plus an application skeleton: the runner's contracts and
deterministic parts are implemented, while prompt rendering, model adapters,
output parsing, and tool execution are explicit seams awaiting approval. No
model is run by any command, and the Alpha experiments are not built.

## Start here

Read in this order; return to the references when your task needs them:

1. [Agent instructions and engineering policy](AGENTS.md).
2. [Project brief, decisions, and architecture boundaries](docs/project.md).
3. [Alpha constraints and readiness gates](docs/alpha.md).
4. [Evaluation methods and evidence requirements](docs/evaluation.md).
5. [Research summary, attribution, and pinned sources](docs/research.md).
6. [Proposed formats and module boundaries](docs/contracts.md).
7. [Current status and handoff](docs/status.md).
8. [Contributor walkthrough](CONTRIBUTING.md).

## Orient before work

From your checkout or assigned worktree, run these read-only commands:

```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch --untracked-files=all
git log -5 --oneline
git worktree list
```

Read the instructions above and your assigned GitHub issue with its comments.
Give a short briefing: project, branch, changes, recent work, checks already run,
uncertainty, and next action. Separate harnesses share neither live memory nor
automatic issue updates. Follow the [claim process](CONTRIBUTING.md#claim-work).

## Application layout

The runner is a standard-library Python package; the frontend is hand-written
HTML, CSS, and JavaScript with no build step and no dependencies.

```text
runner/      experiment runner: implemented parts and declared seams
frontend/    static evidence view; reads frontend/data/export.json
fixtures/    an example case and clearly labelled synthetic attempts
tools/       offline checkers
docs/        decisions, constraints, and proposed formats
```

[Proposed formats and module boundaries](docs/contracts.md) lists which modules
are implemented, which are seams, and what each seam waits on. Formats carry
`schema_version: 0`, meaning proposed and unstable.

## Run the checks

Prerequisites: Git, Bash, and Python 3.10 or newer. No package installation is
required. These check documentation, the skeleton, and the checkers
themselves, not the product's conclusions:

```bash
python3 tools/check_app.py --self-test
python3 tools/check_app.py
python3 tools/check_bootstrap.py --self-test
python3 tools/check_bootstrap.py
git diff --check
```

The documentation checker covers inline Markdown links and URL autolinks;
reference-style or HTML links must be converted to that subset. Both checkers
are offline and never execute shell examples. The application lane establishes
that modules import, seams still refuse, the counting rules hold, the export
matches what the page reads, and the frontend has no external dependency. It
establishes nothing about Alpha connectivity, model behaviour, design-oracle
conformance, or reduced bias.

Optionally, `--oracle PATH` asks the Lean design oracle to judge one trace this
code emitted. That is one observation about one trace, not a conformance lane.

## See the evidence view

Rebuild the export, then open the page. The export writes both `export.json`
and a `export.js` wrapper so the page also works from a `file://` URL:

```bash
python3 -m runner.cli export
python3 -m http.server --directory frontend 8000
```

External-link access, source interpretation, diagram rendering, and
beginner/harness walkthroughs need separate recorded checks. See
[verification status](docs/status.md).

## Working agreement

Use a bounded issue, one human owner, a task branch, and a separate worktree.
Keep architecture, schemas, and environments subject to the lead's explicit
approval. Ask for semantic review before committing substantive work.

Two optional [development skills](docs/research.md#development-skills) guide
task handoffs and Alpha learning. They are repository instructions, not product
runtime dependencies. No cluster account, API subscription, or private vault is
required to read the context pack or run its offline checks.
