# voice/apis/serve.py
from voice.vosk_server import VoskServer

def main(*args, **kwargs):
    """
    Entry point for the 'serve' API.
    Initializes and runs the VoskServer.
    """
    print("Initializing Vosk server...")
    server = VoskServer()
    server.run()