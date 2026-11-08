"""Execute a frozen Alpha batch offline, with one bounded process per attempt.

No installer, download, model selection, parser, or task grading lives here.
Run only inside the approved Slurm allocation using the existing environment.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

MODEL = "Qwen/Qwen3-4B-Instruct-2507"
REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
POLICY = dict(input_limit=1024, max_new_tokens=128, eos_token_id=[151645, 151643],
              do_sample=False, num_beams=1, seed=1, use_model_defaults=False,
              attempt_timeout_seconds=60, repetitions=4, scheduled=20,
              minimum_decisions=10)


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"Duplicate JSON key: {key}")
            value[key] = item
        return value

    def invalid(value):
        raise ValueError(f"Non-finite number: {value}")

    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def write(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_batch(root, batch):
    if read(root / "policy.json") != POLICY:
        raise ValueError("Policy differs from the approved bounded experiment")
    identity = batch["identity"]
    expected = dict(execution_site="alpha_batch", model_id=MODEL, model_revision=REVISION,
                    harness="transformers", harness_version="4.57.1")
    if (batch["format"] != "lantern.alpha.batch" or batch["schema_version"] != 0
            or batch["synthetic"] is not False or batch["purpose"] not in ("experimental", "pilot")
            or identity != expected):
        raise ValueError("Not the approved Alpha experimental identity")
    attempts = batch["attempts"]
    arms = ("baseline", "unchanged_rerun", "neutral_edit", "framing", "correction")
    if len(attempts) != 20 or len({a["case_id"] for a in attempts}) != 1:
        raise ValueError("Expected twenty attempts for one case")
    for index, attempt in enumerate(attempts):
        arm, repetition = arms[index // 4], index % 4
        condition = f"{attempt['case_id']}:{arm}:{repetition}"
        if (attempt["attempt_id"] != f"attempt-{index:02d}" or attempt["arm"] != arm
                or attempt["condition_id"] != condition or attempt["operation_id"] != condition
                or hashlib.sha256(attempt["prompt"].encode()).hexdigest() != attempt["prompt_sha256"]):
            raise ValueError("Attempt schedule or prompt hash differs")
    for entry in batch["evidence"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe supporting evidence path")
        path = root / relative
        if any(p.is_symlink() for p in (path, *path.parents)) or file_hash(path) != entry["sha256"]:
            raise ValueError("Supporting evidence changed")


def tokenize_batch(tokenizer, attempts):
    observations = []
    for attempt in attempts:
        ids = tokenizer.apply_chat_template(
            [{"role": "user", "content": attempt["prompt"]}],
            tokenize=True, add_generation_prompt=True)
        if not 0 < len(ids) <= POLICY["input_limit"]:
            raise ValueError(f"{attempt['attempt_id']}: prompt exceeds 1024 tokens; no truncation allowed")
        observations.append(dict(attempt_id=attempt["attempt_id"], input_ids=ids,
            rendered_prompt=tokenizer.decode(ids, skip_special_tokens=False), prompt_tokens=len(ids)))
    return observations


def preflight(root, model_dir, batch):
    validate_batch(root, batch)
    spec = importlib.util.spec_from_file_location("diagnostic", root / "alpha-inference-diagnostic.py")
    diagnostic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostic)
    packages = diagnostic.check_packages(root / "installed-packages.txt")
    snapshot = diagnostic.check_snapshot(model_dir, read(root / "inference-result.json"))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
    if tokenizer.eos_token_id != 151645 or tokenizer.pad_token_id != 151643:
        raise ValueError("Tokenizer special-token identity differs")
    tokenized = tokenize_batch(tokenizer, batch["attempts"])
    write(root / "tokenized.json", tokenized)
    write(root / "runtime-preflight.json", dict(packages=packages, snapshot_sha256=snapshot,
        hostname=platform.node(), job_id=os.environ.get("SLURM_JOB_ID"),
        python=sys.version, policy=POLICY, checked_utc=utc()))


def termination(generated):
    # EOS at exactly the cap is completion, not truncation.
    if generated and generated[-1] in POLICY["eos_token_id"]:
        return "eos"
    if len(generated) == POLICY["max_new_tokens"]:
        return "token_limit"
    return "unknown"


def worker(root, model_dir, index):
    batch = read(root / "batch.json")
    attempt = batch["attempts"][index]
    observed = read(root / "tokenized.json")[index]
    started = time.perf_counter()
    receipt = dict(started_utc=utc(), attempt_id=attempt["attempt_id"], stage="loading",
                   prompt_sha256=attempt["prompt_sha256"], raw_output=None)
    target = root / f"worker-{index:02d}.json"
    write(target, receipt)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Expected one allocated CUDA device")
    torch.manual_seed(POLICY["seed"])
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(model_dir), local_files_only=True,
        trust_remote_code=False, use_safetensors=True, dtype=torch.bfloat16,
        device_map={"": "cuda:0"}, attn_implementation="sdpa")
    model.eval()
    if any(p.device.type != "cuda" or p.device.index != 0 or
           (p.is_floating_point() and p.dtype != torch.bfloat16) for p in model.parameters()):
        raise RuntimeError("Model is not entirely BF16 on cuda:0")
    config = GenerationConfig(eos_token_id=POLICY["eos_token_id"],
        pad_token_id=tokenizer.pad_token_id, bos_token_id=tokenizer.bos_token_id,
        do_sample=False, num_beams=1, max_new_tokens=128, min_new_tokens=0, use_cache=True)
    effective, kwargs = model._prepare_generation_config(config, use_model_defaults=False)
    if (effective.get_generation_mode().value != "greedy_search"
            or effective.eos_token_id != POLICY["eos_token_id"] or effective.max_new_tokens != 128
            or effective.min_new_tokens != 0 or effective.num_beams != 1):
        raise RuntimeError("Effective decoding differs from the approved policy")
    ids = torch.tensor([observed["input_ids"]], device="cuda:0", dtype=torch.long)
    torch.cuda.synchronize()
    receipt.update(stage="generating", load_seconds=time.perf_counter() - started,
                   effective_generation_config=effective.to_dict(), prompt_tokens=len(observed["input_ids"]),
                   context_limit=model.config.max_position_embeddings)
    write(target, receipt)
    generation_start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                                generation_config=effective, use_model_defaults=False, **kwargs)
    torch.cuda.synchronize()
    generated = output[0, ids.shape[1]:].tolist()
    if not 0 < len(generated) <= 128:
        raise RuntimeError("Generated token count outside the bound")
    receipt.update(stage="complete", generation_seconds=time.perf_counter() - generation_start,
        generated_token_ids=generated, completion_tokens=len(generated),
        raw_output=tokenizer.decode(generated, skip_special_tokens=True),
        termination_reason=termination(generated), runtime_seconds=time.perf_counter() - started,
        finished_utc=utc(), context_limit=model.config.max_position_embeddings,
        peak_memory_bytes=torch.cuda.max_memory_reserved(0),
        peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
        device_name=torch.cuda.get_device_name(0), device_total_bytes=torch.cuda.get_device_properties(0).total_memory)
    write(target, receipt)


class ExecutionStopped(Exception):
    pass


def stop(signum, frame):
    raise ExecutionStopped(f"Supervisor received signal {signum}")


def bounded_process(command, stdout, stderr, timeout):
    """Supervise from the main thread; kill/reap a worker before unwinding."""
    process = None
    pending = []
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}

    def defer(signum, frame):
        pending.append(signum)

    def restore_handlers():
        for sig, handler in handlers.items():
            signal.signal(sig, handler)

    try:
        # A raising handler inside Popen can lose the newly created child's
        # handle. Defer just that exception until assignment is complete.
        # No signal mask is changed or inherited by the worker.
        for sig in handlers:
            signal.signal(sig, defer)
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        restore_handlers()
        if pending:
            raise ExecutionStopped(f"Supervisor received signal {pending[0]} during worker launch")
        return process.wait(timeout=timeout)
    except BaseException:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    finally:
        restore_handlers()


def worker_receipt(root, index):
    path = root / f"worker-{index:02d}.json"
    receipt = read(path) if path.exists() else {}
    if not isinstance(receipt, dict):
        raise ValueError("Worker receipt must be a JSON object")
    return receipt


def result_for(batch, attempt, status, error=None, receipt=None):
    receipt = receipt or {}
    provenance = batch["identity"].copy()
    for name in ("started_utc", "finished_utc", "runtime_seconds", "prompt_tokens",
                 "completion_tokens", "peak_memory_bytes", "context_limit"):
        if name in receipt:
            provenance[name] = receipt[name]
    if "effective_generation_config" in receipt:
        provenance.update(dtype="bfloat16", max_new_tokens=128, seed=1)
        for name in ("temperature", "top_p"):
            provenance[name] = receipt["effective_generation_config"].get(name)
    return dict(attempt_id=attempt["attempt_id"], prompt_sha256=attempt["prompt_sha256"],
        status=status, termination_reason=receipt["termination_reason"] if status == "returned" else "unknown",
        raw_output=receipt.get("raw_output") if status != "not_started" else None,
        provenance=provenance, errors=[error] if error else [])


def supervise(root, model_dir):
    batch = read(root / "batch.json")
    # Refuse remote re-execution, even after interruption. Local resume fetches
    # this run; a new job needs a separately reviewed run identity.
    with (root / "execution-started.json").open("x") as marker:
        json.dump(dict(started_utc=utc(), job_id=os.environ.get("SLURM_JOB_ID")), marker)
        marker.flush()
        os.fsync(marker.fileno())
    started = time.perf_counter()
    results, timings = [], []
    active_attempt = None
    error = None
    try:
        preflight(root, model_dir, batch)
        for index, attempt in enumerate(batch["attempts"]):
            begin = time.perf_counter()
            active_attempt = attempt
            with (root / f"worker-{index:02d}.out").open("x") as stdout, (root / f"worker-{index:02d}.err").open("x") as stderr:
                try:
                    rc = bounded_process([sys.executable, "-I", "-u", "-B", str(Path(__file__).resolve()),
                        "--root", str(root), "--model-dir", str(model_dir), "--worker", str(index)],
                        stdout, stderr, POLICY["attempt_timeout_seconds"])
                    status = "returned" if rc == 0 else "error"
                    detail = None if rc == 0 else f"Worker exited {rc}; see worker-{index:02d}.err"
                except subprocess.TimeoutExpired:
                    status, detail = "timeout", "Attempt exceeded 60 seconds including model loading"
            elapsed = time.perf_counter() - begin
            receipt = worker_receipt(root, index)
            if status == "returned" and receipt.get("stage") != "complete":
                status, detail = "error", "Worker exited without a complete receipt"
            receipt["runtime_seconds"] = elapsed
            results.append(result_for(batch, attempt, status, detail, receipt))
            active_attempt = None
            timings.append(dict(attempt_id=attempt["attempt_id"], elapsed_seconds=elapsed,
                                load_seconds=receipt.get("load_seconds"),
                                generation_seconds=receipt.get("generation_seconds")))
            # A durable prefix is evidence, not a complete importable bundle.
            write(root / "execution-prefix.json", results)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        if active_attempt is not None and len(results) <= index:
            try:
                receipt = worker_receipt(root, index)
            except (OSError, ValueError) as receipt_error:
                error += f"; unreadable worker receipt: {receipt_error}"
                receipt = {}
            receipt["runtime_seconds"] = time.perf_counter() - begin
            results.append(result_for(batch, active_attempt, "error", error, receipt))
            timings.append(dict(attempt_id=active_attempt["attempt_id"],
                elapsed_seconds=receipt["runtime_seconds"], load_seconds=receipt.get("load_seconds"),
                generation_seconds=receipt.get("generation_seconds")))
    finally:
        for attempt in batch["attempts"][len(results):]:
            results.append(result_for(batch, attempt, "not_started", error or "Supervisor stopped before dispatch"))
        with (root / "results.jsonl").open("x") as stream:
            for row in results:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        elapsed = time.perf_counter() - started
        attempted = sum(r["status"] != "not_started" for r in results)
        write(root / "execution-summary.json", dict(elapsed_seconds=elapsed, attempted=attempted,
            attempts_per_second=attempted / elapsed, includes_preflight_and_model_loading=True,
            timings=timings, error=error, memory_scope="PyTorch allocator; not total device memory"))
    return 1 if error else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--worker", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.worker is not None:
        worker(root, args.model_dir, args.worker)
        return 0
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Requires an approved Slurm allocation")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    return supervise(root, args.model_dir)


if __name__ == "__main__":
    raise SystemExit(main())
