"""Standalone Alpha smoke observation, independent of runner/model contracts."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
import traceback

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
PROMPT = "Reply with exactly: GPU inference ready."
INPUT_LIMIT = 1024
OUTPUT_LIMIT = 128
FILES = [
    "config.json", "generation_config.json", "tokenizer_config.json",
    "tokenizer.json", "vocab.json", "merges.txt", "model.safetensors.index.json",
    "model-*.safetensors", "LICENSE", "README.md",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run(model_dir, result_path):
    # Exclusive creation prevents accidental overwriting of a prior observation.
    with result_path.open("x", encoding="utf-8") as receipt:
        record = {
            "status": "running", "stage": "imports", "execution_site": "alpha_batch",
            "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
            "tokenizer_revision": MODEL_REVISION, "model_license": "Apache-2.0",
            "dtype": "bfloat16", "batch_size": 1,
            "input_limit": INPUT_LIMIT, "max_new_tokens": OUTPUT_LIMIT,
            "generation_settings": {"do_sample": False, "num_beams": 1,
                                    "max_new_tokens": OUTPUT_LIMIT},
            "messages": [{"role": "user", "content": PROMPT}],
            "started_utc": utc_now(), "python_executable": sys.executable,
            "python_version": sys.version, "hostname": platform.node(),
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "model_path": str(model_dir),
            "memory_scope": "PyTorch allocator, model loading plus generation; not total device usage",
        }
        torch = None
        memory_started = False

        def save():
            receipt.seek(0)
            json.dump(record, receipt, indent=2, allow_nan=False)
            receipt.write("\n")
            receipt.truncate()
            receipt.flush()

        save()
        try:
            import torch
            from huggingface_hub import snapshot_download
            from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

            record["packages"] = {name: version(name) for name in (
                "torch", "transformers", "accelerate", "numpy", "huggingface-hub",
                "tokenizers", "safetensors",
            )}
            record["cuda_build"] = torch.version.cuda
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable; CPU fallback is prohibited")
            if not torch.cuda.is_bf16_supported():
                raise RuntimeError("BF16 unavailable; precision fallback is prohibited")
            torch.set_num_threads(1)
            record["gpu_name"] = torch.cuda.get_device_name(0)
            record["gpu_total_memory_bytes"] = torch.cuda.get_device_properties(0).total_memory

            record["stage"] = "download"
            save()
            if model_dir.exists() or model_dir.is_symlink():
                raise FileExistsError(f"Refusing existing model directory: {model_dir}")
            start = perf_counter()
            snapshot = snapshot_download(
                repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=str(model_dir),
                allow_patterns=FILES, max_workers=1, token=False,
            )
            record["download_seconds"] = perf_counter() - start
            # Hash the actual snapshot files, excluding downloader metadata.
            record["stage"] = "hash-snapshot"
            save()
            hashes = {}
            for path in sorted(Path(snapshot).iterdir()):
                if path.is_file():
                    digest = hashlib.sha256()
                    with path.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                    hashes[path.name] = digest.hexdigest()
            record["snapshot_sha256"] = hashes

            record["stage"] = "load"
            save()
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats(0)
            memory_started = True
            start = perf_counter()
            tokenizer = AutoTokenizer.from_pretrained(
                snapshot, local_files_only=True, trust_remote_code=False,
            )
            model = AutoModelForCausalLM.from_pretrained(
                snapshot, local_files_only=True, trust_remote_code=False,
                use_safetensors=True, dtype=torch.bfloat16,
                device_map={"": "cuda:0"}, attn_implementation="sdpa",
            )
            model.eval()
            if any(p.device.type != "cuda" or p.device.index != 0 for p in model.parameters()):
                raise RuntimeError("Model parameters are not entirely on cuda:0")
            if any(p.is_floating_point() and p.dtype != torch.bfloat16 for p in model.parameters()):
                raise RuntimeError("Model parameters are not BF16")
            torch.cuda.synchronize()
            record["load_seconds"] = perf_counter() - start

            inputs = tokenizer.apply_chat_template(
                record["messages"], tokenize=True, add_generation_prompt=True,
                return_dict=True, return_tensors="pt",
            )
            input_ids = inputs["input_ids"]
            if input_ids.shape[0] != 1 or not 0 < input_ids.shape[1] <= INPUT_LIMIT:
                raise ValueError(f"Expected one nonempty prompt with at most {INPUT_LIMIT} tokens")
            record["prompt_token_ids"] = input_ids[0].tolist()
            record["prompt_tokens"] = input_ids.shape[1]
            record["rendered_prompt"] = tokenizer.decode(input_ids[0], skip_special_tokens=False)
            record["prompt_sha256"] = hashlib.sha256(record["rendered_prompt"].encode("utf-8")).hexdigest()
            inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
            # Fresh config avoids inheriting sampling/repetition settings from the checkpoint.
            config = GenerationConfig(
                do_sample=False, num_beams=1, max_new_tokens=OUTPUT_LIMIT,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
                bos_token_id=tokenizer.bos_token_id, use_cache=True,
            )
            record["generation_config"] = config.to_dict()
            record["stage"] = "generate"
            save()
            torch.cuda.synchronize()
            start = perf_counter()
            with torch.inference_mode():
                output = model.generate(**inputs, generation_config=config)
            torch.cuda.synchronize()
            record["generation_seconds"] = perf_counter() - start
            generated = output[0, input_ids.shape[1]:].tolist()
            record["generated_token_ids"] = generated
            record["completion_tokens"] = len(generated)
            record["reached_token_cap"] = len(generated) == OUTPUT_LIMIT
            record["raw_output"] = tokenizer.decode(generated, skip_special_tokens=True)
            record["requested_phrase_matched"] = record["raw_output"].strip() == "GPU inference ready."
            if not 0 < len(generated) <= OUTPUT_LIMIT or not record["raw_output"].strip():
                raise RuntimeError("Generation returned empty text or violated the output bound")
            record["status"] = "passed"
            record["stage"] = "complete"
            print("GPU inference passed", flush=True)
            print(record["raw_output"], flush=True)
        except Exception as exc:
            record["status"] = "failed"
            record["error_type"] = type(exc).__name__
            record["error"] = str(exc)
            record["traceback"] = traceback.format_exc()
            raise
        finally:
            if memory_started:
                record["peak_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
                record["peak_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
            record["finished_utc"] = utc_now()
            save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        parser.error("Run inside a Slurm allocation")
    run(args.model_dir, Path("inference-result.json"))


if __name__ == "__main__":
    main()
