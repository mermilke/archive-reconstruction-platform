# Archive Reconstruction Platform — common dev tasks (stdlib only; no build deps).
# Windows users: see tasks.ps1 for PowerShell equivalents.

PYTHON ?= python
export PYTHONPATH := src

.PHONY: help test install demo web dedup clean

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

test:           ## Run the whole test suite
	$(PYTHON) tests/run_all.py

install:        ## Editable install so the `arc` command is on PATH
	$(PYTHON) -m pip install -e .

demo:           ## Render the example timeline to timeline.html
	$(PYTHON) -m arc.cli timeline examples/events.json -o timeline.html
	@echo "Open timeline.html in a browser."

web:            ## Launch the local drag-drop web UI
	$(PYTHON) -m arc.cli web

dedup:          ## Run the example dedup (recommendation only)
	$(PYTHON) -m arc.cli dedup examples/threads

clean:          ## Remove generated artifacts
	rm -f timeline.html arc.db
	rm -rf src/arc/__pycache__ tests/__pycache__
