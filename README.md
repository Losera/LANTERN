# LANTERN

LANTERN will test whether presenting the same evidence differently changes an
AI recommendation, then test whether a declared correction helps. Markets &
Networks is the required track. This repository currently provides engineering
and collaboration setup; the application and Alpha experiments are not built.

## Start here

Read in this order; return to the references when your task needs them:

1. [Agent instructions and engineering policy](AGENTS.md).
2. [Project brief, decisions, and architecture boundaries](docs/project.md).
3. [Alpha constraints and readiness gates](docs/alpha.md).
4. [Evaluation methods and evidence requirements](docs/evaluation.md).
5. [Research summary, attribution, and pinned sources](docs/research.md).
6. [Current status and handoff](docs/status.md).
7. [Contributor walkthrough](CONTRIBUTING.md).

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

## Check bootstrap materials

Prerequisites: Git, Bash, and Python 3.10 or newer. No package installation is
required. These check documentation and the checker itself, not the product:

```bash
python3 tools/check_bootstrap.py --self-test
python3 tools/check_bootstrap.py
git diff --check
```

The checker covers inline Markdown links and URL autolinks; reference-style or
HTML links must be converted to that subset. It is offline and never executes
shell examples. External-link access,
source interpretation, diagram rendering, and beginner/harness walkthroughs
need separate recorded checks. See [verification status](docs/status.md).

## Working agreement

Use a bounded issue, one human owner, a task branch, and a separate worktree.
Keep architecture, schemas, and environments subject to the lead's explicit
approval. Ask for semantic review before committing substantive work.

Two optional [development skills](docs/research.md#development-skills) guide
task handoffs and Alpha learning. They are repository instructions, not product
runtime dependencies. No cluster account, API subscription, or private vault is
required to read the context pack or run its offline checks.
