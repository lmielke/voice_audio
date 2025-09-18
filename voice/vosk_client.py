# Replace the entire contents of this file with the new class-based structure

import requests
import time
import threading
from pynput import keyboard
import voice.settings as sts

class VoskClient:
    def __init__(self, *args, va_server: int, key: str = "f20", **kwargs):
        self.server_url = f"{va_server}:{sts.va_port}"
        self.trigger_key_str = key.lower()
        self.is_listening = False
        try:
            self.trigger_key = getattr(keyboard.Key, self.trigger_key_str)
        except AttributeError:
            raise ValueError(f"Invalid trigger key: {self.trigger_key_str}")

    def _get_result(self):
        print("Waiting for result...")
        while True:
            try:
                resp = requests.get(f"{self.server_url}/result", timeout=5)
                resp.raise_for_status()
                result = resp.json().get("result")
                if result:
                    transcript = " ".join([msg.get("content", "") for msg in result])
                    print(f"Transcript: {transcript}")
                    break
            except requests.exceptions.RequestException as e:
                print(f"Error fetching result: {e}")
                break
            time.sleep(1)
        self.is_listening = False
        print("Ready for next session. Press F20 to start again.")

    def _toggle_listening(self):
        endpoint = "hold" if self.is_listening else "listen"
        action = "Stopping" if self.is_listening else "Starting"
        print(f"{action} remote listening on {self.server_url}/{endpoint}...")
        try:
            requests.post(f"{self.server_url}/{endpoint}", timeout=5)
            self.is_listening = not self.is_listening
            if not self.is_listening: # If we just stopped, get the result
                self._get_result()
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with server: {e}")

    def on_press(self, key):
        if key == self.trigger_key:
            threading.Thread(target=self._toggle_listening, daemon=True).start()

    def run(self):
        print(f"Vosk Client started. Connecting to {self.server_url}")
        print(f"Press {self.trigger_key_str.upper()} to toggle listening.")
        with keyboard.Listener(on_press=self.on_press) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\nExiting client.")