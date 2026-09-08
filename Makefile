# guitar-buddy — project make targets
#
# `make` (or `make up`) is the one-shot spin-up: it creates the venv,
# installs deps, starts the web server in the background, and opens the
# browser. Everything else is optional tooling.

.DEFAULT_GOAL := up

VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PORT       := 8000
SERVER_LOG := server.log
SERVER_PID := .server.pid

.PHONY: up venv install web run demo bench test coverage stop clean help

# --- one-shot spin-up ---------------------------------------------------------

up: venv
	@if [ -f $(SERVER_PID) ] && kill -0 $$(cat $(SERVER_PID)) 2>/dev/null; then \
		echo "Web server already running (pid $$(cat $(SERVER_PID)))"; \
	else \
		nohup python3 -m http.server $(PORT) --directory web > $(SERVER_LOG) 2>&1 & \
		echo $$! > $(SERVER_PID); \
		echo "Web server started on http://localhost:$(PORT) (pid $$!)"; \
	fi
	@open http://localhost:$(PORT)
	@echo "App opened in your browser. Log: $(SERVER_LOG)"
	@echo "Stop it later with: make stop"

venv:
	@test -d $(VENV) || { echo "Creating venv..."; python3 -m venv $(VENV); }
	@test -f $(VENV)/.installed || { \
		echo "Installing dependencies..."; \
		$(PIP) install --upgrade pip >/dev/null 2>&1; \
		$(PIP) install -r requirements.txt; \
		touch $(VENV)/.installed; \
	}
	@echo "Environment ready."

install: venv
	$(PIP) install -r requirements.txt

# --- browser app --------------------------------------------------------------

web:
	python3 -m http.server $(PORT) --directory web

stop:
	@if [ -f $(SERVER_PID) ]; then \
		kill $$(cat $(SERVER_PID)) 2>/dev/null && echo "Web server stopped." || echo "No running server (pid file stale)."; \
		rm -f $(SERVER_PID); \
	else \
		echo "No server running."; \
	fi

# --- python tools -------------------------------------------------------------

run:
	$(PYTHON) scripts/run_webcam.py

demo:
	$(PYTHON) scripts/pipeline_demo.py $(IMG)

bench:
	$(PYTHON) scripts/bench_video.py $(VID) --device cpu

# --- tests --------------------------------------------------------------------

test:
	$(PYTHON) -m pytest

coverage:
	open coverage_html/index.html

# --- housekeeping -------------------------------------------------------------

clean:
	rm -rf .pytest_cache coverage_html .coverage $(SERVER_LOG) $(SERVER_PID)
	rm -rf $(VENV)

help:
	@echo "guitar-buddy targets:"
	@echo "  make (up)    one-shot: venv + deps + serve web + open browser"
	@echo "  make stop    stop the background web server"
	@echo "  make web     run the web server in the foreground (port $(PORT))"
	@echo "  make run     launch the live webcam hand-tracking loop"
	@echo "  make demo    detector on an image (set IMG=path)"
	@echo "  make bench   benchmark a video (set VID=path)"
	@echo "  make test    full pytest suite with coverage gate"
	@echo "  make clean   remove venv and all artifacts"
