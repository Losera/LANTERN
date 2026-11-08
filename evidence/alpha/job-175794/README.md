# Alpha model inference observation: job 175794

Retained from the human-operated run on November 8, 2026 UTC, on `alphagpu01`.
The fourteen original files are copied unchanged; [retention hashes](retained-sha256.json)
cover them. [Input hashes](input-sha256.txt) match all four retained submission
files. The human reported Slurm `COMPLETED`, exit code `0:0`; a separate raw
accounting capture has not yet been retained. [Job status](job-status.json) records
the shell's exit code 0 and completed stage; it is not Slurm accounting.

## Observed GPU response

[The result](inference-result.json) and [log](lantern-inference-175794.out) record:

| Measurement | Observation |
| --- | --- |
| Model | Qwen/Qwen3-4B-Instruct-2507 |
| Model and tokenizer revision | cdbee75f17c01a7cc42f958dc650907174af0554 |
| Execution | Alpha batch, H100 MIG 1g.10gb, BF16, batch 1 |
| Input | 16 tokens including chat template |
| Output | `GPU inference ready.`; five generated tokens including EOS |
| Download / loading / generation | 25.4045 / 2.8380 / 3.8306 seconds |
| Peak allocated / reserved | 8,090,114,560 / 8,111,783,936 bytes |
| Reported slice memory | 10,468,982,784 bytes |

Memory measurements cover PyTorch's allocator during loading and generation,
not all device allocations. This short prompt does not prove fit at the full
1,024-input/128-output budget. The one response is not a throughput benchmark or
evidence of ten valid task decisions.

## Decoding discrepancy: preserve, do not overwrite

The result JSON contains the requested `do_sample: false` configuration. The
log then reports that Transformers modified model-specific defaults, including
`do_sample: True`, temperature 0.7, top_k 20, and top_p 0.8. Therefore this must
not be described as a verified greedy run. The GPU response and memory
observation remain valid.

The [Transformers 4.57.1 implementation](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/generation/utils.py)
copies global-default values from the model configuration unless model defaults
are disabled; explicit generation keyword arguments take precedence. The
original probe recorded its configuration before this resolution and missed the
change. A corrected diagnostic must test actual resolution and record the
effective configuration before the ten-decision gate proceeds.

Original JSON, scripts, and logs are retained verbatim. This annotation does not
retroactively alter them. Executed scripts here are historical evidence, not a
recommendation to resubmit an installation job.

## Reuse and remaining gates

The existing environment and model paths are retained in
[environment-path.txt](environment-path.txt) and [model-path.txt](model-path.txt).
They live outside the fetched run directory and are not in Git. The package
freeze and both pip reports retain installed versions and artifact hashes;
transitive inference dependencies were resolved at install time.

Next: a corrected greedy smoke response and full-budget capacity diagnostic,
reusing these paths without installation or downloads. Ten valid decisions wait
for approved cases and matching/refusal/truncation rules. Alpha runner
integration remains separate from these standalone probes.
