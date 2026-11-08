"""Offline diagnostic controls and receipts; real resolver check runs on Alpha."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diagnostic", ROOT / "examples/alpha-inference-diagnostic.py")
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class Config:
    def __init__(self, **kwargs):
        self.__dict__.update(do_sample=False, num_beams=1, max_new_tokens=None,
                             min_new_tokens=0, use_cache=True, eos_token_id=9)
        self.__dict__.update(kwargs)

    def get_generation_mode(self):
        return SimpleNamespace(value="sample" if self.do_sample else "greedy_search")

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        return cls(do_sample=True)


class Resolver:
    # Simulates precedence for control-flow tests; not evidence about Transformers.
    def _prepare_generation_config(self, config, use_model_defaults=None, **kwargs):
        result = copy.deepcopy(config)
        if use_model_defaults is not False:
            result.do_sample = self.generation_config.do_sample
        result.__dict__.update(kwargs)
        return result, {}


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model_dir = self.root / "model"
        self.model_dir.mkdir()
        hashes = {}
        for name in ("config.json", "model-1.safetensors"):
            (self.model_dir / name).write_bytes(b"fixture")
            hashes[name] = hashlib.sha256(b"fixture").hexdigest()
        self.baseline = dict(model_id=diagnostic.MODEL_ID, model_revision=diagnostic.REVISION,
                             tokenizer_revision=diagnostic.REVISION, snapshot_sha256=hashes)
        self.baseline_path = self.root / "baseline.json"
        self.baseline_path.write_text(json.dumps(self.baseline))
        self.freeze = self.root / "packages.txt"
        self.freeze.write_text("transformers==4.57.1\n")
        self.result = self.root / "diagnostic.json"
        self.tokenizer = MagicMock()
        self.tokenizer.eos_token_id = 9
        self.tokenizer.pad_token_id = 0
        self.tokenizer.bos_token_id = None
        self.tokenizer.all_special_ids = [9, 10]
        self.tokenizer.apply_chat_template.side_effect = lambda messages, **kw: (
            [10, 11, 12, 9, 13, 14, 15, 16] if messages[0]["content"] == ""
            else [10, 11, 12, 3, 4, 9, 13, 14, 15, 16])

        def decode(ids, **kwargs):
            if kwargs.get("skip_special_tokens"):
                return "GPU inference ready."
            return " ".join(map(str, ids))

        self.tokenizer.decode.side_effect = decode
        self.tokenizer.encode.side_effect = lambda text, **kw: [42] if text == " test" else list(map(int, text.split()))
        self.model = MagicMock()
        self.model.generation_config = Config(do_sample=True)
        self.model._prepare_generation_config.side_effect = lambda config, **kw: Resolver._prepare_generation_config(self.model, config, **kw)
        parameter = MagicMock()
        parameter.device.type = "cuda"
        parameter.device.index = 0
        parameter.dtype = "BF16"
        parameter.is_floating_point.return_value = True
        self.model.parameters.side_effect = lambda: iter([parameter])

        def generate(**kwargs):
            self.assertFalse(kwargs["use_model_defaults"])
            self.assertFalse(kwargs["do_sample"])
            self.assertEqual(kwargs["num_beams"], 1)
            output = MagicMock()
            output.__getitem__.return_value.tolist.return_value = (
                [1] * 128 if kwargs["min_new_tokens"] == 128 else [1, 2, 9])
            return output

        self.model.generate.side_effect = generate
        self.torch = MagicMock()
        self.torch.bfloat16 = "BF16"
        self.torch.cuda.is_available.return_value = True
        self.torch.cuda.is_bf16_supported.return_value = True
        self.torch.cuda.get_device_name.return_value = "MIG fixture"
        self.torch.cuda.get_device_properties.return_value.total_memory = 10 * 1024**3
        self.torch.cuda.max_memory_allocated.return_value = 8000
        self.torch.cuda.max_memory_reserved.return_value = 9000
        self.transformers = MagicMock()
        self.transformers.AutoModelForCausalLM.from_pretrained.return_value = self.model
        self.transformers.AutoTokenizer.from_pretrained.return_value = self.tokenizer
        self.transformers.GenerationConfig = Config
        self.modules = {"torch": self.torch, "transformers": self.transformers,
                        "transformers.generation.utils": SimpleNamespace(GenerationMixin=Resolver)}

    def execute(self):
        with patch.dict(sys.modules, self.modules), patch.object(diagnostic, "version", return_value="4.57.1"), \
             contextlib.redirect_stdout(io.StringIO()):
            diagnostic.run(self.model_dir, self.baseline_path, self.freeze, self.result)
        return json.loads(self.result.read_text())

    def test_resolver_disables_defaults_and_overrides_sampling(self):
        result = diagnostic.resolution_regression(Config, Resolver, self.model_dir)
        self.assertTrue(result["legacy_do_sample"])
        self.assertEqual(result["corrected_mode"], "greedy_search")
        self.assertFalse(result["corrected_config"]["do_sample"])

    def test_non_greedy_resolution_is_rejected(self):
        self.model._prepare_generation_config.side_effect = None
        self.model._prepare_generation_config.return_value = (Config(do_sample=True), {})
        with self.assertRaisesRegex(RuntimeError, "not greedy"):
            diagnostic.resolve_greedy(self.model, Config())

    def test_resolved_bound_drift_is_rejected(self):
        self.model._prepare_generation_config.side_effect = None
        self.model._prepare_generation_config.return_value = (Config(max_new_tokens=999), {})
        with self.assertRaisesRegex(RuntimeError, "controls differ"):
            diagnostic.resolve_greedy(self.model, Config())

    def test_capacity_input_has_exact_length_and_intact_template(self):
        ids = diagnostic.capacity_ids(self.tokenizer)
        self.assertEqual(len(ids), 1024)
        self.assertEqual(ids[:3], [10, 11, 12])
        self.assertEqual(ids[-5:], [9, 13, 14, 15, 16])

    def test_capacity_rejects_non_roundtripping_input(self):
        self.tokenizer.encode.side_effect = lambda text, **kw: [42]
        with self.assertRaisesRegex(ValueError, "round-trip"):
            diagnostic.capacity_ids(self.tokenizer)

    def test_package_drift_is_rejected(self):
        with patch.object(diagnostic, "version", return_value="different"):
            with self.assertRaisesRegex(RuntimeError, "Package drift"):
                diagnostic.check_packages(self.freeze)

    def test_snapshot_tampering_is_rejected(self):
        (self.model_dir / "model-1.safetensors").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            diagnostic.check_snapshot(self.model_dir, self.baseline)

    def test_wrong_revision_is_rejected(self):
        self.baseline["tokenizer_revision"] = "main"
        with self.assertRaisesRegex(ValueError, "revision"):
            diagnostic.check_snapshot(self.model_dir, self.baseline)

    def test_two_probes_record_effective_controls_and_memory(self):
        data = self.execute()
        self.assertEqual(data["status"], "passed")
        self.assertEqual(len(data["probes"]), 2)
        smoke, capacity = data["probes"]
        self.assertTrue(smoke["requested_phrase_matched"])
        self.assertTrue(smoke["terminated_with_eos"])
        self.assertEqual(capacity["prompt_tokens"], 1024)
        self.assertEqual(capacity["completion_tokens"], 128)
        self.assertTrue(capacity["synthetic_capacity_input"])
        self.assertTrue(capacity["reached_token_cap"])
        for observation in data["probes"]:
            self.assertEqual(observation["generation_mode"], "greedy_search")
            self.assertFalse(observation["effective_generation_config"]["do_sample"])
            self.assertEqual(observation["peak_reserved_bytes"], 9000)
        for loader in (self.transformers.AutoModelForCausalLM, self.transformers.AutoTokenizer):
            self.assertTrue(loader.from_pretrained.call_args.kwargs["local_files_only"])
            self.assertFalse(loader.from_pretrained.call_args.kwargs["trust_remote_code"])

    def test_capacity_oom_preserves_smoke_and_failure(self):
        generate = self.model.generate.side_effect

        def fail_capacity(**kwargs):
            if kwargs["min_new_tokens"] == 128:
                raise RuntimeError("CUDA out of memory")
            return generate(**kwargs)

        self.model.generate.side_effect = fail_capacity
        with self.assertRaisesRegex(RuntimeError, "out of memory"):
            self.execute()
        data = json.loads(self.result.read_text())
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["probes"][0]["status"], "passed")
        self.assertEqual(data["probes"][1]["status"], "failed")
        self.assertIn("traceback", data)
        self.assertEqual(data["last_phase_peak_reserved_bytes"], 9000)

    def test_existing_receipt_is_not_overwritten(self):
        self.result.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(self.result.read_text(), "keep")

    def test_capacity_preparation_failure_names_its_stage(self):
        with patch.object(diagnostic, "capacity_ids", side_effect=ValueError("invalid template")):
            with self.assertRaisesRegex(ValueError, "invalid template"):
                self.execute()
        data = json.loads(self.result.read_text())
        self.assertEqual(data["stage"], "capacity-1024-128-prepare")
        self.assertEqual(data["probes"][0]["status"], "passed")
        self.assertEqual(data["status"], "failed")

    def test_job_has_no_install_and_forces_offline_mode(self):
        path = ROOT / "examples/alpha-inference-diagnostic.sbatch"
        subprocess.run(["bash", "-n", str(path)], check=True)
        text = path.read_text()
        self.assertIn("HF_HUB_OFFLINE=1", text)
        self.assertIn("TRANSFORMERS_OFFLINE=1", text)
        self.assertNotIn("-m pip", text)
        self.assertNotIn("snapshot_download", text)
        self.assertIn("00:10:00", text)


if __name__ == "__main__":
    unittest.main()
