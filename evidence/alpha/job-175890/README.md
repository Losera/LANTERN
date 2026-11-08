# Alpha greedy and capacity diagnostic: job 175890

Retained from the human-operated run on November 8, 2026 UTC, on `alphagpu01`,
Slurm job 175890. The operator's run ID is `20261108T024353Z-1034773-13886`; no
retained file contains it, so it is the one identifier here with no machine
source. The ten retained files are covered by retention hashes in
[retained-sha256.json](retained-sha256.json). Two of them are inputs rather
than results, so the table below records each file's origin.

This is the corrected diagnostic that [job 175794](../job-175794/README.md)
called for. It reuses that job's environment and model, with no installation,
download, quantization, offloading, or model substitution. The receipt
[diagnostic-result.json](diagnostic-result.json) is the primary record; the
measurement table below is a reading of it.

| File | Origin and content |
| --- | --- |
| `job.sbatch` | The submitted script, as Slurm received it; identical to the reviewed `examples/alpha-inference-diagnostic.sbatch` at `97e5018` |
| `alpha-inference-diagnostic.py` | The executed diagnostic; identical to the reviewed `examples/alpha-inference-diagnostic.py` at `97e5018` |
| `inference-result.json` | An input, not a result: the job 175794 baseline, byte-identical to the committed copy |
| `installed-packages.txt` | An input: the job 175794 package freeze, byte-identical to the committed copy |
| `input-sha256.txt` | The job's own digests of its four inputs, written before Python ran |
| `diagnostic-result.json` | The receipt: effective settings, token IDs, termination, timings, and allocator peaks |
| `lantern-diagnostic-175890.out` | The job's standard output and error |
| `submission.txt` | Slurm's parsable submission receipt, written remotely before being printed locally |
| `accounting.txt` | A human-created accounting capture; see the note below |
| `accounting.tx` | A second copy of the same capture under a shorter name, retained deliberately |

## Accounting is operator-attested

The operator reported Slurm `COMPLETED`, exit code `0:0`. The retained capture
is hand-made: it records no command, timestamp, or cluster, and its
pipe-delimited shape is not what `tools/alpha_submit.sh status` prints.
`accounting.tx` and `accounting.txt` have the same SHA-256, so they are one
capture under two names rather than two independent confirmations. Treat the
terminal state as operator attestation; every other observation below comes
from the machine files. A verbatim accounting capture is still worth retaining
for this job and for the two earlier ones, as [status](../../../docs/status.md)
records.

## What this establishes

| Measurement | Observation |
| --- | --- |
| Model and tokenizer revision | Qwen/Qwen3-4B-Instruct-2507 at `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Execution | Alpha batch, H100 MIG 1g.10gb, BF16, batch 1, `alphagpu01` |
| Assigned slice | MIG UUID `MIG-1b426bd2-3e0b-5557-b486-686f416d7b5c`, driver 580.126.09 |
| Preflight | 43 of 43 recorded package versions matched; 12 of 12 model snapshot hashes matched the baseline |
| Resolver regression | Legacy sampling override reproduced; the same installed resolver with explicit controls and model defaults disabled resolved to greedy search |
| Smoke probe | 16 input tokens, five generated, the exact phrase `GPU inference ready.`, EOS 151645, 1.8110 seconds |
| Capacity probe | 1,024 input tokens, 128 generated, cap-terminated, 40.0553 seconds |
| Loading / wall time | 2.4163 / 75.66 seconds |
| Peak allocated / reserved, capacity | 8,331,914,752 / 8,403,288,064 bytes |
| Peak allocated / reserved, smoke | 8,085,974,016 / 8,086,618,112 bytes |
| Reported slice memory | 10,468,982,784 bytes |

The log reports that `generation_config` default values were modified to
sampling values. That message comes from loading the model, not from either
probe. Both probes recorded `do_sample: false`, `num_beams: 1`, and greedy
search in their effective configuration, which is the receipt job 175794
lacked.

Memory measurements cover PyTorch's allocator, not all device allocations. The
CUDA context and library workspaces lie outside the allocator and were not
measured, so the apparent 2,065,694,720 bytes of headroom overstates free slice
memory by an unmeasured amount. Peak counters were reset before the capacity
probe, with resident weights still counted.

## What this does not establish

The capacity probe reached both bounds by configuration: minimum and maximum
new tokens were both 128, and the input is 1,016 repeated neutral filler tokens
inside an intact empty-user chat template. It shows that this shape's memory
and time cost fit the slice. It is not a task answer, cannot count toward the
ten-decision gate, and says nothing about whether the model would stop on its
own at the full budget. Its text is cut mid-sentence.

The regression reproduces the mechanism behind job 175794's discrepancy using
the actually installed Transformers 4.57.1. It is not a byte-exact replay of
that job's call and does not retroactively establish what job 175794 decoded.
Preserve that run's files and annotation unchanged.

Greedy decoding here rests on resolver inspection plus one consistent output.
The configuration was recorded before generation, which resolves again
internally, and no run was repeated, so determinism is not demonstrated.

Both probes ran with EOS token 151645 alone, while the checkpoint default is
151645 and 151643; nothing was misrecorded here, but the ten-decision harness
must choose its EOS set deliberately, because EOS termination is judged against
whichever set is in effect. That choice belongs with the gate's rules rather
than with this run.

Total device memory use, task competence, sustained throughput, framing
effects, and Alpha runner integration remain untested. Remaining gates are
tracked in [issue 10](https://github.com/Losera/LANTERN/issues/10); the next
inputs are the agreed cases and matching rules named in
[the runtime handoff](../../../docs/alpha-runtime-next.md) and
[Alpha constraints](../../../docs/alpha.md).

## Independent check

A read-only review on November 8, 2026 recomputed
[the input receipt](input-sha256.txt) and matched all four entries; compared
the retained script and job file against the committed blobs at `97e5018`;
confirmed that `inference-result.json` and `installed-packages.txt` are byte
identical to the committed job 175794 files; and re-derived the package,
snapshot, token, timing, and memory figures above from the receipt. It did not
run the diagnostic, reach Alpha, or verify Slurm accounting.
