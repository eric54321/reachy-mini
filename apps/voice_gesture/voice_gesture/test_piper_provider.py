"""Tests for the Piper provider. Requires the en_US-lessac-medium Piper voice
to be downloaded into voices/ (see tts/piper_provider.py docstring).
Run with: pytest test_piper_provider.py
"""

import wave

from voice_gesture.tts.piper_provider import DEFAULT_VOICE, list_available_voices, speak


def test_speak_produces_a_playable_wav_file():
    path = speak("Hello there.")
    try:
        assert path.exists()
        assert path.stat().st_size > 0
        with wave.open(str(path), "rb") as wav_file:
            assert wav_file.getnframes() > 0
    finally:
        path.unlink(missing_ok=True)


def test_list_available_voices_includes_the_default():
    voices = list_available_voices()
    assert DEFAULT_VOICE in voices
    assert voices == sorted(voices)


def test_speak_produces_longer_audio_for_longer_text():
    short_path = speak("Hi.")
    long_path = speak("This is a much longer sentence that should take noticeably more time to say out loud.")
    try:
        assert long_path.stat().st_size > short_path.stat().st_size
    finally:
        short_path.unlink(missing_ok=True)
        long_path.unlink(missing_ok=True)
