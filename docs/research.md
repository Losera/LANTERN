# Research transfer and development resources

Research snapshot: `4ffd86bf788bd5c67034ad7c3fdedaa835e42e20`

Research branch: `docs/three-student-build-plan`

Imported: 2026-11-07

Attribution: AI-assisted research and planning supplied by the project lead;
the original notes disclose their AI assistance. This condensed transfer is
AI-assisted. The November 6 adversarial review was written by the same assistant
that proposed the design; it was not independent review. No paper results were
reproduced for the transfer.

## What belongs where

The application repository owns current approved decisions, operational
constraints, evidence requirements, contribution rules, and dated integration
checkpoints. GitHub Issues own live task state. The vault retains long research,
historical shopping/component proposals, alternative products, attachments, and
the Lean source/fixtures/reports. Do not duplicate current decisions in both.
Update imports through a reviewed diff with a new source date and snapshot.

Retain source attribution, uncertainty, and original dates. Use relative links
for transferred material and pinned GitHub links for retained sources. These
links may require vault access: the connector returned 404 during planning, so
remote readability is unverified. The local checkout at the supplied snapshot
was available. In that checkout, open the exact note title/heading listed below;
a URL alone does not grant access. No personal paths, credentials, full vault,
or organizer attachments are copied here.

## Source manifest

All source-note links below pin the imported snapshot. Dates describe the source,
not a claim that its technical findings were reproduced on import.

| Source | Source date and sections used | Destination and treatment |
| --- | --- | --- |
| [Overview](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20Overview.md) | Nov 7; Recommendation; Event and open questions | Project direction/context; recommendations distinguished from approval |
| [Alpha Setup and Coding Reference](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20Alpha%20Setup%20and%20Coding%20Reference.md) | Nov 7; allocation table; Inference first, serving second; Source conflicts | [Alpha](alpha.md); documented rules, user reports, proposed commands, untested integration |
| [LANTERN Resource-Informed Audit and Alternatives](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20LANTERN%20Resource-Informed%20Audit%20and%20Alternatives.md) | Nov 7; decision boundary; directions 1-3; Shared experiment contract | [Project](project.md), [evaluation](evaluation.md); conditional research recommendations, later direction approval recorded separately |
| [LANTERN Formal Validation and Findings](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20LANTERN%20Formal%20Validation%20and%20Findings.md) | Nov 6; What we can claim; Findings that should direct the build | Evaluation; recorded model evidence, no application conformance claim |
| [Three Student Build Plan](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20Three%20Student%20Build%20Plan.md) | Undated proposal in Nov 7 snapshot; Working agreement; scope cuts | Contribution and ownership; retain delivery lessons, not shopping assignments/counts |
| [Earlier Decision Observatory](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20LANTERN%20Decision%20Observatory.md) | Reassessed Nov 7; Architecture: who does what; What runtime evidence means | Historical design only; evidence boundaries retained, proposed stack not adopted |
| [Adversarial Review](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/NYCAIRR%20HackBU%20-%20LANTERN%20Adversarial%20Review.md) | Nov 6; findings 1-8; Tests that should be able to defeat the proposal | Evaluation limits and adversarial cases; same-assistant critique, no executed audit |
| [Preserved Hacker Guide PDF](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/4ffd86bf788bd5c67034ad7c3fdedaa835e42e20/Attachments/NYCAIRR%20X%20HackBU%20Hacker%20Guide.pdf) | Snapshot; printed pp. 0-2, per research notes | Alpha source conflicts; retained in vault, not redistributed here |

The lead's `lantern_1.md` planning brief and planning-session answers supplied
the bootstrap requirements. [Project decisions](project.md) record the answers;
the local brief itself is not imported as a competing source of current policy.

## Research claims and prior-art boundaries

The current goal is a specific controlled audit with an inspectable correction
and reusable evidence, not invention of agent observability or bias auditing.
The following are condensed comparisons from the audit, not hands-on results:

| Primary source | Relevant overlap and limit |
| --- | --- |
| [ACES paper](https://arxiv.org/html/2508.02630v1) | Controlled shopping position, sponsorship, and description experiments; those results do not establish campus-decision effects |
| [Auditing Provenance Sensitivity](https://arxiv.org/html/2607.20827v2) | Source-authority interventions; authorized reliance differs from correctness, stress-set rates differ from deployment prevalence |
| [Causal Agent Replay](https://arxiv.org/html/2606.08275v1) | Repeated interventions and replay; stochastic continuation/mocked-tool limits prevent internal-causality claims here |
| [Langfuse evaluation](https://langfuse.com/docs/evaluation/overview), [Inspect](https://inspect.aisi.org.uk/) | Existing traces, tasks, checks, and comparisons; a viewer alone is not differentiation |
| [AgentSight](https://github.com/eunomia-bpf/agentsight) | Optional system evidence; native-session and privileged capture have different coverage, neither is established on Alpha |
| [Fairness of Exposure in Rankings](https://arxiv.org/html/1802.07281v2), [Lost in the Middle](https://arxiv.org/html/2307.03172v3) | Relevant alternative methods; neither proves a weekend reranker fair or universally effective |

Keep network propagation and information exposure as deferred alternatives.
The old Python/FastAPI/React shopping proposal, simulated purchases, collector
service, graph, and privileged tracing are not silently selected by this pack.
No novelty, prize probability, population-level fairness, or causal discovery is
established. Lean evidence and its limits are in [evaluation](evaluation.md).

## Development skills

The [EthicalML resource collection](https://github.com/EthicalML/awesome-agentic-engineering-resources)
was used for discovery, including [Anthropic's simple-workflow guidance](https://www.anthropic.com/research/building-effective-agents).
The [Addy collection](https://github.com/addyosmani/agent-skills) was inspected at
individual-skill level. Do not install either collection wholesale.

| Package | Decision and reason | Dependencies and permission | Verification and maintenance |
| --- | --- | --- | --- |
| [lantern-task](../.agents/skills/lantern-task/SKILL.md) | Adapt selected review steps: make an agent apply the issue, diff, evidence, and handoff rules rather than merely read documentation | Instructions only; Git, optional authorized issue comments through `gh`; no automatic commit or architecture approval | Compare a practice task with docs alone and with skill; count missed ownership/untracked-file/evidence steps and human prompts; lead maintains workflow links |
| [alpha-checkpoint](../.agents/skills/alpha-checkpoint/SKILL.md) | Create an original helper inspired by obsidian-quiz: adapt feedback to one learner answer or readiness checkpoint | Instructions only; local sources; no automatic SSH, installation, job submission, tunnel, or cluster-state change; no quiz text copied | Exercise memory/access/OOM/source-conflict/failure/null-result/pause cases; record actual turns separately from the test design; lead rechecks sources on change |

The task skill adapts the [review skill at revision 353ae84](https://github.com/addyosmani/agent-skills/blob/353ae84755adc40c8a84e4db29b5bf2dfc9e7f5b/skills/code-review-and-quality/SKILL.md).
Its MIT attribution is retained in [third-party notices](../THIRD_PARTY_NOTICES.md).
Numerical change-size gates, mandatory mutation edits, automatic issue creation,
and dependencies on other collection skills are omitted. Semantic risk and human
review follow AGENTS.md. No repository-wide license is selected by this transfer.

All three harnesses can explicitly read a canonical SKILL.md. Codex/Pi discovery
and Claude's compatibility instructions are in [CONTRIBUTING](../CONTRIBUTING.md#launch-a-harness).
Discovery is not behavioral interoperability. No skill is part of LANTERN's
product runtime, a cluster service, or an installed personal configuration.

Defer more skills, collection installers, orchestrators, automatic polling,
MCP infrastructure, tracing, and deployment helpers until a measured need exists.
