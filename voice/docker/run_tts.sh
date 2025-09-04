#!/usr/bin/env bash

# --- Debug Logging Setup ---
LOG_FILE="/output/container_run_tts.log"
exec > "$LOG_FILE" 2>&1

# -x: Print each command before executing it
# -e: Exit immediately if a command fails
set -xe
# --- End Debug Logging Setup ---

echo "--- container_run_tts.log started at $(date) ---"

TEXT="${*:-}"
echo "DEBUG: Input text received: '$TEXT'"

if [[ -z "$TEXT" ]]; then
  echo "ERROR: No text was provided to the script." >&2
  exit 2
fi

echo "DEBUG: Writing text to /app/speak.txt"
printf "%s" "$TEXT" > /app/speak.txt

export IN_CONTAINER=1
echo "DEBUG: IN_CONTAINER environment variable set"

PY="/app/venv/bin/python"
echo "DEBUG: Python executable path: $PY"

echo "DEBUG: Executing /app/speaker.py..."
"$PY" /app/speaker.py
echo "DEBUG: Python script finished."

echo "DEBUG: Checking for generated audio file at /app/output.wav"
test -f /app/output.wav
echo "DEBUG: File /app/output.wav found."

echo "DEBUG: Copying /app/output.wav to /output/ directory..."
cp -f /app/output.wav /output/
echo "DEBUG: File copy complete."

echo "--- container_run_tts.log finished successfully at $(date) ---"