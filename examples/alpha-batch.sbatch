#!/bin/bash
# Human submission after exact preflight review; no installs or downloads.
#SBATCH -p alpha
#SBATCH --account=rpicourse
#SBATCH --reservation=binghamton_hackathon
#SBATCH --gres=gpu:1g.10gb:1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 00:30:00
#SBATCH --signal=B:TERM@30
#SBATCH -J lantern-batch
#SBATCH -o %x-%j.out
set -euo pipefail
umask 077
date -u
hostname
printf 'Slurm job: %s\n' "${SLURM_JOB_ID:?Requires an allocation}"
nvidia-smi -L
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
environment_dir=/mnt/home/student019/lantern/envs/qwen3-inference-175794
model_dir=/mnt/home/student019/lantern/models/qwen3-4b-175794
[[ -x "$environment_dir/bin/python" && -d "$model_dir" ]] || { printf 'Existing environment/model missing\n' >&2; exit 1; }
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export OMP_NUM_THREADS=1
# exec lets Slurm's advance TERM reach the Python supervisor, which accounts
# for undispatched work and kills/reaps an active worker before finalizing.
exec "$environment_dir/bin/python" -I -u -B alpha-batch-executor.py --model-dir "$model_dir"
