#!/usr/bin/env python3
"""Run the existing local CLI and serve an isolated frontend preview."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runner import cli
from runner.models import UnapprovedAdapter

RETAINED = ROOT / "evidence/local/pilot-2026-11-08"
EXPECTED_OLLAMA = "0.40.7"


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


def fresh_run() -> Path:
    observed = preflight()
    runs = ROOT / ".demo/runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
    run = Path(tempfile.mkdtemp(prefix=stamp, dir=runs))
    case = run / "case.json"
    shutil.copyfile(ROOT / "fixtures/cases/example-campus-transport.json", case)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (run / "preflight.json").write_text(json.dumps(
        {**observed, "code_revision": revision, "repetitions_per_arm": 4,
         "run_id": run.name}, indent=2) + "\n", encoding="utf-8")
    print(f"Run directory: {run}", flush=True)
    status = cli.main(["run", "--case", str(case), "--reruns", "4",
        "--run-id", run.name, "--attempts", str(run / "attempts.jsonl"),
        "--export", str(run / "export.json"),
        "--label", "LOCAL FICTIONAL-CASE PILOT — correctness unknown"])
    if status:
        raise ValueError(f"Run stopped; retained partial evidence in {run}. See docs/local-demo.md")
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
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.action == "view" and (args.run is None or not str(args.run).strip()):
        parser.error("view requires --run")
    try:
        run = fresh_run() if args.action in ("demo", "run") else (
            RETAINED if args.action == "replay" else args.run)
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
