PYTHON ?= python3
PORT ?= 8000

.PHONY: demo demo-auto demo-run demo-replay demo-view

# Guided input-to-result walkthrough; press Enter between stages.
demo:
	$(PYTHON) tools/local_demo.py demo --port "$(PORT)"

# Same walkthrough without pauses, then serve its frontend.
demo-auto:
	$(PYTHON) tools/local_demo.py demo --yes --port "$(PORT)"

# Fresh pilot and preview files, without starting the web server.
demo-run:
	$(PYTHON) tools/local_demo.py run

# Show the committed pilot without contacting Ollama.
demo-replay:
	$(PYTHON) tools/local_demo.py replay --port "$(PORT)"

# Show a previous run: make demo-view RUN=/absolute/path/to/run
demo-view:
	$(PYTHON) tools/local_demo.py view --run "$(RUN)" --port "$(PORT)"
