# entry_point.py
# this is an example api for voice

from voice import settings as sts
import voice.speaker as speaker

def entry_point_function(*args, **kwargs):
    inst = speaker.main(*args, **kwargs)
    return inst

def main(*args, **kwargs):
    """
    All entry points must contain a main function like main(*args, **kwargs)
    """
    return entry_point_function(*args, **kwargs)