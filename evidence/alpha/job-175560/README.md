# Alpha allocation evidence: Slurm job 175560

Retained output from the first Alpha job this project ran. It satisfies the
allocation gate in [Alpha constraints](../../../docs/alpha.md): a job of our own
with its job ID, the resources actually assigned, and the MIG identity.

These are the unedited files the job produced, copied back by
`bash tools/alpha_submit.sh fetch`. They are kept because the measurement is not
reproducible on demand: the reservation is event-scoped and the allocation is
transient.

| File | What it is |
| --- | --- |
| `job.sbatch` | The submitted script, as Slurm received it |
| `submission.txt` | Slurm's receipt, written remotely before being printed locally |
| `lantern-smoke-175560.out` | The job's stdout |

## What this establishes

| Observation | Value |
| --- | --- |
| Slurm job ID | 175560 |
| Compute node | `alphagpu01` |
| Parent GPU | NVIDIA H100 80GB HBM3 |
| Assigned slice | MIG 1g.10gb, UUID `MIG-268907a6-d048-527d-bdd3-13b682d69f36` |
| Account | `rpicourse`, accepted |
| Reservation | `binghamton_hackathon`, accepted |

The account flag matters because [Alpha constraints](../../../docs/alpha.md)
records it as unconfirmed during planning. This job confirms it is accepted.

## What this does not establish

The job ran `hostname` and `nvidia-smi -L`. It loaded no model, installed
nothing, and performed no CUDA computation, so it says nothing about GPU
inference, task competence, or throughput. A parent H100 listing does not grant
its 80 GB: the slice is 10 GB, and weights, activations, KV cache, and runtime
overhead must fit inside it.

The remaining gates are tracked in
[issue 10](https://github.com/Losera/LANTERN/issues/10). The next one is a short
GPU inference; `examples/alpha-runtime-probe.sbatch` is the diagnostic prepared
for it, and it has not been run here.
