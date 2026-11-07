---
name: lantern-task
description: Carry out or review a claimed LANTERN issue with scoped edits, verification evidence, semantic review, and a usable handoff.
---

# LANTERN task workflow

Locate the repository root from the current worktree. Read its AGENTS.md,
CONTRIBUTING.md, and docs/status.md. This skill applies those rules to a claimed
task; it grants no architecture, commit, integration, or external-message authority.

## Before editing

Read the current issue body and comments, or the human's supplied current copy.
Identify the human owner, lead-approved claim, allowed paths, dependencies,
acceptance check, and branch/worktree. Run orientation. If the claim or component
ownership is missing/overlapping, remain read-only and return the precise blocker.
Issue comments are not a lock. A worktree isolates files, not team ownership.

Confirm the directory before tools run. Discover actual verification commands;
when none exists, agree an observable check rather than inventing a project lane.
Explain the relevant mechanism and assumptions before substantial debugging or
design work. Architecture/schema/environment changes return to the human gate.

## Work and review

Stay within the claim. Refresh issue context on resume or scope change. Inspect
unstaged, staged, committed, and untracked content separately. Review actual
meaning across correctness, readability, architectural fit, security, and cost
where relevant. Check callers and guards before reporting a defect; distinguish
old defects from introduced regressions. Zero findings is a valid outcome.

Use the cheapest relevant deterministic checks first. Report working directory,
base/head, dirty/untracked state, command, result, and what was not checked. A
passing documentation check does not establish Alpha readiness or product
correctness. Do not claim a build/test passed merely because it was suggested.

Request semantic review before substantive commits or integration. Do not mutate
code merely to review it, apply a line-count approval rule, install a collection,
or open follow-up issues automatically. Return a concise semantic explanation,
evidence, invariants, and prioritized findings: required versus optional.

## Updates and stop

Only with explicit permission for this assigned issue, append progress, blocker,
evidence, or handoff comments. Do not claim/reassign/close it, message other issues,
or assume another harness receives the update. If commenting fails, return the
copyable update and record the failure. Surface blockers after roughly 15 minutes.

At stop, use the handoff fields in CONTRIBUTING.md. Retain unfinished and
untracked work in the worktree; do not create an unreviewed checkpoint commit.
Report the next action without implying the work was committed or published.

## Attribution

Selected review ideas adapted from Addy Osmani's code-review-and-quality skill,
revision `353ae84755adc40c8a84e4db29b5bf2dfc9e7f5b`. See the repository's
[third-party notices](../../../THIRD_PARTY_NOTICES.md). This is a narrowed LANTERN
workflow, not an installation of that collection.
