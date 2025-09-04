# File: voice/docker/run_tts.sh

#!/usr/bin/env bash

# --- Debug Logging Setup ---
# All output from this script will be written to container_debug.log
# in the shared /output directory.
LOG_FILE="/output/container_debug.log"
exec > "$LOG_FILE" 2>&1

# -x: Print each command before executing it (creates a trace)
# -e: Exit immediately if a command fails
set -xe
# --- End Debug Logging Setup ---

echo "--- Container log started at $(date) ---"

# Accept the full text passed as arguments
TEXT="${*:-}"
echo "DEBUG: Input text received: '$TEXT'"

if [[ -z "$TEXT" ]]; then
  echo "ERROR: No text was provided to the script."
  exit 2
fi

# Write the text to a file for the Python script to read
echo "DEBUG: Writing text to /app/speak.txt"
printf "%s" "$TEXT" > /app/speak.txt

# Set environment variable for the Python script
export IN_CONTAINER=1
echo "DEBUG: IN_CONTAINER environment variable is set"

# Define the Python executable path
PY="/app/venv/bin/python"
echo "DEBUG: Python executable path set to $PY"

echo "DEBUG: Executing /app/speaker.py..."
"$PY" /app/speaker.py
echo "DEBUG: Python script finished."

echo "DEBUG: Checking for generated audio file at /app/output.wav"
test -f /app/output.wav
echo "DEBUG: File /app/output.wav found."

echo "DEBUG: Copying /app/output.wav to the shared /output/ directory..."
cp -f /app/output.wav /output/
echo "DEBUG: File copy complete."

echo "--- Container log finished successfully at $(date) ---"