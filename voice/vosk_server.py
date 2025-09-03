import time, threading
from flask import Flask, jsonify
from voice_class import App

app = Flask(__name__)

class Chat:
    def __init__(self):
        self.app = App()
        self.prev_user_count = self.app.conv_manager.msg_count_user
        print(f"Initial user message count: {self.prev_user_count}")
        self.last_transcript = None
        self.lock = threading.Lock()

    def monitor_conversation(self):
        try:
            while True:
                if self.app.conv_manager.msg_count_user != self.prev_user_count:
                    print(f"{self.get_session_user_messages() = }")
                    last_user_msg = self.app.conversation.get_last_n_messages(role="user")
                    print(f"Last user message: {last_user_msg}")
                    time.sleep(2)
                    if '/bye' in last_user_msg:
                        self.running = False
                        raise KeyboardInterrupt
                    self.prev_user_count = self.app.conv_manager.msg_count_user
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("Shutting down conversation monitoring...")

    def run(self):
        monitor_thread = threading.Thread(target=self.monitor_conversation, daemon=True)
        monitor_thread.start()
        self.app.run()

class VoskServer(Chat):
    def __init__(self):
        super().__init__()
        self.listen_start_user_count = None
        self.listening_lock = threading.Lock()
        self.is_listening = False
        threading.Thread(target=self.start_api, daemon=True).start()

    def start_api(self):
        app.config["VOSK_SERVER"] = self
        app.run(host="0.0.0.0", port=5005)

    def trigger_listen(self):
        with self.listening_lock:
            if not self.is_listening and not self.app.listener.recording:
                self.listen_start_user_count = self.app.conv_manager.msg_count_user
                self.is_listening = True
                print("[SERVER] Starting listen session at user_count", self.listen_start_user_count)
                self.app.listener.toggle_recording()  # Starts listening
                self.is_listening = False
                print("[SERVER] Finished listen session")

    def hold_listen(self):
        # Only toggle_recording to pause/stop; DO NOT reset listen_start_user_count
        if self.app.listener.recording:
            print("[SERVER] Pausing listen session")
            self.app.listener.toggle_recording()
            print("[SERVER] Paused listen session")

    def get_session_user_messages(self):
        start = self.listen_start_user_count or 0
        print(f"Getting session user messages from count: {start}")
        curr = self.app.conv_manager.msg_count_user
        print(f"Current user message count: {curr}")
        n = curr - start
        print(f"Number of new user messages since listening started: {n}")
        if n > 0:
            # Return last n user messages
            return self.app.conversation.get_last_n_messages(role="user", n=n)
        return []

# Flask endpoints
@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "running"})

@app.route('/listen', methods=['POST'])
def listen():
    server = app.config["VOSK_SERVER"]
    threading.Thread(target=server.trigger_listen).start()
    return jsonify({"status": "listening"})

@app.route('/result', methods=['GET'])
def result():
    server = app.config["VOSK_SERVER"]
    if not server.app.listener.recording:
        msgs = server.get_session_user_messages()
        print(f"Returning session user messages: {msgs}")
        return jsonify({"result": msgs})
    else:
        return jsonify({"result": None})

@app.route('/hold', methods=['POST'])
def hold():
    server = app.config["VOSK_SERVER"]
    threading.Thread(target=server.hold_listen).start()
    return jsonify({"status": "paused"})

@app.route('/stop', methods=['POST'])
def stop():
    server = app.config["VOSK_SERVER"]
    server.running = False
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    vs = VoskServer()
    vs.run()
