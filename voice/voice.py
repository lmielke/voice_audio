import os
import sys
import threading
import wave
import tkinter as tk
from tkinter import Label
from vosk import Model, KaldiRecognizer, SetLogLevel
import pyaudio
import pyttsx3
from pynput import keyboard
from colorama import Fore, Style
from tqdm import tqdm
import time

import voice.settings as sts

# After the existing imports at the top of the file
try:
    import winsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False


# ---------------------------------------
# Configuration
# ---------------------------------------
MODEL_PATH = "{sts.resources_dir}/vosk_model/vosk-model-en-us-0.22"
TIMEOUT_SECONDS = 20
PROGRESS_BAR_SECONDS = 25
CHUNK = 1024
RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16

# ---------------------------------------
# Global Flags and Variables
# ---------------------------------------
is_recording = False
recording_thread = None
last_speech_time = time.time()
running = True
stop_commands = {'stop recording', 'stop listening', 'end recording', 'end listening', 
                'okay thanks', 'okay bye', 'thank you bye', 'thanks bye', 'alright thanks', 
                'alright bye', 'forget it bye', 'thats all bye'}

# ---------------------------------------
# Suppress Vosk logs
# ---------------------------------------
SetLogLevel(-1)

# Check if model path exists
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(    f"Vosk model not found. "
                                f"Please place it in '{sts.resources_dir}/vosk_model/vosk-model-en-us-0.22'.")

model_loaded = False
model = None

# ---------------------------------------
# Model Loading
# ---------------------------------------
def model_loader():
    global model, model_loaded
    model = Model(MODEL_PATH)
    model_loaded = True

loader_thread = threading.Thread(target=model_loader)
loader_thread.start()

# Initialize TTS Engine
tts_engine = pyttsx3.init()

def speak(text: str):
    tts_engine.say(text)
    tts_engine.runAndWait()

speak("Loading Vosk model. This will take about 30 seconds.")

# Show a progress bar for a fixed 30 seconds
for i in tqdm(range(PROGRESS_BAR_SECONDS), desc="Initializing, ...", ncols=70, colour="cyan"):
    time.sleep(1)
loader_thread.join()

speak("Model loaded successfully! Press zero on the num block, and I will listen.")


# ---------------------------------------
# Audio and GUI Setup
# ---------------------------------------
audio = pyaudio.PyAudio()

root = tk.Tk()
root.title("Recording")
root.geometry("200x100")
root.withdraw()

recording_label = Label(root, text="● Recording", font=("Helvetica", 24), fg="red")
recording_label.pack(expand=True)

recognizer = KaldiRecognizer(model, RATE)

# ---------------------------------------
# Functions
# ---------------------------------------
def show_recording_symbol():
    root.deiconify()

def close_recording_symbol():
    root.withdraw()

def toggle_recording():
    global is_recording, recording_thread
    if not is_recording:
        is_recording = True
        print(f"{Fore.GREEN}Recording started!{Style.RESET_ALL}")
        show_recording_symbol()
        recording_thread = threading.Thread(target=record_audio)
        recording_thread.start()
    else:
        is_recording = False
        print(f"{Fore.RED}Recording stopped!{Style.RESET_ALL}")
        close_recording_symbol()
        if recording_thread:
            recording_thread.join()

def record_audio():
    global is_recording, last_speech_time, running
    # If we're not running or not recording, return immediately
    if not running or not is_recording:
        return
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                            input=True, frames_per_buffer=CHUNK)
        # In the record_audio() function, after opening the stream, add:
        last_speech_time = time.time()
        frames = []
        speak("What now!")
        # In toggle_recording(), right after `print(f"{Fore.GREEN}Recording started!{Style.RESET_ALL}")`:
        while running and is_recording:
            data = stream.read(CHUNK)
            if recognizer.AcceptWaveform(data):
                result = recognizer.Result()
                recognized_text = eval(result)["text"].strip()
                if recognized_text and recognized_text != 'the':
                    print(f"{Fore.CYAN}Recognized Text: {recognized_text}{Style.RESET_ALL}")
                    last_speech_time = time.time()
                    if any([cmd in recognized_text for cmd in stop_commands]):
                        print(f"{Fore.YELLOW}Stopping recording.{Style.RESET_ALL}")
                        is_recording = False
                        break
            frames.append(data)
            # Timeout after TIMEOUT_SECONDS of silence
            if time.time() - last_speech_time > TIMEOUT_SECONDS:
                print(f"{Fore.YELLOW}Listening Timeout: Stopping recording.{Style.RESET_ALL}")
                is_recording = False
                break

        stream.stop_stream()
        stream.close()
        close_recording_symbol()
        # Still in toggle_recording(), right after `print(f"{Fore.RED}Recording stopped!{Style.RESET_ALL}")`:
        play_sound("STOP")

        # Flush final result
        final_res = recognizer.FinalResult()
        final_text = eval(final_res).get("text", "").strip()
        if final_text and final_text != 'the':
            print(f"{Fore.CYAN}Recognized Text: {final_text}{Style.RESET_ALL}")

        # Save recording
        with wave.open("output.wav", "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))

    except OSError as e:
        # If we're shutting down (running=False), just suppress the error silently
        if running:
            print("Recording thread encountered an OSError:", e)
        # Otherwise, do nothing

    except Exception as e:
        print("Recording thread encountered an error:", e)

def start_listener():
    def on_press(key):
        if key == keyboard.Key.f20:
            toggle_recording()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

def main():
    global running, is_recording
    print("Press F20 to toggle recording...")
    listener_thread = threading.Thread(target=start_listener)
    listener_thread.daemon = True
    listener_thread.start()
    # After model loading is complete (right after "print('Model loaded successfully!')"):
    try:
        root.mainloop()
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        print("Exiting...")
        speak('buy buy')
        running = False
        is_recording = False
    finally:
        # If recording is ongoing, stop it
        if recording_thread and recording_thread.is_alive():
            recording_thread.join()
        audio.terminate()
        sys.exit(0)


# After other functions and before main(), define play_sound
def play_sound(status: str):
    """
    Plays a short acoustic signal based on the given status.
    Args:
        status: (str) One of ["LOADED", "START", "STOP"].
    """
    if SOUND_AVAILABLE:
        if status == "LOADED":
            winsound.Beep(800, 150)   # 800 Hz for 150ms
        elif status == "START":
            winsound.Beep(600, 150)   # Lower pitch
            winsound.Beep(1000, 150)  # Higher pitch
        elif status == "STOP":
            winsound.Beep(1000, 150)  # Higher pitch
            winsound.Beep(600, 150)   # Lower pitch
    else:
        # Fallback if winsound is not available
        root.bell()

if __name__ == "__main__":
    main()
