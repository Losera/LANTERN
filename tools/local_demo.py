#!/usr/bin/env python3
"""Walk through the local experiment and serve an isolated frontend preview."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
import difflib
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runner import cli
from runner.analysis import summarize
from runner.cases import load_case
from runner.conditions import Arm, expand
from runner.models import UnapprovedAdapter
from runner.prompts import render
from runner.recording import read_attempts

RETAINED = ROOT / "evidence/local/pilot-2026-11-08"
EXPECTED_OLLAMA = "0.40.7"

ARM_PURPOSES = {
    Arm.BASELINE: "Original evidence and instructions: the reference choice.",
    Arm.UNCHANGED_RERUN: "The exact baseline prompt again: check repeatability.",
    Arm.NEUTRAL_EDIT: "Comparable extra wording without changing evidence.",
    Arm.FRAMING: "Change presentation while holding decision-relevant evidence fixed.",
    Arm.CORRECTION: "Change decision-relevant evidence; analyze separately.",
}


def stage(number: int, title: str, explanation: str) -> None:
    print(f"\n[{number}/8] {title}\n{explanation}\n", flush=True)


def checkpoint(pause: bool) -> None:
    if pause:
        input("Press Enter to continue (Ctrl+C to stop)... ")


def show_inputs(case) -> None:
    stage(1, "Start with the evidence packet", "A user supplies a case: question, options, sources, and decision requirements.")
    print(f"Input: {ROOT / 'fixtures/cases/example-campus-transport.json'}")
    print(f"Status: {case.status}\nQuestion: {case.question}")
    for option in case.options:
        print(f"  Option {option.id}: {option.label}")
    for item in case.evidence:
        relevance = "decision-relevant" if item.relevant else "declared irrelevant"
        print(f"\n  {item.id} ({relevance}): {item.claim}\n    Source: {item.source}\n    Authority: {item.source_authority}")
    print("\nDecision requirements:")
    for requirement in case.rubric.requirements:
        print(f"  - {requirement}")
    print("\nResearcher predeclarations are kept out of model prompts. This case is fictional.")


def freeze_prompts(run: Path, case) -> tuple:
    conditions = expand(case.id, reruns=4)
    folder = run / "prompts"
    folder.mkdir()
    manifest = []
    payloads = {}
    for condition in conditions:
        payload = render(case, condition)
        path = folder / f"{condition.arm.value}-{condition.index}.txt"
        path.write_bytes(payload.text.encode("utf-8"))
        manifest.append({**condition.as_dict(), "prompt_file": str(path.relative_to(run)),
                         "prompt_sha256": payload.sha256})
        payloads[condition.id] = payload
    (run / "conditions.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return conditions, payloads


def show_records_and_analysis(run: Path, conditions, *, pause: bool) -> None:
    records = list(read_attempts(run / "attempts.jsonl"))
    stage(6, "Inspect the recorded model responses", "Every attempt is a JSONL record, including failures. Raw text is preserved verbatim.")
    print(f"Records: {run / 'attempts.jsonl'}")
    for arm in Arm:
        rows = [r for r in records if r["arm"] == arm.value]
        print(f"  {arm.value}: " + ", ".join(
            f"{r['outcome']} / {r.get('option_id') or 'unknown choice'}" for r in rows))
    for arm in (Arm.BASELINE, Arm.FRAMING):
        row = next((r for r in records if r["arm"] == arm.value), None)
        if row is not None:
            print(f"\nFirst {arm.value} raw response ({row['outcome']}):")
            print(row["raw_output"] if row["raw_output"] is not None else "unknown: no response body received")
    checkpoint(pause)
    stage(7, "Analyze recommendations", "Compare consistent baseline and framing choices. Disagreement within an arm stays unresolved; no majority vote.")
    analysis = summarize(records, conditions).as_dict()
    exported = json.loads((run / "export.json").read_text(encoding="utf-8"))
    if analysis != exported["analysis"]:
        raise ValueError("Recomputed analysis differs from the run export")
    (run / "summary.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(f"Attempt denominator: {len(records)}; outcomes: {dict(Counter(r['outcome'] for r in records))}")
    for pair in analysis["framing_pairs"]:
        print(f"Framing: {pair['baseline_option']} -> {pair['contrast_option']}: {pair['verdict']} ({pair['reason']})")
    for pair in analysis["correction_pairs"]:
        print(f"Correction (separate): {pair['baseline_option']} -> {pair['contrast_option']}: {pair['verdict']}")
    print(f"Framing effect: {analysis['effect']}\nCorrectness: unknown; no grading key is used.")
    print("Unchanged-rerun and neutral-edit choices are controls to inspect; they do not automatically gate this verdict.")
    print(f"Summary: {run / 'summary.json'}")
    checkpoint(pause)
    stage(8, "Export and open the evidence view", "The runner already wrote this export. The frontend displays these records and their analysis.")
    print(f"Export: {run / 'export.json'}\nLabel: {exported['label']}")
    print(f"All records synthetic: {exported['all_records_synthetic']}")
    print("This is one fictional-case pilot; a null result is valid and correctness remains unknown.")
    checkpoint(pause)


def preflight() -> dict:
    """Refuse missing/wrong runtime before attempting any generation."""
    def get(endpoint):
        with urlopen(f"{UnapprovedAdapter.BASE_URL}/api/{endpoint}", timeout=10) as response:
            return json.load(response)

    version = get("version")
    if version.get("version") != EXPECTED_OLLAMA:
        raise ValueError(f"Expected Ollama {EXPECTED_OLLAMA}; found {version.get('version')!r}")
    models = get("tags")["models"]
    model = next((m for m in models if m.get("name") == UnapprovedAdapter.MODEL_ID), None)
    if model is None or not model.get("digest", "").startswith(UnapprovedAdapter.MODEL_REVISION):
        raise ValueError(f"Install the approved {UnapprovedAdapter.MODEL_ID} revision "
                         f"{UnapprovedAdapter.MODEL_REVISION} before running")
    return {"daemon": version, "model": model}


def fresh_run(*, walkthrough: bool = False, pause: bool = False) -> Path:
    source = ROOT / "fixtures/cases/example-campus-transport.json"
    case_data = load_case(source)
    if walkthrough:
        show_inputs(case_data)
        checkpoint(pause)
        stage(2, "Validate the case and local runtime", "Validate the input and confirm the pinned Ollama model before generating anything.")
        cli.main(["validate", str(source)])
    observed = preflight()
    if walkthrough:
        print(f"Ollama: {observed['daemon']['version']}; model: {observed['model']['name']}")
        print(f"Temperature: {UnapprovedAdapter.TEMPERATURE}; seed: {UnapprovedAdapter.SEED}; max output tokens: {UnapprovedAdapter.MAX_NEW_TOKENS}")
        checkpoint(pause)
    runs = ROOT / ".demo/runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
    run = Path(tempfile.mkdtemp(prefix=stamp, dir=runs))
    case = run / "case.json"
    shutil.copyfile(source, case)
    case_data = load_case(case)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (run / "preflight.json").write_text(json.dumps(
        {**observed, "code_revision": revision, "repetitions_per_arm": 4,
         "run_id": run.name, "case_sha256": hashlib.sha256(case.read_bytes()).hexdigest()},
        indent=2) + "\n", encoding="utf-8")
    print(f"Run directory: {run}", flush=True)
    conditions, payloads = freeze_prompts(run, case_data)
    if walkthrough:
        stage(3, "Expand the five experiment arms", "One case x five arms x four repetitions = 20 scheduled attempts. Repetitions do not change a prompt.")
        for arm in Arm:
            print(f"  {arm.value}: {ARM_PURPOSES[arm]}")
            print("    " + ", ".join(c.id for c in conditions if c.arm is arm))
        print(f"Frozen schedule and prompt hashes: {run / 'conditions.json'}")
        checkpoint(pause)
        stage(4, "Render the actual model inputs", "Read the baseline prompt, then inspect precisely what each other arm changes.")
        baseline = payloads[f"{case_data.id}:baseline:0"].text
        print("BASELINE PROMPT:\n" + baseline)
        for arm in (Arm.UNCHANGED_RERUN, Arm.NEUTRAL_EDIT, Arm.FRAMING, Arm.CORRECTION):
            contrast = payloads[f"{case_data.id}:{arm.value}:0"].text
            print(f"{arm.value.upper()} CHANGES (- baseline, + {arm.value}):")
            if contrast == baseline:
                print("Byte-identical to baseline.")
            else:
                print("".join(difflib.unified_diff(baseline.splitlines(keepends=True), contrast.splitlines(keepends=True),
                                                  fromfile="baseline", tofile=arm.value)))
        print(f"Every arm's exact prompt is saved in {run / 'prompts'}")
        checkpoint(pause)
        stage(5, "Execute the fixed schedule", "Send all 20 prompts through the existing render -> generate -> parse -> record loop. The run command also analyzes and exports.")
    command = ["run", "--case", str(case), "--reruns", "4",
        "--run-id", run.name, "--attempts", str(run / "attempts.jsonl"),
        "--export", str(run / "export.json"),
        "--label", "LOCAL FICTIONAL-CASE PILOT — correctness unknown"]
    print("Equivalent command: " + shlex.join([sys.executable, "-m", "runner.cli", *command]), flush=True)
    with redirect_stdout(io.StringIO()) as output:
        status = cli.main(command)
    (run / "run.stdout.json").write_text(output.getvalue(), encoding="utf-8")
    print(output.getvalue(), end="", flush=True)
    if status:
        raise ValueError(f"Run stopped; retained partial evidence in {run}. See docs/local-demo.md")
    if walkthrough:
        checkpoint(pause)
        show_records_and_analysis(run, conditions, pause=pause)
    return run


def preview(run: Path) -> Path:
    """Copy the frontend and that dataset's export into a fresh preview."""
    run = run.resolve()
    if not (run / "export.json").is_file() or not (run / "export.js").is_file():
        raise ValueError(f"Both export.json and export.js are required in {run}")
    previews = ROOT / ".demo/previews"
    previews.mkdir(parents=True, exist_ok=True)
    site = Path(tempfile.mkdtemp(prefix="view-", dir=previews))
    (site / "data").mkdir()
    for name in ("index.html", "app.js", "styles.css"):
        shutil.copyfile(ROOT / "frontend" / name, site / name)
    for name in ("export.json", "export.js"):
        shutil.copyfile(run / name, site / "data" / name)
    print(f"Showing export: {run / 'export.json'}", flush=True)
    return site


def serve(site: Path, port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Open http://localhost:{port} — Ctrl+C stops the preview.", flush=True)
        server.serve_forever()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("demo", "run", "replay", "view"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--yes", action="store_true", help="skip walkthrough pauses")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.action == "view" and (args.run is None or not str(args.run).strip()):
        parser.error("view requires --run")
    try:
        if args.action in ("demo", "run"):
            walkthrough = args.action == "demo"
            run = fresh_run(walkthrough=walkthrough,
                            pause=walkthrough and sys.stdin.isatty() and not args.yes)
        else:
            run = RETAINED if args.action == "replay" else args.run
        site = preview(run)
        if args.action != "run":
            serve(site, args.port)
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
