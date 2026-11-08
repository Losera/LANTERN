#!/usr/bin/env bash
# Transfer reviewed files and submit a Slurm job; never retry submission.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage:
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh submit JOB_FILE [FILES_OR_DIRS...]
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh submit --run-id RUN_ID JOB_FILE [FILES_OR_DIRS...]
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh status 'JOB_ID[;CLUSTER]'
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh observe 'JOB_ID[;CLUSTER]'
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh receipt RUN_ID
  ALPHA_HOST=user@alpha1.empireai.edu bash tools/alpha_submit.sh fetch RUN_ID NEW_LOCAL_DIRECTORY

submit uploads explicit paths and prints the run ID and Slurm job ID.
status shows queue/accounting output; command success is not job success.
fetch copies a snapshot of the run directory into a new local directory.
OpenSSH handles credentials/MFA through your existing configuration.
Optional ALPHA_CONTROL_PATH reuses a manually authenticated SSH connection.
When set, password/MFA prompts are disabled; establish the connection first.
HELP
}

fail() { printf 'alpha_submit: %s\n' "$*" >&2; exit 1; }

command_name="${1:---help}"
case "$command_name" in
    -h|--help|help) usage; exit 0 ;;
    submit|status|observe|receipt|fetch) shift ;;
    *) usage >&2; fail "Unknown command: $command_name" ;;
esac

alpha_host="${ALPHA_HOST:-}"
[[ "$alpha_host" =~ ^[[:alnum:]_][[:alnum:]_.@-]*$ ]] ||
    fail 'Set ALPHA_HOST to user@host or an SSH configuration alias.'

# Use the same socket for SSH commands and SCP transfers. Never force a PTY
# onto transfers or receipt output, and leave default authentication unchanged.
connection_options=()
if [[ -n "${ALPHA_CONTROL_PATH:-}" ]]; then
    [[ "$ALPHA_CONTROL_PATH" != *\"* && "$ALPHA_CONTROL_PATH" != *\\* &&
       ! "$ALPHA_CONTROL_PATH" =~ [[:cntrl:]] ]] ||
        fail 'ALPHA_CONTROL_PATH must not contain double quotes, backslashes, or control characters.'
    # OpenSSH parses -o values as config text, so quote spaces for that parser too.
    connection_options=(-o "ControlPath=\"$ALPHA_CONTROL_PATH\"" -o ControlMaster=no -o BatchMode=yes)
fi

# Prefix relative local paths so scp does not interpret ':' as a remote host.
local_path() {
    case "$1" in
        /*) printf '%s\n' "$1" ;;
        *) printf './%s\n' "$1" ;;
    esac
}

case "$command_name" in
    submit)
        run_id=''
        if [[ "${1:-}" == --run-id ]]; then
            (( $# >= 3 )) || fail '--run-id needs an ID and job script.'
            run_id="$2"
            [[ "$run_id" =~ ^[[:alnum:]][[:alnum:]_-]*$ ]] || fail 'Invalid run ID.'
            shift 2
        fi
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

        [[ -n "$run_id" ]] || run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$-$RANDOM"
        remote_dir="lantern/runs/$run_id"
        printf 'Run ID: %s\nRemote directory: %s:%s\n' "$run_id" "$alpha_host" "$remote_dir"
        ssh "${connection_options[@]}" -- "$alpha_host" "mkdir -p lantern/runs && mkdir '$remote_dir'"
        scp "${connection_options[@]}" -- "$job_script" "$alpha_host:$remote_dir/job.sbatch"
        if (( $# > 0 )); then
            scp "${connection_options[@]}" -r -- "${payloads[@]}" "$alpha_host:$remote_dir/"
        fi

        # Keep the receipt remotely even if SSH drops after Slurm accepts it.
        if ! submission=$(ssh "${connection_options[@]}" -- "$alpha_host" \
            "cd '$remote_dir' && sbatch --parsable job.sbatch > submission.txt && cat submission.txt"); then
            fail "Submission status is unknown. Inspect $remote_dir/submission.txt and your queue before retrying."
        fi
        [[ "$submission" =~ ^[0-9]+(\;[[:alnum:]_-]+)?$ ]] ||
            fail "Unexpected submission receipt. Inspect $remote_dir/submission.txt and your queue before retrying."
        printf 'Job ID: %s\n' "$submission"
        ;;

    status|observe)
        (( $# == 1 )) || fail 'status needs one job ID (optionally JOB_ID;CLUSTER).'
        [[ "$1" =~ ^([0-9]+)(\;([[:alnum:]_-]+))?$ ]] || fail 'Invalid job ID or cluster.'
        job_id="${BASH_REMATCH[1]}"
        cluster="${BASH_REMATCH[3]:-}"
        cluster_option=''
        [[ -z "$cluster" ]] || cluster_option="--clusters='$cluster'"
        if [[ "$command_name" == observe ]]; then
            # Two named sections; neither query failure nor absent accounting
            # can be read as terminal completion by the coordinator.
            ssh "${connection_options[@]}" -- "$alpha_host" "query_status=0
printf 'QUEUE\\n'
squeue --me --noheader --format='%i|%T' $cluster_option || query_status=1
printf 'ACCOUNTING\\n'
sacct --allocations --noheader --parsable2 --jobs='$job_id' --format=JobIDRaw,State,ExitCode $cluster_option || query_status=1
exit \$query_status"
            exit $?
        fi
        # Always try accounting, even if the completed job has left the queue.
        if ! ssh "${connection_options[@]}" -- "$alpha_host" "query_status=0
squeue --jobs='$job_id' $cluster_option || query_status=1
sacct --allocations --jobs='$job_id' --format=JobID,State,ExitCode $cluster_option || query_status=1
exit \$query_status"; then
            fail 'A status query failed; inspect the displayed results. Missing records do not establish completion.'
        fi
        printf 'Read State and ExitCode above; empty records do not establish completion.\n'
        ;;

    receipt)
        (( $# == 1 )) || fail 'receipt needs one run ID.'
        [[ "$1" =~ ^[[:alnum:]][[:alnum:]_-]*$ ]] || fail 'Invalid run ID.'
        ssh "${connection_options[@]}" -- "$alpha_host" "cat 'lantern/runs/$1/submission.txt'"
        ;;

    fetch)
        (( $# == 2 )) || fail 'fetch needs a run ID and a new local directory.'
        run_id="$1"
        [[ "$run_id" =~ ^[[:alnum:]][[:alnum:]_-]*$ ]] || fail 'Invalid run ID.'
        destination="$(local_path "$2")"
        [[ ! -e "$destination" && ! -L "$destination" ]] ||
            fail 'The local destination already exists; choose a new directory.'
        mkdir -- "$destination"
        if ! scp "${connection_options[@]}" -r -- "$alpha_host:lantern/runs/$run_id/." "$destination/"; then
            fail "Fetch failed; partial files may remain in $destination."
        fi
        printf 'Copied run snapshot to %s; this does not establish job completion.\n' "$destination"
        ;;
esac
