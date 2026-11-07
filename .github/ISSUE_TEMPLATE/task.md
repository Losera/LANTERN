---
name: Bounded task
about: A human-owned task with approved paths and observable acceptance
title: ''
labels: ''
assignees: ''
---

## Task contract

- Objective:
- State: Ready
- Human owner: Unassigned; proposed Teammate <letter> - <name or name pending>
- Agent/session: none assigned; record harness/version, session/task name, and active/stopped once assigned
- Approved scope: Pending lead claim; list proposed files/components
- Branch/worktree:
- Acceptance: exact command or observable walkthrough
- Dependencies:
- Claim approval: Pending lead decision; no edit authority yet
- Issue-comment authorization: none unless explicitly granted in the launch task

## Progress and evidence

- Latest progress and date:
- Next action / blocker:
- Verification: directory, base/head SHAs, dirty/untracked state, exact commands and results
- Evidence locations:
- Not run / limitations:

## Handoff

- Completed work and changed files:
- Verification still needed:
- Failed approaches / discoveries:
- Unresolved risks:
- Next recommended action:

States: Ready / Doing / Blocked / Review / Done. The lead controls claims,
scope changes, and closure; comments are not atomic locks. A claimed issue has
one named human owner, written as `Teammate A - Losera`, for example. An unclaimed
issue stays `Unassigned` even when it has a proposed teammate slot or label.
Changing or stopping an agent session preserves the human owner and approved
claim. The body holds current state; dated comments retain progress and handoffs.
Labels `teammate-a`, `teammate-b`, and `teammate-c` filter slots only and grant no
ownership or edit authority. See
[CONTRIBUTING](https://github.com/Losera/LANTERN/blob/main/CONTRIBUTING.md#claim-work) and
[engineering policy](https://github.com/Losera/LANTERN/blob/main/AGENTS.md).
Read the current issue and comments at launch, resume, scope change, review, and
handoff; sessions do not synchronize automatically.
