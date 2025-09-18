# voice/apis/client.py
from voice.vosk_client import VoskClient

def main(*args, **kwargs):
    """
    Entry point for the 'client' API.
    Initializes and runs the VoskClient.
    """
    try:
        client = VoskClient(*args, **kwargs)
        client.run()
    except (ValueError, KeyError) as e:
        print(f"Error initializing client: {e}")