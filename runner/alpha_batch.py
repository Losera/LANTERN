"""Prepare and resume one reviewed Alpha batch. Live commands are human-operated.

The local journal is versioned independently of the existing importer envelope.
Only Linux/macOS advisory locks are supported; no concurrent dataset writers.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from runner import alpha_import, parsing, prompts
from runner.analysis import summarize
from runner.cases import load_cases
from runner.conditions import expand
from runner.export import build_export, write_export
from runner.outcomes import classify, Outcome
from runner.recording import read_attempts

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen3-4B-Instruct-2507"
REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
IDENTITY = dict(execution_site="alpha_batch", model_id=MODEL, model_revision=REVISION,
                harness="transformers", harness_version="4.57.1")
POLICY = dict(input_limit=1024, max_new_tokens=128, eos_token_id=[151645, 151643],
              do_sample=False, num_beams=1, seed=1, use_model_defaults=False,
              attempt_timeout_seconds=60, repetitions=4, scheduled=20,
              minimum_decisions=10)
JOB = re.compile(r"[0-9]+(?:;[A-Za-z0-9_-]+)?")


class BatchError(ValueError):
    """A prerequisite is missing, or recovery needs human inspection."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return alpha_import._json(path.read_bytes(), str(path))


def atomic_json(path: Path, value) -> None:
    fd, name = tempfile.mkstemp(prefix=".journal-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(run: Path):
    try:
        import fcntl
    except ImportError as exc:
        raise BatchError("Run coordination requires Linux/macOS advisory locks") from exc
    if run.is_symlink() or not run.is_dir():
        raise BatchError("Run directory must exist and must not be a symlink")
    with (run / "coordinator.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BatchError("Another coordinator owns this run") from exc
        yield


def load_state(run: Path) -> dict:
    state = read_json(run / "progress.json")
    required = {"format", "version", "run_id", "host", "phase", "job_id", "operations", "fetched", "input_hashes"}
    if (not isinstance(state, dict) or not required <= state.keys()
            or state.get("format") != "lantern.alpha.progress"
            or type(state.get("version")) is not int or state["version"] != 1):
        raise BatchError("Unsupported progress journal")
    if state["phase"] not in {"prepared", "submission_uncertain", "submitted", "fetched", "complete"}:
        raise BatchError("Unknown progress phase; inspect the journal")
    return state


def verify_inputs(run: Path, state: dict, bundle: Path | None = None) -> None:
    root = bundle or run / "inputs"
    for name, expected in state["input_hashes"].items():
        if digest(alpha_import._file(root.resolve(), name)) != expected:
            raise BatchError(f"Frozen input changed: {name}")
    for name, expected in read_json(run / "inputs/local-source.json").items():
        if digest(ROOT / name) != expected:
            raise BatchError(f"Local implementation changed since preparation: {name}")


def interpretation_ready(case) -> None:
    # This synthetic probe exercises the owned interfaces, never real output.
    raw = json.dumps(dict(option_id=case.options[0].id, evidence_ids=[], explanation=""))
    try:
        decision = parsing.parse(raw, case)
        if classify(decision.signal) is not Outcome.DECISION:
            raise BatchError("Parser does not accept the agreed JSON response shape")
        parsing.grade(decision, case)
    except NotImplementedError as exc:
        raise BatchError("B's parser/grader is not ready; no batch prepared") from exc


def prepare(*, cases_dir: Path, grading_key: Path, approval: Path, out: Path,
            host: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", host):
        raise BatchError("Invalid Alpha host")
    if out.exists() or out.is_symlink():
        raise BatchError("Choose a new durable run directory")
    cases = load_cases(cases_dir)
    if len(cases) != 1 or "FICTIONAL_EXAMPLE" in cases[0].status.upper():
        raise BatchError("Exactly one explicitly approved case is required")
    case = cases[0]
    interpretation_ready(case)
    for path in (grading_key, approval):
        if path.is_symlink() or not path.is_file() or not path.read_text().strip():
            raise BatchError("A non-empty grading key and approval record are required")
    files = sorted(cases_dir.glob("*.json"))
    if len(files) != 1 or files[0].is_symlink():
        raise BatchError("Supply one regular case JSON file")
    conditions = expand(case.id, reruns=4)
    payloads = [prompts.render(case, condition) for condition in conditions]
    for payload in payloads:
        if not payload.text.strip() or hashlib.sha256(payload.text.encode()).hexdigest() != payload.sha256:
            raise BatchError("Renderer returned an empty prompt or incorrect hash")
    texts = {c.id: p.text for c, p in zip(conditions, payloads)}
    baseline = texts[f"{case.id}:baseline:0"]
    for arm in ("baseline", "unchanged_rerun", "neutral_edit", "framing", "correction"):
        if any(texts[f"{case.id}:{arm}:{i}"] != texts[f"{case.id}:{arm}:0"] for i in range(4)):
            raise BatchError("Repetitions of one arm must preserve the exact prompt")
    if any(texts[f"{case.id}:unchanged_rerun:{i}"] != baseline for i in range(4)):
        raise BatchError("Unchanged reruns must preserve baseline text")
    if any(texts[f"{case.id}:{arm}:0"] == baseline
           for arm in ("neutral_edit", "framing", "correction")):
        raise BatchError("Condition-sensitive renderer is not ready")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    # Validation precedes directory creation. A failed copy leaves evidence in
    # place and cannot become submittable without a complete progress journal.
    out.mkdir(mode=0o700, parents=True)
    inputs = out / "inputs"
    inputs.mkdir()
    (inputs / "cases").mkdir()
    copies = {
        "cases/case.json": files[0], "grading-key.md": grading_key,
        "approval.md": approval,
        "job.sbatch": ROOT / "examples/alpha-batch.sbatch",
        "alpha-batch-executor.py": ROOT / "examples/alpha-batch-executor.py",
        "alpha-inference-diagnostic.py": ROOT / "examples/alpha-inference-diagnostic.py",
        "inference-result.json": ROOT / "evidence/alpha/job-175794/inference-result.json",
        "installed-packages.txt": ROOT / "evidence/alpha/job-175794/installed-packages.txt",
    }
    for name, source in copies.items():
        shutil.copyfile(source, inputs / name)
    if load_cases(inputs / "cases") != cases:
        raise BatchError("Case changed during preparation; inspect the retained partial directory")
    atomic_json(inputs / "policy.json", POLICY)
    sources = [*sorted((ROOT / "runner").glob("*.py")), ROOT / "tools/alpha_submit.sh"]
    atomic_json(inputs / "local-source.json", {str(p.relative_to(ROOT)): digest(p) for p in sources})
    batch = dict(format="lantern.alpha.batch", schema_version=0, purpose="experimental",
                 synthetic=False, run_id=run_id, identity=IDENTITY.copy(), attempts=[], evidence=[])
    for index, (condition, payload) in enumerate(zip(conditions, payloads)):
        batch["attempts"].append(dict(attempt_id=f"attempt-{index:02d}", case_id=case.id,
            condition_id=condition.id, arm=condition.arm.value, operation_id=condition.id,
            prompt=payload.text, prompt_sha256=payload.sha256))
    for name in sorted([*copies, "policy.json", "local-source.json"]):
        batch["evidence"].append(dict(path=name, purpose="frozen experiment input", sha256=digest(inputs / name)))
    atomic_json(inputs / "batch.json", batch)
    lines = ["# Alpha preflight freeze", "", f"Run: {run_id}", f"Host: {host}",
             "", "Twenty attempts; at least ten readable decisions; no replacement attempts.",
             "Correctness is graded separately. All attempted failures stay in the denominator.",
             "Fresh process per attempt; throughput includes model loading.", "",
             "## Policy", "", "```json", json.dumps(POLICY, indent=2), "```", "",
             "## Input hashes", ""]
    for path in sorted(inputs.rglob("*")):
        if path.is_file():
            lines.append(f"- `{path.relative_to(inputs)}`: `{digest(path)}`")
    lines += ["", "## Exact schedule", ""]
    lines += [f"- {a['attempt_id']}: `{a['condition_id']}`; prompt `{a['prompt_sha256']}`"
              for a in batch["attempts"]]
    lines += ["", "Review batch.json for exact prompts and approval.md/grading-key.md for the human decisions.",
              "Tokenized prompt lengths and environment identity are checked on Alpha before any attempt.",
              "Outcome precedence: timeout > error > truncated > refusal > malformed > invalid_choice > decision.",
              "Refusal classification is disabled for this experiment.", ""]
    (inputs / "preflight.md").write_text("\n".join(lines), encoding="utf-8")
    state = dict(format="lantern.alpha.progress", version=1, run_id=run_id, host=host,
                 phase="prepared", job_id=None, operations=[], fetched=None,
                 input_hashes={str(p.relative_to(inputs)): digest(p)
                               for p in inputs.rglob("*") if p.is_file()})
    atomic_json(out / "progress.json", state)
    return dict(run_id=run_id, preflight_sha256=digest(inputs / "preflight.md"),
                next="Review the frozen inputs before human-operated submit")


def helper(run: Path, state: dict, *args: str) -> str:
    operation = len(state["operations"])
    entry = dict(command=list(args), stdout=f"operation-{operation:04d}.out",
                 stderr=f"operation-{operation:04d}.err", returncode=None)
    state["operations"].append(entry)
    atomic_json(run / "progress.json", state)
    env = os.environ.copy()
    env["ALPHA_HOST"] = state["host"]
    with (run / entry["stdout"]).open("x") as stdout, (run / entry["stderr"]).open("x") as stderr:
        result = subprocess.run(["bash", str(ROOT / "tools/alpha_submit.sh"), *args],
                                env=env, stdout=stdout, stderr=stderr, check=False)
    entry["returncode"] = result.returncode
    atomic_json(run / "progress.json", state)
    if result.returncode:
        raise BatchError(f"Transport failed; inspect {entry['stderr']}; submission is never retried")
    return (run / entry["stdout"]).read_text()


def submit(run: Path, approved_sha256: str) -> dict:
    with locked(run):
        state = load_state(run)
        verify_inputs(run, state)
        if approved_sha256 != digest(run / "inputs/preflight.md"):
            raise BatchError("Preflight approval hash does not match")
        if state["phase"] != "prepared":
            raise BatchError("Submission already attempted; use resume, never submit again")
        inputs = run / "inputs"
        # Persist intent before any remote operation, including upload.
        state["phase"] = "submission_uncertain"
        atomic_json(run / "progress.json", state)
        paths = [str(p) for p in sorted(inputs.iterdir()) if p.name != "job.sbatch"]
        output = helper(run, state, "submit", "--run-id", state["run_id"],
                        str(inputs / "job.sbatch"), *paths)
        match = re.search(r"^Job ID: ([0-9]+(?:;[A-Za-z0-9_-]+)?)$", output, re.M)
        if not match:
            raise BatchError("No valid job receipt; use resume to inspect the existing remote run")
        state.update(job_id=match[1], phase="submitted")
        atomic_json(run / "progress.json", state)
        return dict(phase=state["phase"], job_id=state["job_id"])


TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY",
            "NODE_FAIL", "PREEMPTED", "BOOT_FAIL", "DEADLINE", "REVOKED"}


def accounting(output: str, receipt: str) -> tuple[str, str] | None:
    """Require unambiguous root-job accounting and no queue entry for that job."""
    if output.count("QUEUE\n") != 1 or output.count("ACCOUNTING\n") != 1:
        raise BatchError("Invalid status observation")
    queue, account = output.split("ACCOUNTING\n")
    if not queue.startswith("QUEUE\n"):
        raise BatchError("Invalid queue observation")
    root = receipt.split(";")[0]
    queue_rows = [line.strip().split("|") for line in queue[len("QUEUE\n"):].splitlines() if line.strip()]
    if any(len(row) != 2 for row in queue_rows):
        raise BatchError("Malformed queue observation")
    rows = [line.strip().split("|") for line in account.splitlines() if line.strip()]
    root_rows = [r for r in rows if r[0] == root]
    if len(root_rows) != 1:
        return None
    row = root_rows[0]
    if len(row) != 3 or not re.fullmatch(r"[0-9]+:[0-9]+", row[2]):
        raise BatchError("Malformed terminal accounting")
    # Slurm may append a cancellation UID or truncate long states with '+'.
    state = row[1].split()[0] if row[1].split() else ""
    if state not in TERMINAL or any(row[0] == root for row in queue_rows):
        return None
    if state == "COMPLETED" and row[2] != "0:0":
        raise BatchError("COMPLETED accounting has a nonzero exit code")
    return state, row[2]


def finish(run: Path, state: dict) -> dict:
    bundle = run / state["fetched"]
    verify_inputs(run, state, bundle)
    batch = read_json(bundle / "batch.json")
    if batch["run_id"] != state["run_id"]:
        raise BatchError("Fetched run identity differs")
    # Record every fetched file hash, including logs the immutable batch could
    # not inventory before execution. Symlinks are refused, never followed.
    source_hashes = {}
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise BatchError("Fetched evidence contains a symlink")
        if path.is_file():
            source_hashes[str(path.relative_to(bundle))] = digest(path)
    if state.get("fetched_hashes") is not None and source_hashes != state["fetched_hashes"]:
        raise BatchError("Retained evidence changed after fetch")
    state["fetched_hashes"] = source_hashes
    atomic_json(run / "progress.json", state)
    throughput = read_json(bundle / "execution-summary.json")
    if not isinstance(throughput, dict):
        raise BatchError("Missing or inconsistent execution timing")
    elapsed = throughput.get("elapsed_seconds")
    if (type(elapsed) not in (int, float) or elapsed <= 0
            or isinstance(elapsed, float) and not math.isfinite(elapsed)
            or type(throughput.get("attempted")) is not int
            or not 0 <= throughput["attempted"] <= len(batch["attempts"])):
        raise BatchError("Missing or inconsistent execution timing")
    result_rows = [alpha_import._json(line, f"results.jsonl:{index}")
                   for index, line in enumerate((bundle / "results.jsonl").read_bytes().splitlines(), 1)]
    scheduled = {attempt["attempt_id"] for attempt in batch["attempts"]}
    # Full envelope validation remains the importer's responsibility. Only
    # compare counts for a complete set of terminal identities; incomplete or
    # duplicate results will be rejected by the importer before any append.
    if (len(result_rows) == len(scheduled)
            and all(isinstance(row, dict) and isinstance(row.get("attempt_id"), str) for row in result_rows)
            and {row["attempt_id"] for row in result_rows} == scheduled):
        attempted = sum(row.get("status") != "not_started" for row in result_rows)
        if throughput["attempted"] != attempted:
            raise BatchError("Missing or inconsistent execution timing")
    dataset = run / "dataset"
    dataset.mkdir(exist_ok=True)
    report = alpha_import.import_bundle(bundle, cases_dir=bundle / "cases",
                                       attempts_path=dataset / "attempts.jsonl")
    atomic_json(dataset / "import-report.json", report.as_dict())
    records = (list(read_attempts(dataset / "attempts.jsonl"))
               if (dataset / "attempts.jsonl").exists() else [])
    if throughput["attempted"] != len(records):
        raise BatchError("Dataset count differs from validated execution timing")
    cases = load_cases(bundle / "cases")
    conditions = tuple(c for case in cases for c in expand(case.id, reruns=4))
    analysis = summarize(records, conditions)
    write_export(dataset / "export.json", build_export(cases=cases, conditions=conditions,
        records=records, analysis=analysis, label=("Synthetic Alpha workflow fixture"
            if batch["synthetic"] else "Alpha fixed twenty-attempt experiment")))
    decisions = sum(row["outcome"] == "decision" for row in records)
    summary = dict(synthetic=batch["synthetic"], scheduled=20, attempted=len(records), decisions=decisions,
                   not_started=list(report.not_started),
                   gate_passed=len(records) == 20 and decisions >= 10,
                   analysis=analysis.as_dict(), source_hashes=source_hashes,
                   accounting=state["accounting"], throughput=throughput)
    summary["decisions_per_second"] = decisions / throughput["elapsed_seconds"]
    atomic_json(dataset / "summary.json", summary)
    state["phase"] = "complete"
    atomic_json(run / "progress.json", state)
    return summary


def resume(run: Path) -> dict:
    with locked(run):
        state = load_state(run)
        verify_inputs(run, state)
        if state["phase"] == "prepared":
            raise BatchError("No submission attempted; review preflight and use submit")
        if not state["job_id"]:
            receipt = helper(run, state, "receipt", state["run_id"]).strip()
            if JOB.fullmatch(receipt) is None:
                raise BatchError("Submission remains uncertain; inspect receipt and queue manually")
            state.update(job_id=receipt, phase="submitted")
            atomic_json(run / "progress.json", state)
        if not state.get("fetched"):
            output = helper(run, state, "observe", state["job_id"])
            terminal = accounting(output, state["job_id"])
            if terminal is None:
                return dict(phase="waiting", job_id=state["job_id"],
                            note="Running, missing, or contradictory accounting; resume later")
            state["accounting"] = dict(state=terminal[0], exit_code=terminal[1])
            # Interrupted/failed fetches get a new path. No partial is removed.
            name = f"fetch-{len(state['operations']):04d}"
            helper(run, state, "fetch", state["run_id"], str(run / name))
            state.update(fetched=name, phase="fetched")
            atomic_json(run / "progress.json", state)
        return finish(run, state)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare", help="freeze local inputs; no network or model")
    for name in ("cases", "grading-key", "approval", "out", "host"):
        p.add_argument("--" + name, required=True)
    p = commands.add_parser("submit", help="human-operated: upload and submit exactly once")
    p.add_argument("--run", required=True)
    p.add_argument("--approved-preflight-sha256", required=True)
    p = commands.add_parser("resume", help="human-operated: observe, fetch, import, export")
    p.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            report = prepare(cases_dir=Path(args.cases), grading_key=Path(args.grading_key),
                             approval=Path(args.approval), out=Path(args.out).absolute(), host=args.host)
        elif args.command == "submit":
            report = submit(Path(args.run).absolute(), args.approved_preflight_sha256)
        else:
            report = resume(Path(args.run).absolute())
    except (OSError, ValueError, TypeError, NotImplementedError) as exc:
        print(json.dumps(dict(error=str(exc))), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
