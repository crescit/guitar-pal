#!/bin/bash
# guitar-buddy: launch the live hand-tracking webcam loop in a GUI terminal.
# Double-click this (or: open run_webcam.command). Must run from a GUI session
# so macOS grants camera access and MediaPipe can use Metal.
cd "$(dirname "$0")"
exec .venv/bin/python scripts/run_webcam.py
