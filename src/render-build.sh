#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements-speech.txt -r requirements-judge.txt
# No desktop/OpenGL libraries are required on Render.
python -m pip uninstall -y opencv-python opencv-python-headless
python -m pip install opencv-python-headless==4.11.0.86
python -m football.cli download-speech-model
python -m football.cli download-model
