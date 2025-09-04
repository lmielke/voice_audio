#!/usr/bin/env bash
set -euo pipefail

# Accept full text (all args); fall back to existing file if no args.
TEXT="${*:-}"
if [[ -z "$TEXT" ]] && [[ -f /app/speak.txt ]]; then
  TEXT="$(cat /app/speak.txt)"
fi
if [[ -z "$TEXT" ]]; then
  echo "No text provided to run_tts.sh" >&2
  exit 2
fi

# Write the exact text (no trailing newline)
printf "%s" "$TEXT" > /app/speak.txt
# Tell speaker.py to use container mode (reads /app/speak.txt)
export IN_CONTAINER=1

# Prefer venv Python, fallback to system python3
PY="/app/venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

"$PY" /app/speaker.py

# Copy out the result produced by speaker.py
test -f /app/output.wav
cp -f /app/output.wav /output/
