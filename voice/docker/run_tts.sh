#!/bin/bash
# Check if the text input is provided as an argument or already in the file
if [ "$#" -gt 0 ]; then
  echo "$1" > /app/speak.txt
fi
python3 /app/speak.py
cp /app/output.wav /output/
