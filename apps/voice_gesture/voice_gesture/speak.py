"""Text-to-speech adapter: turn a sentence into an audio file.

Every provider (Piper, and later OpenAI/ElevenLabs/Grok) plugs in behind the
same `speak(sentence, voice_id) -> Path` shape, so the rest of the app never
has to know which one produced the audio.

Currently implemented: Piper (free, local, no API key/network needed at
runtime — just a downloaded .onnx voice model).

Voice models live in `voices/<voice_id>.onnx` (+ matching `.onnx.json`
config), fetched with:

    python -m piper.download_voices <voice_id> --download-dir voices
"""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

from piper import PiperVoice

VOICES_DIR = Path(__file__).parent.parent / "voices"

DEFAULT_VOICE_ID = "en_US-lessac-medium"

# Cache loaded PiperVoice objects (loading the .onnx model is the slow part).
_voice_cache: dict[str, PiperVoice] = {}


def _load_voice(voice_id: str) -> PiperVoice:
    if voice_id not in _voice_cache:
        model_path = VOICES_DIR / f"{voice_id}.onnx"
        config_path = VOICES_DIR / f"{voice_id}.onnx.json"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper voice '{voice_id}' not found at {model_path}. "
                f"Download it with: python -m piper.download_voices {voice_id} "
                f"--download-dir {VOICES_DIR}"
            )
        _voice_cache[voice_id] = PiperVoice.load(model_path, config_path=config_path)
    return _voice_cache[voice_id]


def list_available_voices() -> list[str]:
    """Voice ids that are actually downloaded and ready to use (voices/*.onnx)."""
    if not VOICES_DIR.exists():
        return []
    return sorted(p.stem for p in VOICES_DIR.glob("*.onnx"))


def speak(sentence: str, voice_id: str = DEFAULT_VOICE_ID) -> Path:
    """Synthesize `sentence` with the given voice, return the path to a WAV file.

    The file is written to a temp directory; the caller is responsible for
    playing it (e.g. via `reachy_mini.media_manager.play_sound(path)`) and
    may delete it afterwards.
    """
    voice = _load_voice(voice_id)

    fd, path_str = tempfile.mkstemp(suffix=".wav", prefix="voice_gesture_")
    path = Path(path_str)
    with wave.open(path_str, "wb") as wav_file:
        voice.synthesize_wav(sentence, wav_file)
    os.close(fd)

    return path


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or "Hello, I am Reachy Mini."
    out_path = speak(text)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
