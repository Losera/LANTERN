"""The presentation projection: one JSON file the static frontend reads.

The export is deliberately a *projection*, not a dump. It carries the cases,
the per-attempt records, the comparison, and -- non-negotiably -- the
boundaries, because the frontend is what a judge or reviewer actually looks at
and docs/evaluation.md requires each evidence lane to stay separate.

:data:`BOUNDARIES` is therefore part of the data rather than page copy. If the
export exists, the caveats exist with it, and they travel with the file into
any screenshot or hand-off.

Every export states its ``label``. An export built from the synthetic fixture
is labelled as such and the page shows that label prominently, so an example
screenshot cannot be mistaken for an experiment result.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path

from runner import LANE, SCHEMA_VERSION
from runner.analysis import Analysis
from runner.cases import Case
from runner.conditions import Condition
from runner.trace import ORACLE_CONFORMANCE

#: Boundaries shipped with every export. Each is traceable to a source
#: document; none may be dropped to make a page look stronger.
BOUNDARIES = (
    {
        "title": "Coverage is not task success",
        "detail": "Coverage asks whether every registered attempt reached a "
                  "definitive outcome. A fully recorded failure is covered, and "
                  "an empty run is vacuously covered.",
        "source": "docs/evaluation.md; lantern-formal README",
    },
    {
        "title": "A timeout stays unknown",
        "detail": "An attempt that never returned is neither a failure nor the "
                  "model resisting a cue. It is counted separately.",
        "source": "docs/evaluation.md",
    },
    {
        "title": "Design-oracle conformance is NOT_RUN",
        "detail": "The Lean model proves properties about a transition system. "
                  "This application emits traces in that vocabulary but no "
                  "conformance comparison has been run, so existing proofs "
                  "establish nothing about this code.",
        "source": "lantern-formal/HANDOFF.md",
    },
    {
        "title": "The recorder has a boundary",
        "detail": "Registered coverage cannot detect every bypass. Activity "
                  "that avoids the recorder is outside the recorded record, "
                  "and model internals are never observed.",
        "source": "docs/project.md",
    },
    {
        "title": "An explanation is received text",
        "detail": "A model's stated reasoning is retained as received output. "
                  "It is not evidence about the model's internal computation.",
        "source": "docs/evaluation.md",
    },
    {
        "title": "A mention is not observed evidence",
        "detail": "A source named in output without a recorded successful "
                  "outcome stays visible as an unsupported mention and is never "
                  "promoted to observed evidence.",
        "source": "lantern-formal README",
    },
)


def _plain(value: object) -> object:
    """Recursively convert dataclasses and enums into JSON-safe values."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def case_view(case: Case, conditions: tuple[Condition, ...]) -> dict[str, object]:
    """One case as the page shows it, with its condition matrix."""
    return {
        "id": case.id,
        "status": case.status,
        "question": case.question,
        "rubric": {"id": case.rubric.id, "requirements": list(case.rubric.requirements)},
        "options": [{"id": o.id, "label": o.label} for o in case.options],
        "evidence": [
            {
                "id": item.id,
                "claim": item.claim,
                "source": item.source,
                "source_authority": item.source_authority,
                "relevant": item.relevant,
            }
            for item in case.evidence
        ],
        "relevant_count": len(case.relevant_evidence),
        "irrelevant_count": len(case.irrelevant_evidence),
        "conditions": [
            c.as_dict() for c in conditions if c.case_id == case.id
        ],
    }


def build_export(
    *,
    cases: tuple[Case, ...],
    conditions: tuple[Condition, ...],
    records: list[dict] | tuple[dict, ...],
    analysis: Analysis,
    label: str,
    generated_utc: str | None = None,
) -> dict[str, object]:
    """Assemble the document the frontend reads.

    ``label`` is required and has no default: an unlabelled export is exactly
    the artifact that gets mistaken for a result.
    """
    if not label.strip():
        raise ValueError("every export must state its label")
    records = list(records)
    synthetic = [r for r in records if r.get("synthetic") is True]
    return {
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "lane": LANE,
        "generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(),
        "oracle_conformance": ORACLE_CONFORMANCE,
        "synthetic_records": len(synthetic),
        "all_records_synthetic": bool(records) and len(synthetic) == len(records),
        "cases": [case_view(case, conditions) for case in cases],
        "attempts": [_plain(record) for record in records],
        "analysis": analysis.as_dict(),
        "boundaries": [dict(b) for b in BOUNDARIES],
    }


def write_export(path: str | Path, document: dict[str, object]) -> tuple[Path, Path]:
    """Write the export as JSON, plus a script-tag wrapper beside it.

    Two files, for one practical reason: browsers block ``fetch`` on a
    ``file://`` page, so a JSON-only export cannot be opened by double-clicking
    ``index.html``. A ``<script>`` source is not subject to that restriction.

    The JSON file stays canonical -- it is what tooling reads and what the
    checker validates. The ``.js`` file is a generated wrapper around the exact
    same bytes, never edited by hand, and ``tools/check_app.py`` verifies the
    two agree so they cannot drift apart.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(body + "\n", encoding="utf-8")
    wrapper = path.with_suffix(".js")
    wrapper.write_text(
        "/* Generated by `python3 -m runner.cli export`. Do not edit.\n"
        "   Wraps export.json so the page also works from a file:// URL,\n"
        "   where fetch() is blocked. Regenerate both together. */\n"
        "window.LANTERN_EXPORT = " + body + ";\n",
        encoding="utf-8",
    )
    return path, wrapper


__all__ = ["BOUNDARIES", "case_view", "build_export", "write_export"]
