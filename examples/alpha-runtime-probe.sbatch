#!/bin/bash
#SBATCH -p alpha
#SBATCH --account=rpicourse
#SBATCH --reservation=binghamton_hackathon
#SBATCH --gres=gpu:1g.10gb:1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 00:10:00
#SBATCH -J lantern-runtime-probe
#SBATCH -o %x-%j.out

# Runtime diagnostic only: no model, installation, or download.
# Submit from a directory containing alpha-runtime-probe.py.
set -euo pipefail

date -u
hostname
printf 'Slurm job: %s\n' "$SLURM_JOB_ID"
nvidia-smi -L

if ! type module >/dev/null 2>&1; then
    printf 'Runtime probe failed: module command unavailable in batch shell.\n' >&2
    exit 1
fi
module load Python/3.10.15
module list 2>&1

printf '\nCompute-node OS:\n'
cat /etc/os-release

printf '\nPython shared-library dependencies:\n'
ldd /mnt/home/software/software/Python/3.10.15-system/bin/python3.10

printf '\nSystem libcrypt entries:\n'
ls -l /lib64/libcrypt.so* /usr/lib64/libcrypt.so* 2>&1 || true

/mnt/home/software/software/Python/3.10.15-system/bin/python3.10 \
    -u -B alpha-runtime-probe.py

date -u
