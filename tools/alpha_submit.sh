#!/usr/bin/env bash
# Transfer reviewed files and submit a Slurm job; never retry submission.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage:
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh submit JOB_FILE [FILES_OR_DIRS...]
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh status 'JOB_ID[;CLUSTER]'
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh fetch RUN_ID NEW_LOCAL_DIRECTORY

submit uploads explicit paths and prints the run ID and Slurm job ID.
status shows queue/accounting output; command success is not job success.
fetch copies a snapshot of the run directory into a new local directory.
OpenSSH handles credentials/MFA through your existing configuration.
HELP
}

fail() { printf 'alpha_submit: %s\n' "$*" >&2; exit 1; }

command_name="${1:---help}"
case "$command_name" in
    -h|--help|help) usage; exit 0 ;;
    submit|status|fetch) shift ;;
    *) usage >&2; fail "Unknown command: $command_name" ;;
esac

alpha_host="${ALPHA_HOST:-}"
[[ "$alpha_host" =~ ^[[:alnum:]_][[:alnum:]_.@-]*$ ]] ||
    fail 'Set ALPHA_HOST to user@host or an SSH configuration alias.'

# Prefix relative local paths so scp does not interpret ':' as a remote host.
local_path() {
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf './%s\n' "$1" ;;
    esac
}

case "$command_name" in
    submit)
        (( $# >= 1 )) || fail 'submit needs a job script.'
        job_script="$1"
        shift
        [[ -f "$job_script" && -r "$job_script" ]] ||
            fail "Missing or unreadable job script: $job_script"
        job_script="$(local_path "$job_script")"

        # scp keeps the basename of each selected payload. Refuse collisions.
        payloads=()
        names=(job.sbatch submission.txt)
        for path in "$@"; do
            [[ -e "$path" && -r "$path" ]] || fail "Missing or unreadable input: $path"
            trimmed="${path%/}"
            name="${trimmed##*/}"
            [[ "$name" =~ ^[[:alnum:]_.-]+$ && "$name" != . && "$name" != .. ]] ||
                fail 'Input basenames must use letters, digits, dots, underscores, or hyphens.'
            for previous in "${names[@]}"; do
                [[ "$name" != "$previous" ]] || fail "Duplicate or reserved input basename: $name"
            done
            names+=("$name")
            payloads+=("$(local_path "$path")")
        done

        run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$-$RANDOM"
        remote_dir="lantern/runs/$run_id"
        printf 'Run ID: %s\nRemote directory: %s:%s\n' "$run_id" "$alpha_host" "$remote_dir"
        ssh -- "$alpha_host" "mkdir -p lantern/runs && mkdir '$remote_dir'"
        scp -- "$job_script" "$alpha_host:$remote_dir/job.sbatch"
        if (( $# > 0 )); then
            scp -r -- "${payloads[@]}" "$alpha_host:$remote_dir/"
        fi

        # Keep the receipt remotely even if SSH drops after Slurm accepts it.
        if ! submission=$(ssh -- "$alpha_host" \
            "cd '$remote_dir' && sbatch --parsable job.sbatch > submission.txt && cat submission.txt"); then
            fail "Submission status is unknown. Inspect $remote_dir/submission.txt and your queue before retrying."
        fi
        [[ "$submission" =~ ^[0-9]+(\;[[:alnum:]_-]+)?$ ]] ||
            fail "Unexpected submission receipt. Inspect $remote_dir/submission.txt and your queue before retrying."
        printf 'Job ID: %s\n' "$submission"
        ;;

    status)
        (( $# == 1 )) || fail 'status needs one job ID (optionally JOB_ID;CLUSTER).'
        [[ "$1" =~ ^([0-9]+)(\;([[:alnum:]_-]+))?$ ]] || fail 'Invalid job ID or cluster.'
        job_id="${BASH_REMATCH[1]}"
        cluster="${BASH_REMATCH[3]:-}"
        cluster_option=''
        [[ -z "$cluster" ]] || cluster_option="--clusters='$cluster'"
        # Always try accounting, even if the completed job has left the queue.
        if ! ssh -- "$alpha_host" "query_status=0
squeue --jobs='$job_id' $cluster_option || query_status=1
sacct --allocations --jobs='$job_id' --format=JobID,State,ExitCode $cluster_option || query_status=1
exit \$query_status"; then
            fail 'A status query failed; inspect the displayed results. Missing records do not establish completion.'
        fi
        printf 'Read State and ExitCode above; empty records do not establish completion.\n'
        ;;

    fetch)
        (( $# == 2 )) || fail 'fetch needs a run ID and a new local directory.'
        run_id="$1"
        [[ "$run_id" =~ ^[[:alnum:]][[:alnum:]_-]*$ ]] || fail 'Invalid run ID.'
        destination="$(local_path "$2")"
        [[ ! -e "$destination" && ! -L "$destination" ]] ||
            fail 'The local destination already exists; choose a new directory.'
        mkdir -- "$destination"
        if ! scp -r -- "$alpha_host:lantern/runs/$run_id/." "$destination/"; then
            fail "Fetch failed; partial files may remain in $destination."
        fi
        printf 'Copied run snapshot to %s; this does not establish job completion.\n' "$destination"
        ;;
esac
