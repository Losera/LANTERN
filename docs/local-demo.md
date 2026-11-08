# Reproduce the local Ollama pilot for judges

Run these commands from the repository root. You need Python 3.10 or newer,
GNU Make, Ollama 0.40.7, and the approved `qwen2.5:1.5b-instruct` model whose
digest starts with `65ec06548149`. No Python packages or frontend build are needed.
The demo checks the running daemon and installed model before generating.

## Fastest option: show the completed pilot

```bash
make demo-replay
```

Open <http://localhost:8000>. This shows the committed November 8 pilot;
it makes no model calls and needs no Ollama connection. Say that it is a
recorded run. Press Ctrl+C when finished.

## Fresh run for each judge

If Ollama is already running, leave it running. Otherwise start it in a
separate terminal and leave that terminal open:

```bash
ollama serve
```

On a new machine with Ollama 0.40.7 installed, fetch the approved model if
needed. The demo refuses a model whose digest no longer matches:

```bash
ollama pull qwen2.5:1.5b-instruct
```

Start the guided workflow:

```bash
make demo
```

The terminal pauses after each numbered stage. Press Enter when you are ready
to explain the next step; Ctrl+C stops the walkthrough.

1. **Evidence input:** read the actual fictional question, route options,
   evidence claims, sources, relevance labels, and decision requirements.
2. **Validation:** validate the case and check the installed model and running
   Ollama version. Show the fixed temperature, seed, and output limit.
3. **Conditions:** expand the case into five arms and four repetitions per arm.
   Explain each arm and show all 20 scheduled condition IDs.
4. **Prompts:** display the exact baseline prompt and each other arm's changes
   as a diff, including the unchanged rerun. All 20 prompt files and their
   hashes are saved before execution.
5. **Execution:** run the existing CLI once over the 20 conditions. The terminal
   prints the equivalent command so you can reproduce it directly. This command
   generates, parses, records, analyzes, and exports; it does not grade.
6. **Records:** show every arm's recorded outcomes and choices, then inspect
   the first baseline and framing responses as verbatim raw text. Failures stay
   in the dataset and in the counts.
7. **Analysis:** recompute the summary from the records and check it matches the
   export. Show the framing comparison, correction separately, and the total
   attempt denominator. Unchanged-rerun and neutral-edit controls are visible
   for interpretation; their choices do not automatically gate the verdict.
8. **Frontend:** identify the export and its label, then start the preview.
   Open <http://localhost:8000> when the URL appears.

Each invocation creates a fresh dataset under `.demo/runs/`. The terminal prints
its absolute directory. Keep the case copy, preflight, `conditions.json`,
`prompts/`, `attempts.jsonl`, `run.stdout.json`, `summary.json`, and the exports
to inspect how evidence became the displayed result. The preview contains that
run's data, separate from the repository's default frontend data.

Press Ctrl+C to stop the preview before the next judge. Run `make demo` again
for another independent pilot. These outputs are ignored by Git; copy them to
durable storage if you want to publish another run's evidence.

The retained pilot took about 25 seconds, but new runtime and choices can
differ. It returned 20 readable decisions, all choosing Route West, with
`effect: none_measured`. Report whatever the new run returns, including no
effect or insufficient readable pairs. This is a fictional-case pilot;
correctness remains unknown. It uses local Ollama, not Alpha.

## Other commands

Show the same eight stages without waiting for Enter:

```bash
make demo-auto
```

Piped/noninteractive invocations also skip pauses. For an unattended run that
generates evidence without the walkthrough or a web server:

```bash
make demo-run
```

Show a previous run, using the exact directory printed by the run command:

```bash
make demo-view RUN=/absolute/path/to/your/run
```

If port 8000 is busy, choose another port:

```bash
make demo-replay PORT=8001
```

Then open <http://localhost:8001>. Without Make, the equivalent entry points are
`python3 tools/local_demo.py demo` and `python3 tools/local_demo.py replay`.

## Interruption or failure

If generation is interrupted, completed attempts remain in the printed run
directory. Do not delete or replace failures. To resume, use that directory
and its name as the run ID. Confirm the Ollama version and model are unchanged:

```bash
RUN=/absolute/path/to/your/run
python3 -m runner.cli run \
  --case "$RUN/case.json" \
  --reruns 4 \
  --run-id "$(basename "$RUN")" \
  --attempts "$RUN/attempts.jsonl" \
  --export "$RUN/export.json" \
  --label 'LOCAL FICTIONAL-CASE PILOT — correctness unknown'
make demo-view RUN="$RUN"
```

If the dataset is damaged or the runtime changed, preserve it and show the
committed pilot with `make demo-replay`. No command repairs model output or
retries completed failures. The repository's synthetic frontend data and
original pilot evidence remain unchanged.
