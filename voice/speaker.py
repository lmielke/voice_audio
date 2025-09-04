# speaker.py
import os
import sys
import argparse
import subprocess
import wave

try:
    import voice.settings as sts
except ModuleNotFoundError:
    import settings as sts
"""
# Audio playback: try winsound first, then falls back to playsound.
this module requires docker container setup

# This builds the base container 
- docker build -t piper_base -f Dockerfile.base .

# This builds the TTS container, which is used to generate speach.
- docker build -t piper_tts -f Dockerfile.tts .

run like: python speaker.py -t "Direct input text for TTS"
"""
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
            print("winsound failed:", e)

    if _has_simpleaudio:
        try:
            wave_obj = sa.WaveObject.from_wave_file(file_path)
            play_obj = wave_obj.play()
            play_obj.wait_done()
            return
        except Exception as e:
            print("simpleaudio failed:", e)

    print("No valid audio playback method available.")


# Try to import PiperVoice for container mode.
try:
    from piper.voice import PiperVoice
except ImportError:
    PiperVoice = None

# Constants for container mode.
MODEL_PATH = "/app/piper_models/en_US-lessac-medium.onnx"
CONFIG_PATH = MODEL_PATH + ".json"
INPUT_FILE = "/app/speak.txt"
OUTPUT_FILE = "/app/output.wav"

def local_text_to_speech(text: str) -> None:
    """
    Generate speech from text and save it to OUTPUT_FILE using the PiperVoice API.
    This function is used when running inside the container.
    """
    if PiperVoice is None:
        print("Error: PiperVoice is not available. Are you running in the container?")
        sys.exit(1)
    voice = PiperVoice.load(MODEL_PATH, CONFIG_PATH)
    with wave.open(OUTPUT_FILE, "wb") as wav_file:
        voice.synthesize(text, wav_file)
    print(f"✅ Speech saved to {OUTPUT_FILE}")


class Speaker:
    def __init__(self, *args, docker_image: str = "piper_tts:latest",
                 container_name: str = "voice_runner",
                 mount_dir: str = None, **kwargs) -> None:
        """
        Initialize the Speaker with the Docker image, persistent container name,
        and mount directory.

        Args:
            docker_image (str): Name of the Docker image to use.
            container_name (str): Name of the persistent container.
            mount_dir (str): Host directory to mount for output.
                             Defaults to $PWD/output.
        """
        self.docker_image = docker_image
        self.container_name = container_name
        # work_dir = os.path.dirname(os.path.abspath(__file__))
        self.mount_dir = mount_dir or os.path.join(sts.resources_dir, "output")
        self.output_dir = f"{self.mount_dir}:/output"
        # self.mount_dir = mount_dir or os.path.join(os.getcwd(), "output")
        os.makedirs(self.mount_dir, exist_ok=True)

    def ensure_container(self, *args, **kwargs) -> None:
        """
        Check if the persistent container is running.
        - If running, do nothing.
        - If exists but not running, start it.
        - If it doesn't exist, create and start it.
        """
        # Check if container is running.
        result_running = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name=^{self.container_name}$"],
            capture_output=True, text=True
        )
        if result_running.stdout.strip():
            print(f"Container '{self.container_name}' is running.")
            return

        # Check if container exists but is stopped.
        result_all = subprocess.run(
            ["docker", "ps", "-aq", "-f", f"name=^{self.container_name}$"],
            capture_output=True, text=True
        )
        if result_all.stdout.strip():
            print(f"Container '{self.container_name}' exists but is not running. Starting it...")
            result_start = subprocess.run(
                ["docker", "start", self.container_name],
                capture_output=True, text=True
            )
            if result_start.returncode != 0:
                print("Error starting persistent container:")
                print(result_start.stderr)
                sys.exit(1)
            print(f"Container '{self.container_name}' started.")
            return

        # Container does not exist; start a new one using the verified command:
        # docker run -d --name voice_runner -v ${PWD}\output:/output -e IN_CONTAINER=1 
        # --entrypoint /bin/bash piper_tts:latest -c "while true; do sleep 3600; done"
        print(f"Container '{self.container_name}' not found. Starting it...")
        run_cmd = [
                        "docker", "run", "-d",
                        "--name", self.container_name,
                        "-v", self.output_dir,
                        self.docker_image,
                    ]

        res = subprocess.run(run_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("Error starting persistent container:")
            print(res.stderr)
            sys.exit(1)
        print(f"Container '{self.container_name}' started.")

    def speak(self, text: str, *args, **kwargs) -> None:
        """
        Generate speech from text using the persistent container.

        Args:
            text (str): Text to synthesize.
        """
        if os.environ.get("IN_CONTAINER"):
            local_text_to_speech(text)
        else:
            self.ensure_container()
            # Use the verified docker exec command.
            exec_cmd = [
                            "docker", "exec", self.container_name,
                            "/app/run_tts.sh", text
                        ]

            print("Running docker exec command in persistent container...")
            result = subprocess.run(exec_cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print("Error running docker exec command:")
                print(result.stderr)
                sys.exit(1)
            output_file = os.path.join(self.mount_dir, "output.wav")
            if not os.path.exists(output_file):
                print("Error: output.wav was not generated.")
                sys.exit(1)
            print("Playing output.wav...")
            play_audio(output_file)

def main(*args, text:str=None, file:str=None, **kwargs) -> None:
    # If running inside the container, bypass argument parsing.
    if os.environ.get("IN_CONTAINER"):
        if not os.path.exists(INPUT_FILE):
            print(f"❌ Error: {INPUT_FILE} not found in container.")
            sys.exit(1)
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            loaded_text = f.read().strip()
        if not loaded_text:
            print("❌ Error: speak.txt is empty in container.")
            sys.exit(1)
        local_text_to_speech(loaded_text)
        sys.exit(0)

    if text is not None:
        input_text = text
    elif os.path.exists(str(file)):
        with open(file, "r", encoding="utf-8") as f:
            input_text = f.read().strip()
    else:
        print(f"Error: file '{file}' does not exist.")
        sys.exit(1)

    speaker = Speaker(*args, **kwargs)
    speaker.speak(input_text, *args, **kwargs)

if __name__ == "__main__":
        # Host mode: Parse command-line arguments.
    parser = argparse.ArgumentParser(
        description="Generate speech using a persistent Docker TTS container and play the audio."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-t", "--text", help="Direct input text for TTS.")
    group.add_argument("-f", "--file", help="Path to text file for TTS.")
    args = parser.parse_args()

    main(text=args.text, file=args.file)
