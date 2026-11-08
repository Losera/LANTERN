# Review of PR 39 evaluation rules

## Findings and feedback for B

Reviewed delivery: [PR 39](https://github.com/Losera/LANTERN/pull/39), head
`43d3cbae552f926337e582af27a3ae2289411a98`, merged as
`93f8d0fdc6c89fbdc6a7209d6ce7f2f7ac1e8aea`. References below identify lines in
that delivered revision, before this correction. Feedback is prepared locally;
it has not been posted or sent to B.

1. High: `docs/evaluation.md:46` defines correctness as agreement with the user's
   choice. This changes the evaluation target: a model agreeing with a wrong
   reference would be called correct, while a justified disagreement would be
   called incorrect. Grade against the frozen case rubric, and report agreement
   with a declared reference separately. A readable wrong answer is still a
   decision; non-decisions remain ungraded/unknown.
2. High: the added section at `docs/evaluation.md:40` does not settle #25's
   acceptance. It describes parsing without exact matching, refusal, or
   truncation criteria. C would still have to guess the inputs to
   `choice_in_rubric`, `refused`, and `truncated`. State the approved strict JSON
   validation and exact ID matching, the lead-selected refusal policy, runtime
   precedence, and expected classification examples before parser handoff.
3. Medium: `docs/evaluation.md:42` calls the response a JSON file. The exact
   model text is a string in the outer results record's `raw_output`; parsing
   creates a local `Decision`. Preserve the string and distinguish the response
   from its storage envelope. Received explanations and evidence references do
   not establish internal reasoning or successful tool execution.

The missing heading space at line 40 is corrected with the replacement section.
The original delivery remains preserved in Git history. Issue 25 was observed
closed despite its missing acceptance; that issue state has not been changed.

## Corrections and the lead's decision

The lead requested review feedback and gap corrections on November 8, 2026,
then explicitly chose: keep JSON-only, with free-text refusals classified as
malformed for the bounded first experiment. The parser must set `refused=False`
throughout this protocol. A valid known option remains a decision even when
the explanation uses refusal language. A known insufficient-evidence option
also remains a decision; neither is automatically rubric-correct.

This choice avoids an undeclared second response format or heuristic refusal
detector. It limits the measurement: zero refusal outcomes cannot be read as
evidence that no refusals occurred. Raw text remains available for a separately
declared analysis. A later refusal protocol needs explicit approval before use;
do not retrofit it into these held-out results.

The corrective diff replaces the faulty section with the
[operative evaluation rules](evaluation.md#reading-and-grading-model-choices),
aligns the [response contract](alpha-import.md#proposed-structured-model-response),
and marks the earlier handoff as historical. It does not implement parsing or
grading code, rendering, a new schema, or agreement metrics.

It also closes the broader grading gap with a pre-run key: each rubric
requirement needs observable pass/fail conditions and supporting case evidence.
Completed answers receive requirement-level satisfied/violated/indeterminate
labels, aggregated to correct/incorrect/unknown by fixed rules. If an approved
case-specific key is missing, inconsistent, or not decidable before held-out
outputs exist, correctness remains ungraded; agreement remains separate.

This is a bounded lead-requested correction after B's delivery merged. B retains
ongoing evaluation ownership and C retains parser ownership. At inspection,
#25 was closed with no assigned agent session, #26 was deferred with no assigned
session, and no PR was open. No new teammate claim is granted, no issues are
edited, and no teammate is contacted by this delivery.

## Review and verification handoff

Human owner: Teammate A / Losera. Agent/session: Codex, evaluation-rule review.
Branch: `docs/evaluation-rule-corrections` in `/home/losera/LANTERN`.
Base/head before changes: `93f8d0fdc6c89fbdc6a7209d6ce7f2f7ac1e8aea`.
The branch started clean from fetched `origin/main`.

Changed documents: evaluation rules, Alpha response contract, historical
response-contract handoff, and this review. Runner code, fixtures, and check
tooling are unchanged. All changes are uncommitted and unstaged.

Verification on this documentation tree:

- `python3 tools/check_bootstrap.py`: passed for 25 tracked documents and 148
  links, explicitly skipping this untracked review.
- The same checker with `--root` pointing to a temporary export containing all
  tracked files plus this review: passed for 26 documents, 151 links, 33 shell
  examples, and eight JSON examples; 55 external URLs were not fetched.
- `python3 tools/check_app.py`: passed, with three refusing seams, four
  implemented callables, and oracle lane `NOT_RUN`.
- `git diff --check`: passed. The new review was also checked for whitespace.
- Unicode inspection and a cleanup comparison found no changes in any of the
  four documents. No style rewrite was needed.

These checks establish documentation structure and existing application
coherence. They do not exercise the classification examples through a real
parser: `parse` and `grade` still refuse. No model, Alpha job, live adapter,
case grading, or oracle conformance was tested.

Remaining acceptance: A reviews the semantic diff before substantive commit or
integration. Communicating feedback or reconciling #25/#9 requires separate
authorization; this delivery makes no board-state change. C's later work must
implement and test these rules and retain actual parser/import evidence before
the path is called verified.

The grading procedure is documented, but each experiment still needs its own
approved key: the existing fictional fixture is not approved, and its prose
requirements have not been translated into frozen pass/fail conditions. Keep
that case-level approval explicit in C's handoff; do not infer correctness from
agreement or treat this documentation as fixture approval.
