# Alpha batch automation

The local Bash helper uploads a reviewed job and selected inputs, submits it to
Slurm, queries its status, and retrieves a run snapshot. It uses existing SSH
authentication and MFA; it does not store credentials, install packages, select
a model, or execute inference on the login host. Read the
[Alpha constraints](alpha.md) before a live run.

## First submission

Run from this repository/worktree. Set your account and complete first-login
MFA setup through SSH if needed:

```bash
export ALPHA_HOST="YOUR_USERNAME@alpha1.empireai.edu"
ssh "$ALPHA_HOST"
```

Exit the remote shell and submit from your laptop:

```bash
bash tools/alpha_submit.sh submit examples/alpha-smoke.sbatch
```

The smoke job requests one 10 GB MIG slice, one CPU, 32 GB host RAM, and ten
minutes using the organizer's event settings reproduced in the Alpha reference.
It prints the hostname, job ID, and GPU list. This is an allocation check, not
model inference. Confirm that the event reservation and resource settings still
apply before submitting. No live run has been performed by the helper's tests.

The helper prints a run ID, a remote directory, and Slurm's job receipt. Save
those values. Each submission gets its own `lantern/runs/RUN_ID` directory;
an existing directory is never reused. The uploaded job is named `job.sbatch`.
Slurm's receipt is also saved there as `submission.txt` before it is printed
locally, so it can survive an SSH disconnect after acceptance.

For a future reviewed inference job, pass each required file or directory after
the job script. For example, the command shape is
`bash tools/alpha_submit.sh submit reviewed.sbatch runner fixtures`.
Each selected input keeps its basename inside the run directory; directory
contents stay together. Only explicitly selected inputs are uploaded. Review
them first: recursive SCP follows symbolic links. Input basenames must use
letters, digits, dots, underscores, or hyphens, and must be unique. `job.sbatch`
and `submission.txt` are reserved. Local parent directories and the job-script
filename may contain spaces.

The current runner has no model-execution command. This helper does not fill
its model, prompt, parsing, or tool-execution seams. Your later job script must
load the approved environment and invoke the reviewed inference program.

## Status and retrieval

Replace the sample job ID below with your returned ID. If the receipt includes
a cluster suffix such as `12345;alpha`, pass the entire value in quotes:

```bash
bash tools/alpha_submit.sh status '12345'
```

This queries both `squeue` and `sacct`, even when the queue query fails. Read
the accounting `State` and `ExitCode`; a successful query does not mean the job
succeeded. Empty records leave completion unknown. Accounting availability and
timing depend on the site. There is no background polling or automatic retry.

After inspecting completion, replace `RUN_ID` with your printed run ID and
choose a new local destination whose parent directory already exists:

```bash
bash tools/alpha_submit.sh fetch RUN_ID ./alpha-results
```

Fetch copies the run directory's contents, including the job, receipt, logs,
and any results written there. It can copy a running job's partial files, so
successful retrieval is not evidence of completion. Outputs written elsewhere
by the job are not included. Existing local destinations are refused. A failed
transfer returns an error and leaves any partial copy in place for inspection.

## Recovery and verification

If the submission connection fails, do not blindly rerun `submit`: Slurm may
already have accepted the job. Inspect `submission.txt` in the printed remote
directory and query your queue with `squeue --me` over SSH. An unexpected receipt
also stops the helper without retrying. No cancellation or cleanup is automated.

Local checks require Bash and Python 3.10 or newer:

```bash
bash -n tools/alpha_submit.sh
bash -n examples/alpha-smoke.sbatch
python3 tools/test_alpha_submit.py
```

The tests replace SSH, SCP, and Slurm commands with local fixtures. They cover
argument validation, transfer/submission ordering, receipt recovery, separate
run directories, cluster IDs, status failures, and preservation of local files.
They do not establish real transfer behavior, MFA, Alpha connectivity,
allocation, accounting availability, CUDA inference, or model competence.

Command references: [OpenSSH SCP](https://man.openbsd.org/scp.1),
[Slurm submission](https://slurm.schedmd.com/sbatch.html),
[Slurm queue](https://slurm.schedmd.com/squeue.html), and
[Slurm accounting](https://slurm.schedmd.com/sacct.html).

## Implementation handoff

Human owner: Teammate A - Losera. Agent/session: Codex, Alpha automation task.
Scope: the helper, its offline tests, smoke job, and this guide. Branch:
`feat/alpha-automate`; worktree: `/home/losera/LANTERN-alpha-automation`;
base: `62779fa8406294a1b041edeaf2de063ea78be713`.
The supplied worktree was clean before implementation. No existing file or
runner contract was changed. Verification results and the review diff are
returned to the lead; a real Alpha run remains separate acceptance. Stop for
semantic review before substantive commit or merge.

Preparation verification at that base with four new, uncommitted files:
the helper's 18 offline tests passed; both Bash syntax checks passed; the
application check and its 15 self-tests passed; the documentation checker and
its ten self-tests passed (16 documents, 100 links, 27 shell examples, three
JSON examples; 44 external URLs not fetched). The design-oracle lane remained
`NOT_RUN`. Tracked and new-file whitespace checks passed. Alpha access and the
live smoke job remain untested. The next action is lead semantic review of
the four-file change before commit or integration.
