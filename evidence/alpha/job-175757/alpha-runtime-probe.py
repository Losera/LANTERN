import sys

print("Python executable:", sys.executable, flush=True)
print("Python version: ", sys.version, flush=True)

import torch

print("PyTorch version: ", torch.__version__, flush=True)
print("PyTorch CUDA build: ", torch.version.cuda, flush=True)

cuda_available = torch.cuda.is_available()
print("Cuda available:", cuda_available, flush=True)

if not cuda_available:
    raise SystemExit("GPU Probe failed: CUDA unavailable")

print("GPU:", torch.cuda.get_device_name(0), flush=True)

x = torch.tensor([1.0, 2.0, 3.0], device="cuda")
print("Tensor device:", x.device, flush=True)

result = (x * x).sum().item()
print("Sum of squares:", result, flush=True)

if result != 14.0:
    raise SystemExit(f"GPU probe failed: expected 14.0, got {result}")

print("GPU calculation passed", flush=True)
