#!/bin/bash
# Prepare/review this exact payload before human submission and downloads.
#SBATCH -p alpha
#SBATCH --account=rpicourse
#SBATCH --reservation=binghamton_hackathon
#SBATCH --gres=gpu:1g.10gb:1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 00:30:00
#SBATCH -J lantern-inference
#SBATCH -o %x-%j.out
set -euo pipefail
umask 077

stage=preflight
environment_dir="$HOME/lantern/envs/qwen3-inference-${SLURM_JOB_ID:?Requires a Slurm allocation}"
model_dir="$HOME/lantern/models/qwen3-4b-$SLURM_JOB_ID"

finish() {
    job_exit=$?
    trap - EXIT
    /usr/bin/python3 -I -B - "$job_exit" "$stage" "$environment_dir" "$model_dir" <<'PY'
import datetime
import json
import pathlib
import sys

pathlib.Path("job-status.json").write_text(json.dumps({
    "exit_code": int(sys.argv[1]), "stage": sys.argv[2],
    "environment_path": sys.argv[3], "model_path": sys.argv[4],
    "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}, indent=2) + "\n")
PY
    exit "$job_exit"
}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

date -u
hostname
printf 'Slurm job: %s\n' "$SLURM_JOB_ID"
nvidia-smi -L
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
for input in alpha-inference-probe.py alpha-inference-baseline.txt alpha-inference-requirements.txt; do
    [[ -r "$input" ]] || { printf 'Missing input: %s\n' "$input" >&2; exit 1; }
done
sha256sum job.sbatch alpha-inference-probe.py alpha-inference-baseline.txt alpha-inference-requirements.txt > input-sha256.txt
/usr/bin/python3 -I -B -c 'import sys; print(sys.version); sys.exit(0 if sys.version_info[:2] == (3, 12) else "Expected native Python 3.12")'
pip_command=(/usr/bin/python3 -I -B -m pip --isolated --disable-pip-version-check)
"${pip_command[@]}" --python /usr/bin/python3 --version
for new_path in "$environment_dir" "$model_dir"; do
    [[ ! -e "$new_path" && ! -L "$new_path" ]] || { printf 'Refusing existing path: %s\n' "$new_path" >&2; exit 1; }
done
printf '%s\n' "$environment_dir" > environment-path.txt
printf '%s\n' "$model_dir" > model-path.txt

stage=create-environment
mkdir -p -- "${environment_dir%/*}" "${model_dir%/*}"
/usr/bin/python3 -I -B -m venv --without-pip "$environment_dir"
stage=install-baseline
"${pip_command[@]}" --python "$environment_dir/bin/python" install \
    --no-input --no-cache-dir --only-binary=:all: \
    --index-url https://download.pytorch.org/whl/cu126 \
    --report pip-baseline-report.json -r alpha-inference-baseline.txt
stage=install-inference
"${pip_command[@]}" --python "$environment_dir/bin/python" install \
    --no-input --no-cache-dir --only-binary=:all: \
    --index-url https://pypi.org/simple \
    --report pip-inference-report.json \
    -c alpha-inference-baseline.txt -r alpha-inference-requirements.txt
"${pip_command[@]}" --python "$environment_dir/bin/python" freeze > installed-packages.txt
"${pip_command[@]}" --python "$environment_dir/bin/python" check

stage=download-and-inference
export HF_HOME="$model_dir/.hf-home"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export OMP_NUM_THREADS=1
"$environment_dir/bin/python" -I -u -B alpha-inference-probe.py --model-dir "$model_dir"
stage=complete
date -u
