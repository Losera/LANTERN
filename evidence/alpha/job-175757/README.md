# Alpha tensor runtime observation: job 175757

Retained from the human-operated run on November 8, 2026 UTC. The seven original
files are copied unchanged; [retention hashes](retained-sha256.json) cover them.
The human reported Slurm `COMPLETED`, exit code `0:0`; a separate raw accounting
capture has not yet been retained.

The [log](lantern-runtime-setup-175757.out) records Python 3.12.3,
PyTorch 2.9.1+cu126, CUDA available on an H100 MIG 1g.10gb slice, a tensor on
`cuda:0`, sum of squares `14.0`, and `GPU calculation passed`. Package checks
reported no broken requirements. NumPy was absent; that warning did not prevent
this tensor calculation.

The environment is recorded in [environment-path.txt](environment-path.txt).
The environment itself is not in this evidence directory or in Git.

This establishes GPU tensor computation, not model inference. The later
[job 175794](../job-175794/README.md) establishes one model response, with a
generation-setting discrepancy retained explicitly.
