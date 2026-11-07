# LANTERN agent instructions

Read [README](README.md), then [project decisions](docs/project.md),
[current status](docs/status.md), and [CONTRIBUTING](CONTRIBUTING.md). Read the
Alpha and evaluation references only as the task requires. Run the orientation
commands in README before substantive work. This repository contains bootstrap
materials; there are no application tests yet.

The Universal Engineering Policy below is supplied by the project lead and is
the canonical repository copy. Skills and other documents must not weaken it.

# Universal Engineering Policy

These are my personal software-engineering rules. They apply across projects and agent runtimes unless a project-specific instruction explicitly narrows them.

## 1. Engineering objective

Use agents to improve engineering quality and accelerate execution without replacing my understanding of the system.

Optimize for:

* correctness
* maintainability
* engineering learning
* recoverability
* explicit verification
* simple designs
* clear architectural reasoning

Do not optimize for maximum code generation or maximum autonomy.

## 2. Cold re-entry

Assume I may remember little from the previous agent session.

Before substantive work in an existing project:

1. Identify the repository and branch.
2. Inspect Git status.
3. Inspect recent relevant history.
4. Read applicable project instructions.
5. Determine the current task and verification state.
6. Run the project's orientation procedure when one exists.

Then give me a concise re-entry briefing:

* project
* branch
* working-tree state
* current/recent work
* verification state
* important uncertainty
* next action

Do not make me reconstruct the previous session from raw logs.

## 3. Repository grounding

Understand before modifying.

Do not assume:

* file paths
* architecture
* tool availability
* test commands
* project state
* another agent's unfinished work

Verify them from the current repository and runtime.

Do not infer available tools from another harness or from documentation about another environment.

If a tool call reports that the tool does not exist, stop retrying it and determine which capabilities actually exist.

## 4. Architecture is human-gated

Do not introduce or materially change any of the following without my explicit approval:

* architecture or major components
* database or persistent schema
* Docker/container/environment architecture

When proposing an architectural change, provide enough information for me to learn from and judge it.

Include as appropriate:

* problem being solved
* current design
* at least one meaningful alternative
* tradeoffs
* recommendation
* adversarial critique
* relevant research or evidence
* migration/rollback implications
* diagram when structure or data flow is nontrivial

Do not silently convert an implementation task into an architecture redesign.

## 5. Preserve engineering-learning work

Architecture, debugging, and system design are deliberate learning priorities.

For substantial work in these areas:

* explain the relevant system before changing it
* expose important assumptions
* show evidence for the diagnosis
* involve me in architectural decisions
* do not hide complexity behind generated code

Prefer helping me understand the failure mechanism over merely making the symptom disappear.

## 6. Git workflow

Before substantive modifications, inspect Git status.

For a nontrivial feature or fix, use a task branch rather than working directly on `main`.

Use a separate Git worktree when:

* multiple agents work concurrently
* an unproven/weak model receives edit authority
* an experimental change should be isolated

Do not:

* discard existing changes
* reset user work
* force-push
* rewrite history
* perform destructive Git operations

without explicit approval.

## 7. Commit policy

Agents may automatically commit a minimal, self-contained change after relevant verification passes.

A change is not minimal if it involves:

* architecture or component boundaries
* public API/contract changes
* schema changes
* environment/build-system changes
* new concurrency behavior
* substantial control/data-flow changes
* broad refactoring
* unclear or incompletely understood behavior

Substantive work must wait for my semantic diff review before commit or merge.

File count or line count alone does not make a change minimal.

Every merge of substantive agent work into `main` requires my review of the semantic diff.

## 8. Verification

Every code change requires a risk-appropriate verification strategy.

Prefer deterministic evidence over model confidence.

Use, as applicable:

1. targeted reproduction/test
2. compiler/type checker
3. unit tests
4. integration tests
5. static analysis
6. sanitizer/fuzzer/property checks
7. runtime or domain-specific validation
8. broader CI

For bug fixes, add a regression test when practical.

Run the cheapest relevant check first, then broader checks when risk warrants them.

Never report:

* "fixed"
* "working"
* "verified"
* "tests pass"

unless the corresponding verification actually ran.

State exactly what was and was not verified.

There is no universal requirement to follow a fixed testing pyramid or fixed unit/integration-test ratio.

## 9. Diff review

After modifying code:

1. inspect the resulting diff
2. confirm only intended files changed
3. explain semantic changes
4. identify remaining risks

For substantive changes, stop for my review before committing or merging.

## 10. Fallback-model policy

Model availability does not imply model suitability.

Strong/proven agents may receive normal edit authority within the other rules in this file.

Unproven or weak/local models default to:

* reading
* searching
* repository exploration
* code localization
* reviewing diffs
* analysis

They do not receive write authority merely because the primary model is unavailable.

Promote a weaker model to editing only deliberately.

When a weak/unproven model edits, prefer an isolated task branch/worktree and require deterministic verification afterward.

## 11. Agent handoff

When work stops mid-task or moves to another agent, leave a concise handoff containing:

* objective
* branch
* current state
* completed work
* changed files
* verification performed
* verification still needed
* failed approaches or important discoveries
* unresolved risks
* next recommended action

Prefer durable repository/Git state over transferring a huge conversation transcript.

## 12. Scope control

Keep changes scoped to the requested task.

Do not:

* rewrite unrelated documentation
* opportunistically redesign adjacent systems
* add infrastructure because it is fashionable
* introduce Docker, Kubernetes, orchestration, MCP servers, or other infrastructure without a demonstrated need

Every additional abstraction layer must solve a demonstrated problem.

## 13. Pull-request workflow

Use the installed `gh stack` extension for future pull-request creation and
management. Prefer `gh stack init`, `gh stack add`, and `gh stack submit` so PR
dependencies, bases, ordering, and updates remain explicit and recoverable.

Use plain `gh pr create` only when the change is intentionally standalone and
does not belong to a stack. State that exception before creating the PR.

Do not convert existing PRs into a stack, change their bases, or restack them
without first inspecting the current branch and PR topology.
