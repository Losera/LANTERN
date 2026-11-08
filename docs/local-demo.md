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

Run the full pilot and open its frontend:

```bash
make demo
```

Open <http://localhost:8000> after the command prints the URL. Each invocation
creates a fresh dataset under `.demo/runs/`, runs five arms with four repetitions
each, then serves a separate frontend preview containing that run's export.
The terminal prints the absolute run directory. Keep it for raw responses,
the case copy, runtime preflight, and JSON/JavaScript exports.

Press Ctrl+C to stop the preview before the next judge. Run `make demo` again
for another independent pilot. These outputs are ignored by Git; copy them to
durable storage if you want to publish another run's evidence.

The retained pilot took about 25 seconds, but new runtime and choices can
differ. It returned 20 readable decisions, all choosing Route West, with
`effect: none_measured`. Report whatever the new run returns, including no
effect or insufficient readable pairs. This is a fictional-case pilot;
correctness remains unknown. It uses local Ollama, not Alpha.

## Other commands

Generate evidence without starting a server:

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
