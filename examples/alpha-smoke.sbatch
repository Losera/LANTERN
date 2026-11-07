#!/bin/bash
#SBATCH -p alpha
#SBATCH --reservation=binghamton_hackathon
#SBATCH --gres=gpu:1g.10gb:1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 00:10:00
#SBATCH -J lantern-smoke
#SBATCH -o %x-%j.out

# Allocation check only: no model, package installation, or training.
set -euo pipefail
hostname
printf 'Slurm job: %s\n' "$SLURM_JOB_ID"
nvidia-smi -L
