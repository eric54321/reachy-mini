"""Piper TTS provider: free, local, ONNX-based, no network needed at runtime.

Voice models live in `voices/<voice_name>.onnx` (+ matching `.onnx.json`
config), fetched with:

    python -m piper.download_voices <voice_name> --download-dir voices
"""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

from piper import PiperVoice

VOICES_DIR = Path(__file__).parent.parent.parent / "voices"

DEFAULT_VOICE = "en_GB-alan-medium"

# Cache loaded PiperVoice objects (loading the .onnx model is the slow part).
_voice_cache: dict[str, PiperVoice] = {}


def _load_voice(voice_name: str) -> PiperVoice:
    if voice_name not in _voice_cache:
        model_path = VOICES_DIR / f"{voice_name}.onnx"
        config_path = VOICES_DIR / f"{voice_name}.onnx.json"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper voice '{voice_name}' not found at {model_path}. "
                f"Download it with: python -m piper.download_voices {voice_name} "
                f"--download-dir {VOICES_DIR}"
            )
        _voice_cache[voice_name] = PiperVoice.load(model_path, config_path=config_path)
    return _voice_cache[voice_name]


def list_available_voices() -> list[str]:
    """Voice names actually downloaded and ready to use (voices/*.onnx)."""
    if not VOICES_DIR.exists():
        return []
    return sorted(p.stem for p in VOICES_DIR.glob("*.onnx"))


def speak(sentence: str, voice_name: str = DEFAULT_VOICE) -> Path:
    """Synthesize `sentence`, return the path to a temp WAV file the caller owns."""
    voice = _load_voice(voice_name)

    fd, path_str = tempfile.mkstemp(suffix=".wav", prefix="reachy_says_piper_")
    path = Path(path_str)
    with wave.open(path_str, "wb") as wav_file:
        voice.synthesize_wav(sentence, wav_file)
    os.close(fd)

    return path


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or "Reachy says, touch your nose!"
    out_path = speak(text)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
