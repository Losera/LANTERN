#!/bin/bash
#SBATCH -p alpha
#SBATCH --account=rpicourse
#SBATCH --reservation=binghamton_hackathon
#SBATCH --gres=gpu:1g.10gb:1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 00:30:00
#SBATCH -J lantern-runtime-setup
#SBATCH -o %x-%j.out

# Requires approval for PyTorch/dependency downloads before human submission.
# Creates a new compute-node Python environment, then runs the tensor probe.
# No model weights, CUDA module load, system install, or automatic cleanup.
set -euo pipefail
umask 077

date -u
hostname
printf 'Slurm job: %s\n' "$SLURM_JOB_ID"
nvidia-smi -L
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
[[ -r alpha-runtime-probe.py ]] || { printf 'Missing alpha-runtime-probe.py\n' >&2; exit 1; }

/usr/bin/python3 -I -B -c \
    'import sys; print(sys.version, flush=True); sys.exit(0 if sys.version_info[:2] == (3, 12) else "Expected native Python 3.12")'

# Verify system pip supports --python before creating anything.
pip_command=(/usr/bin/python3 -I -B -m pip --isolated --disable-pip-version-check)
"${pip_command[@]}" --python /usr/bin/python3 --version

environment_dir="$HOME/lantern/envs/runtime-py312-torch291-cu126-$SLURM_JOB_ID"
if [[ -e "$environment_dir" || -L "$environment_dir" ]]; then
    printf 'Refusing to reuse existing environment: %s\n' "$environment_dir" >&2
    exit 1
fi
printf '%s\n' "$environment_dir" > environment-path.txt
printf 'New environment: %s\n' "$environment_dir"
mkdir -p -- "${environment_dir%/*}"
/usr/bin/python3 -I -B -m venv --without-pip "$environment_dir"

# System pip manages only the explicitly targeted virtual environment.
# Dependencies are resolved at install time; the report records exact artifacts.
"${pip_command[@]}" --python "$environment_dir/bin/python" install \
    --no-input --no-cache-dir --only-binary=:all: \
    --index-url https://download.pytorch.org/whl/cu126 \
    --report pip-install-report.json 'torch==2.9.1+cu126'

"${pip_command[@]}" --python "$environment_dir/bin/python" freeze > installed-packages.txt
cat installed-packages.txt
"${pip_command[@]}" --python "$environment_dir/bin/python" check

"$environment_dir/bin/python" -I -u -B alpha-runtime-probe.py
date -u
