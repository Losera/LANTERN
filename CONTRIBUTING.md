# Contributing to LANTERN

Start with [README](README.md), [AGENTS.md](AGENTS.md), [project decisions](docs/project.md),
and [status](docs/status.md). Git and Bash are the shared foundation. Linux/macOS
or Git Bash are supported by these examples; record each teammate's actual OS,
Git, Python, harness version, and access during onboarding. Never paste keys or
tokens into issues. A missing prerequisite is a blocker to report, not permission
for an agent to install it.

## Claim work

The lead is the single dispatcher. A human owner is accountable for a task;
the agent is the bounded worker. Issue comments and assignees are not atomic
locks. Do not start editing merely because an issue appears unassigned.

1. Read open issues and the chosen issue's comments. Replace `123` below with the
   actual issue number; it is an example, not a pre-created task:

   ```bash
   gh issue list --repo Losera/LANTERN --state open
   gh issue view 123 --repo Losera/LANTERN --comments
   ```

2. Request a claim with human owner, proposed branch, and affected paths. The
   lead checks all active claims, records the approved scope in the issue body,
   and moves its state from Ready to Doing before work starts. Only the lead
   grants or changes claims. One active writer per path/component across all
   machines and harnesses; separate worktrees alone do not prevent conflicts.
3. Shared contracts, root instructions, dependency/build files, integration
   files, and check tooling belong to the lead. Ask the lead to handle an edit
   outside your claim. Stop on unexpected overlap instead of expanding scope.
4. The lead may reassign only after confirming the old worker stopped and saved
   a handoff. Inactivity does not release a claim. Competing requests are resolved
   serially by the lead; neither requester starts until the decision is recorded.

Use [the issue template](.github/ISSUE_TEMPLATE/task.md). The issue body owns
current owner/scope/state; comments preserve dated progress and evidence. Include
objective, acceptance command or walkthrough, dependencies, blockers, and handoff.
Done means checked, explained, reviewed, and integrated, not just generated.

If `gh` is unavailable, use GitHub's web interface or paste the issue body and
comments into the session. Without current issue context and claim approval,
continue read-only. Do not invent a local lock or assume cached context is fresh.

## Start from current state

First run [orientation](README.md#orient-before-work), read applicable instructions,
and inspect existing changes. Do not reuse another person's active worktree.
From the main checkout, fetch and inspect the current remote:

```bash
git fetch origin
git status --short --branch --untracked-files=all
git log -5 --oneline --graph --all
git diff main..origin/main
```

If the main checkout is clean, switch to main and fast-forward. If it is dirty
or divergent, stop and involve its owner; do not stash/reset someone else's work:

```bash
git switch main
git merge --ff-only origin/main
```

Create the approved branch/worktree from the agreed base. Replace the illustrative
branch and sibling path with the issue's approved values. Git refuses a duplicate
branch or conflicting checkout; do not bypass that protection:

```bash
git worktree add -b docs/issue-123-topic ../LANTERN-123 origin/main
cd ../LANTERN-123
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch --untracked-files=all
```

## Launch a harness

Observed on the lead's Linux machine on November 7, 2026: Pi 0.81.1, Codex
0.163.0, Claude Code 2.1.241, GitHub CLI 2.102.1, and `gh stack` 0.1.0. These
versions are observations, not required installations. Check your own version
and `--help` before relying on options. Provider authentication and useful model
behavior were not tested by checking a version.

Open a terminal in the assigned worktree and start exactly one writing harness:

```bash
pi
```

or:

```bash
codex
```

or:

```bash
claude
```

Use the manually created worktree rather than additionally asking the harness
to create one. Inspect project/global hooks, skills, extensions, and trust prompts
before accepting project execution. Do not bypass permission controls. For a
read-only review, Codex supports `--sandbox read-only`; Claude supports
`--permission-mode plan`. These controls do not grant authorization for writes.
Pi has no assumed built-in `--plan` flag; extension flags vary.

Paste a launch instruction after filling the actual issue and approved paths:

```text
Read AGENTS.md and docs/status.md. Confirm your directory and branch.
Read the current issue and comments supplied with this task.
Human owner: <name>. Issue: <URL>. Approved claim: <lead's record>.
Allowed paths: <paths>. Objective: <bounded outcome>.
Acceptance: <existing command or observable walkthrough>.
You may append progress/evidence/handoff comments only to this issue.
Do not claim/reassign/close issues, expand scope, or edit architecture/schemas.
Stop for human semantic review before substantive commits or merges.
Report what ran, what did not, and unresolved risks.
```

Omit the comment authorization if the human will post updates. No harness
automatically polls GitHub or shares live memory with the other harnesses.
Refresh issue context at launch, resume, scope change, review, and handoff. Post
updates on start, meaningful progress, blocker, review, and stop. Surface a blocker
after roughly 15 minutes with exact command/error and attempts made.

The canonical skills are under `.agents/skills/`. In every harness you can say:
"Read `.agents/skills/lantern-task/SKILL.md` and follow it for this assigned task."
For Alpha learning, explicitly read `.agents/skills/alpha-checkpoint/SKILL.md`.
Codex documents project discovery and `$lantern-task`; Pi 0.81.1 documents
`/skill:lantern-task`. Check discovery after trusting/restarting the project.
Claude 2.1.241 can read the file explicitly; this repository does not install a
second skill copy or assume newer Claude discovery. `CLAUDE.md` imports AGENTS.md.

Primary references: [Codex instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[Codex skills](https://learn.chatgpt.com/docs/build-skills),
[Pi skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md),
[Pi commands](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/README.md),
[Claude instructions](https://code.claude.com/docs/en/memory), and
[Claude skills](https://code.claude.com/docs/en/skills).
Current upstream docs may describe capabilities newer than installed versions.

## Inspect and verify

Use terminal Git commands with any harness; you do not need a special diff UI.
Pi's installed reference supports `!git diff`, but ordinary terminal Git is the
portable path. Inspect each category because `git diff` omits untracked contents:

```bash
git status --short --untracked-files=all
git diff --stat
git diff
git diff --cached
git ls-files --others --exclude-standard
```

Open each untracked file in your editor or read it explicitly. For a text file,
`git diff --no-index -- /dev/null PATH` shows its contents as additions; exit code
1 means a difference was found. Use the actual filename in place of `PATH`.
Once your branch contains commits, inspect the committed change separately:

```bash
git diff origin/main...HEAD
```

Run the issue's existing checks, cheapest relevant first. For this bootstrap:

```bash
python3 tools/check_bootstrap.py --self-test
python3 tools/check_bootstrap.py
git diff --check
```

These commands do not test the future application. Record the working directory,
base/head SHAs, unstaged/untracked state, exact commands, results, and limitations.
Evidence from a dirty tree describes that tree, not a later commit automatically.
No guessed pytest/npm/CUDA command should be called an established project lane.

## Semantic review and PRs

Explain behavior/meaning changes, ownership compliance, evidence, and remaining
risks using [the PR template](.github/pull_request_template.md). Ask the lead for
semantic review before committing substantive work. Approval of architecture
does not automatically approve the implementation diff. Stage explicit paths
only after review and inspect `git diff --cached` again. Rerun relevant checks if
the reviewed content changes.

Before any PR operation, inspect branch/PR/stack topology:

```bash
git branch -vv
git log --oneline --graph --all -12
gh pr list --repo Losera/LANTERN --state open
gh stack view
```

A missing current stack is an observation, not a reason to restack existing PRs.
The installed `gh stack` 0.1.0 can adopt an existing approved branch:

```bash
gh stack init --base main docs/bootstrap
```

Use the actual branch for other tasks. `gh stack add` creates a dependent layer;
do not use it to connect independent sibling tasks. Avoid its automatic staging
and commit options. Do not initialize/adopt a branch already owned by a stack.
After semantic review and allowed commits, submit the inspected stack as drafts:

```bash
gh stack submit --auto
```

This command pushes branches, creates/updates PRs, and may update bases. Inspect
its planned stack first. Replace generated descriptions with the reviewed PR
template content; for multiline CLI text, save a body file and use `--body-file`.
Do not automatically sync, rebase, force-push, or merge a stack. Main integration
requires the lead's semantic review. A plain `gh pr create` is permitted only for
an intentionally standalone change after stating that exception.
See [the versioned stack reference](https://github.com/github/gh-stack/blob/v0.1.0/README.md).

## Conflicts, handoff, and cleanup

Pause affected writers on unexpected overlap or conflict. Inspect the state:

```bash
git status
git diff --name-only --diff-filter=U
git diff
```

Save a handoff and involve both human owners. Resolve each conflict deliberately;
do not select ours/theirs wholesale, reset, discard files, rewrite history, or
abort another person's operation. The lead chooses the integration base after
inspection. Recheck the resolved content and run affected verification.

Use this copyable handoff in the assigned issue, or return it to the human when
commenting is not authorized/available:

```text
Objective / human owner:
Issue / approved scope:
Branch / base SHA / head SHA / worktree:
Current state, including staged/unstaged/untracked files:
Completed work and changed files:
Verification commands, results, and artifact locations:
Verification still needed:
Failed approaches / discoveries:
Unresolved risks / blockers:
Next recommended action:
```

Leave unfinished work in its worktree unless the owner authorizes another safe
retention method. A patch alone omits untracked files. Do not create an unreviewed
checkpoint commit to bypass the semantic-review gate.

After work is reviewed and safely retained remotely/integrated, inspect the
worktree for tracked, untracked, and ignored material before removal:

```bash
git status --short --untracked-files=all
git ls-files --others --ignored --exclude-standard
```

Back up needed ignored artifacts too. Exit the harness, move to the main checkout,
and remove only the confirmed disposable worktree:

```bash
cd ../LANTERN
git worktree remove ../LANTERN-123
git worktree list
```

Do not use `--force`. Retain the branch until the lead confirms integration.
See [Git's worktree reference](https://git-scm.com/docs/git-worktree).

## Beginner acceptance walkthrough

Use a lead-approved disposable task/worktree, not a live component. Practice with
a tracked edit, a staged edit, and a new untracked text file. The beginner must
locate each, explain the diff, run the bootstrap checks, and produce a handoff.
The lead then verifies nothing was lost before cleanup.

Repeat task discovery using the web/pasted-issue fallback. Simulate competing
claims and stop until the lead grants one; simulate an interrupted session and
resume from current files plus the handoff, not assumed model memory. Show how a
conflict would be escalated without discarding work. Record actual outcomes,
help needed, and remaining gaps. A written walkthrough is not a completed user
test. Skill/help comparisons and actual harness behavior remain separate evidence.
