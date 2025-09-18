# voice_class.py

import json, os, pyaudio, pyttsx3, re, sys, threading, time, wave
from datetime import datetime as dt
import tkinter as tk
from tkinter import Label
from pynput import keyboard
from tqdm import tqdm
from colorama import Fore, Style
import random as rd

from vosk import Model, KaldiRecognizer, SetLogLevel

import voice.settings as sts
# ---------------------------------------
# Configuration
# ---------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(sts.resources_dir, 'vosk_model', 'vosk-model-en-us-0.42-gigaspeech')
TIMEOUT_SECONDS = 20
LISTEN_TIMEOUT = .1
PROGRESS_BAR_SECONDS = 28
CHUNK = 1024
RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
RUNTIME = re.sub(r"([: .])", r"-" , str(dt.now()))
MESSAGES_FILE = os.path.join(sts.resources_dir, 'chats', f"{RUNTIME}_messages.json")
PAUSE_COMMANDS = {
                "stop recording", "stop listening", "end recording", "end listening",
                "okay thanks", "okay bye", "thank you bye", "thanks bye", "alright thanks",
                "alright bye", "forget it bye", "that's all bye", "okay that's it", 
                "okay that's all", "hold it",
}

EXIT_COMMANDS = {
                    "over and out", "thank you and good bye", "good bye", "exit", "quit",
                    "thank you and goodbye", "goodbye",
                }
INVALID_TERMS = {"the", "I"}

try:
    import winsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False

SetLogLevel(-1)

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Vosk model not found in { MODEL_PATH =}.")

# ---------------------------------------
# Classes
# ---------------------------------------

# Global speaking flag for the entire module
GLOBAL_SPEAKING_FLAG = threading.Event()


class Speaker:
    def __init__(self, *args, speaking_flag: threading.Event, **kwargs):
        self.tts_engine = pyttsx3.init()
        self.tts_lock = threading.Lock()
        self.last_speak_time = 0  # Track when speaking finishes

    def speak(self, *args, text: str, **kwargs) -> None:
        with self.tts_lock:
            GLOBAL_SPEAKING_FLAG.set()
            time.sleep(LISTEN_TIMEOUT)
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            self.last_speak_time = time.time()
            GLOBAL_SPEAKING_FLAG.clear()

    def play_sound(self, *args, status: str, **kwargs) -> None:
        """
        Play a short acoustic signal.
        
        Args:
            status (str): One of ["LOADED", "START", "STOP"].
        """
        with self.tts_lock:
            if SOUND_AVAILABLE:
                if status == "LOADED":
                    winsound.Beep(800, 150)
                elif status == "START":
                    winsound.Beep(600, 150)
                    winsound.Beep(1000, 150)
                elif status == "STOP":
                    winsound.Beep(1000, 150)
                    winsound.Beep(600, 150)
            else:
                root = tk.Tk()
                root.bell()
                root.destroy()


class Listener:
    def __init__(self, *args, model_path: str, speaker: Speaker,
                 speaking_flag: threading.Event, conversation, 
                 timeout: int = TIMEOUT_SECONDS, shutdown_callback=None, **kwargs):
        """
        Initialize listener with model and audio configs.
        
        Args:
            model_path (str): Path to Vosk model.
            speaker (Speaker): Speaker instance for status messages.
            conversation: The shared Conversation instance.
            timeout (int): Silence timeout in seconds.
            shutdown_callback: Optional callback to execute shutdown.
        """
        self.model = None
        self.model_path = model_path
        self.timeout = timeout
        self.speaker = speaker
        self.speaking_flag = speaking_flag
        self.conversation = conversation
        self.recording = False
        self.running = True
        self.text = ""
        self.last_speech_time = time.time()
        self.recognizer = None
        self.audio = pyaudio.PyAudio()
        self.recording_thread = None
        self.gui_root = None
        self.recording_label = None
        self.reacts = ('How can I help?', 'What now?', 'What do you want!', 'Not again!',
                       'Havent I suffered enough?')
        self.shutdown_callback = shutdown_callback

    def load_model(self, *args, **kwargs) -> None:
        """
        Load the Vosk model.
        """
        self.model = Model(self.model_path)
        self.recognizer = KaldiRecognizer(self.model, RATE)

    def setup_gui(self, *args, **kwargs) -> None:
        """
        Setup and hide GUI initially.
        """
        self.gui_root = tk.Tk()
        self.gui_root.title("Recording")
        self.gui_root.geometry("200x100")
        self.gui_root.withdraw()
        self.recording_label = Label(self.gui_root, text="● Recording",
                                     font=("Helvetica", 24), fg="red")
        self.recording_label.pack(expand=True)

    def toggle_recording(self, *args, **kwargs) -> None:
        """
        Toggle recording on/off.
        """
        if not self.recording:
            self.start_recording()
        else:
            self.pause_recording()

    def start_recording(self, *args, **kwargs) -> None:
        """
        Start the recording process.
        """
        self.recording = True
        print(f"{Fore.GREEN}Recording resumed!{Style.RESET_ALL}")
        self.gui_root.deiconify()  # show recording symbol
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.recording_thread.start()

    def pause_recording(self, *args, **kwargs) -> None:
            """
            Signals the recording thread to stop and waits for it to finish.
            """
            if self.recording and self.recording_thread.is_alive():
                self.recording = False
                self.recording_thread.join()  # Wait for the thread to clean up

    def record_audio(self, *args, **kwargs) -> None:
            if not self.running or not self.recording:
                return
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
            self.last_speech_time = time.time()
            frames = []
            self.say_hello(*args, **kwargs)

            while self.running and self.recording:
                self.hold_while_speaking(*args, **kwargs)
                data = stream.read(CHUNK, exception_on_overflow=False)
                if self.recognizer.AcceptWaveform(data):
                    self.text = eval(self.recognizer.Result())["text"].strip()
                else:
                    self.text = ""
                frames.append(data)
                if self.is_valid_text(*args, **kwargs):
                    self.conversation.append_message(role="user", content=self.text)
                    self.last_speech_time = time.time()

            # --- SAFE CLEANUP SEQUENCE ---
            stream.stop_stream()
            stream.close()

            # Now that the stream is safely closed, get the final result.
            final_text = eval(self.recognizer.FinalResult()).get("text", "").strip()
            if final_text and final_text not in INVALID_TERMS:
                 self.conversation.append_message(role="user", content=final_text)

            print(f"{Fore.RED}Recording paused!{Style.RESET_ALL}")
            self.gui_root.withdraw()
            self.speaker.play_sound(status="STOP")
            self.save_audio(frames)
            self.recognizer = KaldiRecognizer(self.model, RATE)

    def say_hello(self, *args, **kwargs) -> None:
        """
        Say hello to the user.
        """
        self.speaker.speak(text=self.reacts[0] if self.conversation.msg_count_user == 0 
                           else rd.choice(self.reacts))

    def hold_while_speaking(self, *args, **kwargs) -> None:
        """
        Hold the recording for a specified time.
        """
        while GLOBAL_SPEAKING_FLAG.is_set():
            time.sleep(0.05)
            continue

    def recognize_text(self, *args, **kwargs) -> str:
        data = self.stream.read(CHUNK)
        if self.recognizer.AcceptWaveform(data):
            self.text = eval(self.recognizer.Result())["text"].strip()
        else:
            self.text = ""
        self.frames.append(data)

    def is_valid_text(self, *args, **kwargs) -> None:
        """
        Clean up the Vosk result and return the text.
        
        Args:
            result (str): Vosk recognizer result.
        
        Returns:
            str: Cleaned up text.
        """
        if self.text and self.text not in INVALID_TERMS:
            if any(cmd in self.text for cmd in PAUSE_COMMANDS):
                print(f"{Fore.YELLOW}Pausing recording.{Style.RESET_ALL}")
                self.recording = False
                return False
            if any(self.text in cmd for cmd in EXIT_COMMANDS):
                print(f"{Fore.YELLOW}Exit command recognized. Shutting down.{Style.RESET_ALL}")
                self.running = False
                if self.shutdown_callback:
                    self.shutdown_callback()
                else:
                    sys.exit(0)
                return False
            return True
        if time.time() - self.last_speech_time > self.timeout:
            print(f"{Fore.YELLOW}Listening Timeout: Pausing recording.{Style.RESET_ALL}")
            self.recording = False
            return False

    def cleanup(self, *args, **kwargs) -> None:
        final_res = self.recognizer.FinalResult()
        final_text = eval(final_res).get("text", "").strip()
        if final_text and final_text not in INVALID_TERMS:
            if any(final_text in cmd for cmd in EXIT_COMMANDS):
                self.conversation.append_message(role="user", content='/bye')
            elif any(cmd in final_text for cmd in PAUSE_COMMANDS):
                pass
            else:
                self.conversation.append_message(role="user", content=final_text)

    def save_audio(self, frames, *args, **kwargs) -> None:
        """
        Save recorded audio to output.wav.
        
        Args:
            frames (list): Recorded audio frames.
        """
        with wave.open("output.wav", "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))


class Conversation:
    """
    Manages the conversation in memory and persists messages to a file
    asynchronously.
    """
    def __init__(self) -> None:
        self.messages: dict[str, list[dict]] = {"assistant": [], "user": []}
        self.msg_count_assistant = 0
        self.msg_count_user = 0

    def append_message(self, role: str, content: str) -> None:
        """
        Append a message to the in-memory conversation and then save it to file.
        
        Args:
            role (str): "user" or "assistant".
            content (str): Message text.
        """
        msg = {"role": role, "content": content, "msg_timestamp": time.time()}
        self.messages[role].append(msg)
        if role == "assistant":
            self.msg_count_assistant += 1
        elif role == "user":
            self.msg_count_user += 1

        color = Fore.YELLOW if role == "assistant" else Fore.GREEN
        print(f"{color}{role}:{Style.RESET_ALL} {content}")

        threading.Thread(target=self._save_message_to_file, args=(msg,)).start()

    def _save_message_to_file(self, msg: dict) -> None:
        messages = []
        if os.path.exists(MESSAGES_FILE):
            try:
                with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except json.JSONDecodeError:
                messages = []
        messages.append(msg)
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    
    def get_last_n_messages(self, role: str = None, n: int = 1) -> list:
        """
        Retrieve the last n messages from the in-memory store.

        Args:
            role (str, optional): Filter by role ("assistant" or "user").
            n (int, optional): Number of messages to return. Default is 1.

        Returns:
            list: The last n messages (each as dict, newest last). Returns an empty list if none exist.
        """
        if role:
            msgs = self.messages[role]
            return msgs[-n:] if msgs else []
        # If no role, combine both and sort by timestamp
        all_msgs = self.messages["assistant"] + self.messages["user"]
        all_msgs.sort(key=lambda x: x["msg_timestamp"])
        return all_msgs[-n:] if all_msgs else []



class ConversationManager:
    def __init__(self, *args, speaker: Speaker, conversation: Conversation, **kwargs):
        """
        Manage conversation responses.
        """
        self.speaker = speaker
        self.conversation = conversation
        self.running = True

    def poll_responses(self, *args, **kwargs) -> None:
        last_msg_count = self.conversation.msg_count_assistant
        while self.running:
            current_count = self.conversation.msg_count_assistant
            if current_count > last_msg_count:
                response = self.conversation.get_last_n_messages(role='assistant', n=1)
                if response:
                    self.speaker.speak(text=response)
                last_msg_count = current_count
            time.sleep(0.5)

    @property
    def msg_count_assistant(self) -> int:
        return self.conversation.msg_count_assistant

    @property
    def msg_count_user(self) -> int:
        return self.conversation.msg_count_user


class App:
    def __init__(self, *args, **kwargs):
        self.speaking_flag = threading.Event()
        self.speaker = Speaker(speaking_flag=self.speaking_flag)
        self.conversation = Conversation()  # Create a single Conversation instance.
        self.listener = Listener(model_path=MODEL_PATH, speaker=self.speaker,
                                 speaking_flag=self.speaking_flag,
                                 conversation=self.conversation,
                                 shutdown_callback=self.shutdown)
        self.conv_manager = ConversationManager(speaker=self.speaker,
                                                  conversation=self.conversation)
        self.listener.setup_gui()
        self.keyboard_listener = None

    def run(self, *args, **kwargs) -> None:
        """
        Run the main application logic.
        """
        self.initial_loading()
        # self.start_listener_thread()
        self.start_gui()

    def initial_loading(self, *args, **kwargs) -> None:
        """
        Load the model in a separate thread and show progress bar during loading.
        """
        model_loaded = threading.Event()

        def load_model_thread():
            self.listener.load_model()
            model_loaded.set()

        loader_thread = threading.Thread(target=load_model_thread)
        loader_thread.start()

        self.speaker.speak(text="Loading Vosk model. This might take 20 to 25 seconds.")

        for _ in tqdm(range(PROGRESS_BAR_SECONDS), desc="Initializing...", 
                      ncols=70, colour="cyan"):
            if model_loaded.is_set():
                break
            time.sleep(1)

        loader_thread.join()
        self.speaker.speak(text=("Model loaded! "
                                 "I start to listen when you press "
                                 "the zero key on the num block."))
        self.speaker.play_sound(status="LOADED")

    def start_listener_thread(self, *args, **kwargs) -> None:
        """
        Start a keyboard listener for toggling recording and the conversation poll.
        """
        def on_press(key):
            if key == keyboard.Key.f20:
                self.listener.toggle_recording()

        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.daemon = True
        self.keyboard_listener.start()

        resp_thread = threading.Thread(target=self.conv_manager.poll_responses)
        resp_thread.daemon = True
        resp_thread.start()

    def keyboard_listener_func(self, on_press, *args, **kwargs) -> None:
        """
        Alternative keyboard listener that uses join.
        """
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()

    def start_gui(self, *args, **kwargs) -> None:
        """
        Start the Tkinter mainloop.
        """
        try:
            self.listener.gui_root.mainloop()
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self, *args, **kwargs) -> None:
        """
        Shutdown procedure.
        """
        print("Exiting...")
        self.speaker.speak(text='Have a nice day, bye.')
        self.listener.running = False
        self.conv_manager.running = False
        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
        if self.listener.gui_root:
            self.listener.gui_root.quit()
        sys.exit(0)


if __name__ == "__main__":
    app = App()
    app.run()
