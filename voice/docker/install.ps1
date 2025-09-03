# install.ps1

# This script installs the Piper TTS system in a Docker container.

Write-Host "Building Docker image: piper_base..."
docker build -t piper_base -f Dockerfile.base .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error: Failed to build piper_base."
    exit $LASTEXITCODE
}

Write-Host "Building Docker image: piper_tts..."
docker build -t piper_tts -f Dockerfile.tts .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Error: Failed to build piper_tts."
    exit $LASTEXITCODE
}

Write-Host "Running test TTS command..."
# This command uses the installed package to generate speech saying "install completed successfully"
python speak.py -t "install completed successfully"

Write-Host "Installation completed successfully!"

# this part downloads the most recent vosk model to its destination
# first we create vosk_model directory if it does not yet exist
if (-not (Test-Path -Path "vosk_model")) {
    New-Item -ItemType Directory -Path "vosk_model"
}
# # then we download the model
# $uri = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.42-gigaspeech.zip"
# $destination = "vosk_model/vosk-model-en-us-0.42-gigaspeech.zip"
# Invoke-WebRequest -Uri $uri -OutFile $destination