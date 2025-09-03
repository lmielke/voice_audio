# Piper TTS Utility
A lightweight text-to-speech utility using Docker and Piper.
It builds two Docker images to isolate TTS synthesis.
It uses a persistent container to generate and play speech from text.

# Installation
1. Build Docker Images:

```bash
docker build -t piper_base -f Dockerfile.base .
docker build -t piper_tts -f Dockerfile.tts .
```
Alternatively, on Windows, run the provided PowerShell script:

```powershell
.\install.ps1
```
2. Test Installation:
The install script runs a test TTS command that speaks "install completed successfully".


# Usage
Generate Speech:
Run the following command to synthesize speech from text:

```bash
# This uses text you provided as an argument -t 
python speak.py -t "Your text here"
```
Use a Text File:
Provide a file with your text:

```bash
# This uses text from a file you provided as an argument -f
python speak.py -f path/to/yourfile.txt
```

Enjoy your TTS utility!