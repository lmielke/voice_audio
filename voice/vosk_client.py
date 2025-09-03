import argparse
import requests
import time
import threading
from pynput import keyboard

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", required=True, help="Server index (e.g. 1 for while-ai-1)")
    parser.add_argument("-k", "--key", default="f20", help="Trigger key (default: f20)")
    return parser.parse_args()

args = parse_args()
SERVER_URL = f"http://while-ai-{args.server}:5005"
TRIGGER_KEY = args.key.lower()

is_listening = False

def listen_and_get_result():
    global is_listening
    if not is_listening:
        print(f"Triggering remote listen on {SERVER_URL}/listen ...")
        requests.post(f"{SERVER_URL}/listen")
        is_listening = True
        print("Listening started. Press the trigger key again to stop and fetch result.")
    else:
        print(f"Sending hold signal to {SERVER_URL}/hold ...")
        requests.post(f"{SERVER_URL}/hold")
        print("Waiting for result...")
        while True:
            resp = requests.get(f"{SERVER_URL}/result")
            result = resp.json().get("result")
            if result:
                print("Transcript:", result)
                break
            time.sleep(1)
        is_listening = False
        print("Ready for next session. Press the trigger key to start listening again.")

def on_press(key):
    try:
        if hasattr(keyboard.Key, TRIGGER_KEY) and key == getattr(keyboard.Key, TRIGGER_KEY):
            threading.Thread(target=listen_and_get_result, daemon=True).start()
    except Exception as e:
        print(f"Key error: {e}")

if __name__ == "__main__":
    print(f"Press {TRIGGER_KEY.upper()} to start/stop remote Vosk listener (Ctrl+C to exit)...")
    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nExiting vosk_client.")
        listener.stop()
