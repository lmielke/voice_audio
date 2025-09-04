# File: voice/speaker.py

import os
import sys
import argparse
import subprocess
import wave
import logging

try:
    import voice.settings as sts
except ModuleNotFoundError:
    import settings as sts

# --- Global Logger ---
logger = logging.getLogger(__name__)

def setup_logging(*args, log_filename: str, in_container: bool = False, **kwargs):
    """Configures the logger to write to the specified file."""
    log_dir = "/output" if in_container else sts.resources_dir
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, log_filename)

    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.FileHandler(log_file_path, mode='w')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.info(f"--- Logging started for {log_filename} ---")

try:
    import winsound as _winsound
    _has_winsound = True
except ImportError:
    _winsound = None
    _has_winsound = False

try:
    import simpleaudio as sa
    _has_simpleaudio = True
except ImportError:
    sa = None
    _has_simpleaudio = False


def play_audio(file_path: str) -> None:
    if _has_winsound:
        try:
            _winsound.PlaySound(file_path, _winsound.SND_FILENAME)
            return
        except Exception as e:
            logger.error(f"winsound failed: {e}")

    if _has_simpleaudio:
        try:
            wave_obj = sa.WaveObject.from_wave_file(file_path)
            play_obj = wave_obj.play()
            play_obj.wait_done()
            return
        except Exception as e:
            logger.error(f"simpleaudio failed: {e}")

    logger.warning("No valid audio playback method available.")

try:
    from piper.voice import PiperVoice
except ImportError:
    PiperVoice = None

MODEL_PATH = "/app/piper_models/en_US-lessac-medium.onnx"
CONFIG_PATH = MODEL_PATH + ".json"
INPUT_FILE = "/app/speak.txt"
OUTPUT_FILE = "/app/output.wav"

def container_text_to_speech(text: str) -> None:
    """Generate speech from text inside the container."""
    if PiperVoice is None:
        logger.error("PiperVoice is not available. Check piper-tts installation.")
        sys.exit(1)
    logger.info("PiperVoice found. Loading model...")
    voice = PiperVoice.load(MODEL_PATH, CONFIG_PATH)
    logger.info("Model loaded. Synthesizing speech...")
    with open(OUTPUT_FILE, "wb") as f:
        voice.synthesize(text, f)
    logger.info(f"Speech saved to {OUTPUT_FILE}")


class Speaker:
    def __init__(self, *args, docker_image: str = "piper_tts:latest",
                 container_name: str = "voice_runner",
                 mount_dir: str = None, **kwargs) -> None:
        self.docker_image = docker_image
        self.container_name = container_name
        self.mount_dir = mount_dir or os.path.join(sts.resources_dir, "output")
        self.output_dir = f"{self.mount_dir}:/output"
        os.makedirs(self.mount_dir, exist_ok=True)

    def ensure_container(self, *args, **kwargs) -> None:
        result_running = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name=^{self.container_name}$"],
            capture_output=True, text=True
        )
        if result_running.stdout.strip():
            logger.info(f"Container '{self.container_name}' is running.")
            return

        result_all = subprocess.run(
            ["docker", "ps", "-aq", "-f", f"name=^{self.container_name}$"],
            capture_output=True, text=True
        )
        if result_all.stdout.strip():
            logger.info(f"Container '{self.container_name}' exists but is not running. Starting it...")
            result_start = subprocess.run(
                ["docker", "start", self.container_name],
                capture_output=True, text=True
            )
            if result_start.returncode != 0:
                logger.error(f"Error starting container: {result_start.stderr}")
                sys.exit(1)
            logger.info(f"Container '{self.container_name}' started.")
            return

        logger.info(f"Container '{self.container_name}' not found. Creating and starting it...")
        run_cmd = [
            "docker", "run", "-d", "--name", self.container_name,
            "-v", self.output_dir, self.docker_image,
        ]
        res = subprocess.run(run_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"Error creating container: {res.stderr}")
            sys.exit(1)
        logger.info(f"Container '{self.container_name}' started.")

    def speak(self, text: str, *args, **kwargs) -> None:
        if os.environ.get("IN_CONTAINER"):
            container_text_to_speech(text)
        else:
            self.ensure_container()
            exec_cmd = ["docker", "exec", self.container_name, "/app/run_tts.sh", text]
            logger.info(f"Running command -> {' '.join(exec_cmd)}")
            try:
                result = subprocess.run(
                    exec_cmd, capture_output=True, text=True, timeout=30
                )
            except Exception as e:
                logger.error(f"Subprocess execution failed: {e}")
                sys.exit(1)

            logger.debug(f"Return Code: {result.returncode}")
            logger.debug(f"Stdout: '{result.stdout.strip()}'")
            logger.debug(f"Stderr: '{result.stderr.strip()}'")
            if result.returncode != 0:
                logger.error("Docker exec command failed.")
                sys.exit(1)

            output_file = os.path.join(self.mount_dir, "output.wav")
            if not os.path.exists(output_file):
                logger.error(f"output.wav was not generated in '{self.mount_dir}'")
                sys.exit(1)
            
            logger.info("Playing output.wav...")
            play_audio(output_file)

def container_exec(*args, **kwargs) -> None:
    setup_logging(log_filename="container_speaker.log", in_container=True)
    logger.info("Executing speaker.py inside container.")
    txt = ""
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            txt = f.read().strip()
    if txt:
        container_text_to_speech(txt)
    else:
        logger.error(f"{INPUT_FILE} missing or empty inside container.")
        sys.exit(1)

def local_exec(*args, text: str = None, file: str = None, **kwargs):
    setup_logging(log_filename="local_speaker.log")
    logger.info("Executing speaker.py on host.")
    if text is not None:
        input_text = text
    elif file and os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            input_text = f.read().strip()
    else:
        logger.error(f"Neither valid text '{text}' nor file '{file}' was provided.")
        sys.exit(1)
    
    speaker = Speaker(*args, **kwargs)
    speaker.speak(input_text, *args, **kwargs)

def main(*args, **kwargs) -> None:
    if os.environ.get("IN_CONTAINER"):
        container_exec(*args, **kwargs)
    else:
        local_exec(*args, **kwargs)

def get_kwargs(*args, **kwargs) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-t", "--text", help="Direct input text for TTS.")
    group.add_argument("-f", "--file", help="Path to text file for TTS.")
    args = parser.parse_args()
    if not args.text and not args.file:
        if os.environ.get("IN_CONTAINER"):
            args.file = INPUT_FILE
        else:
            args.file = os.path.join(sts.resources_dir, "speak.txt")
    return args

if __name__ == "__main__":
    args = get_kwargs()
    main(text=args.text, file=args.file)