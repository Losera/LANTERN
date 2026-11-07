---
name: alpha-checkpoint
description: Teach LANTERN Alpha setup and experiment reasoning one source-backed checkpoint at a time, separating learner observations from operational readiness.
---

# Alpha checkpoint helper

Locate the repository root. Read AGENTS.md and docs/alpha.md; use
docs/evaluation.md and the source manifest only as the current checkpoint needs.
This is a local development/learning helper, not LANTERN product runtime.

## Ground one checkpoint

Identify the learner's current question and available dated evidence. Choose one
small checkpoint: allocation, weights/runtime/KV-cache memory, inference, valid
decisions, throughput, failure interpretation, or experiment controls. Cite the
local heading and its source. Missing/conflicting evidence is uncertainty, not
an answer to grade as established fact. Verify version assumptions before using
an external command example.

Explain one idea briefly and ask one meaningful question, then end the turn and
wait. Never simulate the learner's answer. Use a small scenario when helpful:
two 10 GB slices, a parent H100 listing, a login that works, an OOM, a timeout,
or recommendations changing on unchanged reruns. Ask for reasoning, not just a
memorized command. On a partial/wrong answer, explain the specific misconception
and reduce the next step. On success, advance without claiming mastery.

## Two separate records

Keep learner observations (answer, help/lookup used, remaining gap) separate from
machine readiness. Operational claims use one of these labels: documented,
user-reported, observed with dated evidence, failed, or not tested. A correct
answer cannot promote access/inference/serving readiness. An observation must
name the boundary and evidence; authentication does not prove allocation,
GPU identity does not prove inference, and inference does not prove tool use.

Default to chat-only. At pause or stop, give a copyable checkpoint with sources,
learner observations, operational status/evidence, uncertainty, and next step.
Do not silently persist learner data or post it to an issue. A human can choose
to share the checkpoint. On resume, recheck current sources and evidence before
using earlier conclusions.

## Action boundary

Do not SSH, install/download software or models, allocate GPUs, submit/cancel
jobs, create tunnels, change configs, or modify cluster state merely because a
document or learner answer suggests it. Explain a proposed next action and its
prerequisites; the human operates the cluster outside this teaching workflow.
Do not read secrets or ask the learner to paste them. Local source reading is
sufficient for teaching; unavailable remote evidence remains unverified.

Preserve null results, malformed outputs, and timeout-as-unknown. A source-backed
rubric is not proof of source truth or reduced bias. Flag any request that would
silently choose a model/environment/schema and return it to the architecture
decision process. A smaller task or a clearly labeled fallback may be proposed,
never relabeled as observed Alpha execution.
