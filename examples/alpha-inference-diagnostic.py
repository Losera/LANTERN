"""Offline-model Alpha diagnostics; no installer, downloader, or runner adapter."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
from time import perf_counter
import traceback
from types import SimpleNamespace

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
PROMPT = "Reply with exactly: GPU inference ready."
INPUT_LIMIT = 1024
OUTPUT_LIMIT = 128


def check_packages(freeze):
    observed = {}
    for line in freeze.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==")
        actual = version(name)
        if actual != expected:
            raise RuntimeError(f"Package drift: {name}: expected {expected}, found {actual}")
        observed[name] = actual
    if not observed:
        raise ValueError("Empty package freeze")
    return observed


def check_snapshot(model_dir, baseline):
    if (baseline["model_id"], baseline["model_revision"], baseline["tokenizer_revision"]) != (MODEL_ID, REVISION, REVISION):
        raise ValueError("Baseline does not name the approved model/tokenizer revision")
    hashes = baseline["snapshot_sha256"]
    if not hashes or "config.json" not in hashes or not any(name.endswith(".safetensors") for name in hashes):
        raise ValueError("Baseline lacks model snapshot hashes")
    for name, expected in hashes.items():
        if Path(name).name != name or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid snapshot hash entry")
        digest = hashlib.sha256()
        with (model_dir / name).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"Snapshot hash mismatch: {name}")
    return hashes


def controls(capacity=False):
    # Explicit generate kwargs have precedence over model defaults in 4.57.1.
    return dict(do_sample=False, num_beams=1, max_new_tokens=OUTPUT_LIMIT,
                min_new_tokens=OUTPUT_LIMIT if capacity else 0, use_cache=True)


def resolve_greedy(model, config, capacity=False):
    settings = controls(capacity)
    effective, _ = model._prepare_generation_config(
        config, use_model_defaults=False, **settings,
    )
    if effective.get_generation_mode().value != "greedy_search":
        raise RuntimeError("Resolved generation mode is not greedy")
    if any(getattr(effective, key) != value for key, value in settings.items()):
        raise RuntimeError("Resolved generation controls differ from explicit settings")
    return effective, settings


def resolution_regression(GenerationConfig, GenerationMixin, model_dir):
    # Use the actual installed resolver, without loading weights or generating.
    defaults = GenerationConfig.from_pretrained(str(model_dir), local_files_only=True)
    if not defaults.do_sample:
        raise RuntimeError("Expected the pinned checkpoint's sampling default")
    receiver = SimpleNamespace(generation_config=defaults)
    legacy, _ = GenerationMixin._prepare_generation_config(receiver, GenerationConfig())
    if not legacy.do_sample:
        raise RuntimeError("The observed model-default override was not reproduced")
    receiver._prepare_generation_config = lambda config, **kw: GenerationMixin._prepare_generation_config(receiver, config, **kw)
    corrected, _ = resolve_greedy(receiver, GenerationConfig())
    return {"legacy_do_sample": legacy.do_sample,
            "corrected_mode": corrected.get_generation_mode().value,
            "corrected_config": corrected.to_dict()}


def capacity_ids(tokenizer):
    # Insert neutral tokens inside an otherwise intact empty-user chat template.
    ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": ""}], tokenize=True, add_generation_prompt=True,
    )
    filler = tokenizer.encode(" test", add_special_tokens=False)
    if len(filler) != 1 or filler[0] in tokenizer.all_special_ids:
        raise ValueError("Expected a single neutral filler token")
    if not 0 < len(ids) < INPUT_LIMIT:
        raise ValueError("Unexpected chat-template length")
    user_end = ids.index(tokenizer.eos_token_id)
    ids = ids[:user_end] + filler * (INPUT_LIMIT - len(ids)) + ids[user_end:]
    text = tokenizer.decode(ids, skip_special_tokens=False)
    if tokenizer.encode(text, add_special_tokens=False) != ids:
        raise ValueError("Capacity input does not round-trip through the tokenizer")
    return ids


def run(model_dir, baseline_path, freeze, result_path):
    with result_path.open("x", encoding="utf-8") as receipt:
        record = dict(status="running", stage="preflight", execution_site="alpha_batch",
                      model_id=MODEL_ID, model_revision=REVISION, tokenizer_revision=REVISION,
                      dtype="bfloat16", batch_size=1, hostname=platform.node(),
                      slurm_job_id=os.environ.get("SLURM_JOB_ID"), probes=[],
                      started_utc=datetime.now(timezone.utc).isoformat(),
                      memory_scope="PyTorch allocator, not total device allocations")
        torch = None
        measuring = False

        def save():
            receipt.seek(0)
            json.dump(record, receipt, indent=2, allow_nan=False)
            receipt.write("\n")
            receipt.truncate()
            receipt.flush()

        save()
        try:
            record["packages"] = check_packages(freeze)
            baseline = json.loads(baseline_path.read_text())
            record["snapshot_sha256"] = check_snapshot(model_dir, baseline)
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
            from transformers.generation.utils import GenerationMixin

            if version("transformers") != "4.57.1":
                raise RuntimeError("Resolver guard is pinned to Transformers 4.57.1")
            if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
                raise RuntimeError("CUDA with BF16 is required")
            torch.set_num_threads(1)
            record["gpu_name"] = torch.cuda.get_device_name(0)
            record["gpu_total_memory_bytes"] = torch.cuda.get_device_properties(0).total_memory
            record["stage"] = "resolution-regression"
            save()
            record["resolution_regression"] = resolution_regression(GenerationConfig, GenerationMixin, model_dir)
            record["stage"] = "load"
            save()
            torch.cuda.reset_peak_memory_stats(0)
            measuring = True
            torch.cuda.synchronize()
            started = perf_counter()
            tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
            model = AutoModelForCausalLM.from_pretrained(
                str(model_dir), local_files_only=True, trust_remote_code=False,
                use_safetensors=True, dtype=torch.bfloat16, device_map={"": "cuda:0"},
                attn_implementation="sdpa",
            )
            model.eval()
            if any(p.device.type != "cuda" or p.device.index != 0 or
                   (p.is_floating_point() and p.dtype != torch.bfloat16) for p in model.parameters()):
                raise RuntimeError("Model is not entirely BF16 on cuda:0")
            torch.cuda.synchronize()
            record["load_seconds"] = perf_counter() - started

            for name in ("greedy-smoke", "capacity-1024-128"):
                capacity = name.startswith("capacity")
                record["stage"] = name + "-prepare"
                save()
                if capacity:
                    # Reset after the smoke result was saved; resident weights remain counted.
                    torch.cuda.reset_peak_memory_stats(0)
                    ids = capacity_ids(tokenizer)
                else:
                    ids = tokenizer.apply_chat_template(
                        [{"role": "user", "content": PROMPT}], tokenize=True, add_generation_prompt=True,
                    )
                if not 0 < len(ids) <= INPUT_LIMIT:
                    raise ValueError("Prompt exceeds the input bound")
                config = GenerationConfig(
                    eos_token_id=tokenizer.eos_token_id, pad_token_id=tokenizer.pad_token_id,
                    bos_token_id=tokenizer.bos_token_id,
                )
                effective, settings = resolve_greedy(model, config, capacity)
                observation = dict(name=name, status="running", synthetic_capacity_input=capacity,
                                   prompt_tokens=len(ids), prompt_token_ids=ids,
                                   rendered_prompt=tokenizer.decode(ids, skip_special_tokens=False),
                                   generation_mode=effective.get_generation_mode().value,
                                   effective_generation_config=effective.to_dict(),
                                   explicit_generate_kwargs=dict(use_model_defaults=False, **settings))
                record["probes"].append(observation)
                record["stage"] = name
                save()
                inputs = torch.tensor([ids], device="cuda:0", dtype=torch.long)
                torch.cuda.synchronize()
                started = perf_counter()
                with torch.inference_mode():
                    output = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                                            generation_config=effective, use_model_defaults=False, **settings)
                torch.cuda.synchronize()
                observation["generation_seconds"] = perf_counter() - started
                generated = output[0, len(ids):].tolist()
                observation.update(generated_token_ids=generated, completion_tokens=len(generated),
                                   raw_output=tokenizer.decode(generated, skip_special_tokens=True),
                                   reached_token_cap=len(generated) == OUTPUT_LIMIT,
                                   peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                                   peak_reserved_bytes=torch.cuda.max_memory_reserved(0))
                eos = effective.eos_token_id
                eos_ids = eos if isinstance(eos, list) else [eos]
                observation["terminated_with_eos"] = bool(generated and generated[-1] in eos_ids)
                if not 0 < len(generated) <= OUTPUT_LIMIT:
                    raise RuntimeError("Invalid generated token count")
                if capacity:
                    if len(ids) != INPUT_LIMIT or len(generated) != OUTPUT_LIMIT:
                        raise RuntimeError("Capacity probe did not reach both requested bounds")
                else:
                    observation["requested_phrase_matched"] = observation["raw_output"].strip() == "GPU inference ready."
                    if not observation["raw_output"].strip():
                        raise RuntimeError("Smoke response was empty")
                observation["status"] = "passed"
                save()
                del inputs, output
            record.update(status="passed", stage="complete")
            print("Both Alpha diagnostic probes passed", flush=True)
        except Exception as exc:
            record.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
            if record["probes"] and record["probes"][-1]["status"] == "running":
                record["probes"][-1]["status"] = "failed"
            raise
        finally:
            if measuring:
                record["last_phase_peak_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
                record["last_phase_peak_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
            record["finished_utc"] = datetime.now(timezone.utc).isoformat()
            save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--baseline-result", type=Path, default=Path("inference-result.json"))
    parser.add_argument("--package-freeze", type=Path, default=Path("installed-packages.txt"))
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("Run inside a Slurm allocation")
    run(args.model_dir, args.baseline_result, args.package_freeze, Path("diagnostic-result.json"))
