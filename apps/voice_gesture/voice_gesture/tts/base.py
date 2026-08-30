"""Protocol every TTS provider module implements.

A "provider" here is a module (not a class) exposing two functions at module
level: `speak()` and `list_available_voices()`. See `piper_provider.py` /
`pocket_tts_provider.py` for reference implementations, and `tts/__init__.py`
for how a provider gets registered.

This file is documentation/typing only — nothing imports it at runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TTSProvider(Protocol):
    def list_available_voices(self) -> list[str]:
        """Voice names usable with this provider right now (no provider prefix)."""
        ...

    def speak(self, sentence: str, voice_name: str) -> Path:
        """Synthesize `sentence`, return the path to a temp WAV file the caller owns."""
        ...
