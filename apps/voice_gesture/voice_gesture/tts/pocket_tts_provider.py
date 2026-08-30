"""pocket-tts (Kyutai) provider: local, CPU-capable neural TTS with built-in
character voices plus voice cloning from any short audio sample.

Optional dependency: `pocket-tts` (which pulls in `torch`) is only imported
lazily, the first time this provider is actually used — install it with:

    pip install -e ".[kyutai]"

Voices are fetched from Hugging Face on first use and cached locally by
pocket-tts itself (`~/.cache/huggingface`) — no manual download step needed,
and no network access after the first call for a given voice. Browse the
full voice library at https://huggingface.co/kyutai/tts-voices.

BUILTIN_VOICES work immediately with no account needed. VOICE_ALIASES (e.g.
"announcer") clone a real audio sample and need the gated voice-cloning
weights — see the comment on VOICE_ALIASES below before using one.
"""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

DEFAULT_VOICE = "alba"

# pocket-tts's own built-in voice names (precomputed embeddings, resolved
# internally by the library). Work out of the box, no Hugging Face account
# or login needed.
BUILTIN_VOICES = [
    "alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma",
    "anna", "vera", "charles", "paul", "george", "mary", "jane", "michael", "eve",
    "bill_boerst", "peter_yearsley", "stuart_bell", "caro_davy", "giovanni", "lola",
    "juergen", "rafael", "estelle",
]  # fmt: skip

# Friendly shortcuts for voices from the wider kyutai/tts-voices library that
# aren't one of the built-in names above. Any raw "hf://..." path or local
# WAV file also works as a voice_name even if it isn't listed here.
#
# These clone a real audio sample, which needs pocket-tts's voice-cloning
# weights — a *gated* Hugging Face repo. Until you've both (1) accepted the
# terms at https://huggingface.co/kyutai/pocket-tts and (2) logged in locally
# with `uvx hf auth login`, pocket-tts silently falls back to the
# non-cloning weights and these voices raise a ValueError. BUILTIN_VOICES
# above always works without any of that.
VOICE_ALIASES: dict[str, str] = {
    "announcer": "hf://kyutai/tts-voices/alba-mackenna/announcer.wav",
    "merchant": "hf://kyutai/tts-voices/alba-mackenna/merchant.wav",
    "casual": "hf://kyutai/tts-voices/alba-mackenna/casual.wav",
}

_model = None
_voice_state_cache: dict[str, object] = {}


def _get_model():
    global _model
    if _model is None:
        from pocket_tts import TTSModel

        _model = TTSModel.load_model()
    return _model


def _get_voice_state(voice_name: str):
    if voice_name not in _voice_state_cache:
        model = _get_model()
        source = VOICE_ALIASES.get(voice_name, voice_name)
        state = model.get_state_for_audio_prompt(source)
        if state is None:
            raise ValueError(f"pocket-tts voice '{voice_name}' failed to load from '{source}'")
        _voice_state_cache[voice_name] = state
    return _voice_state_cache[voice_name]


def list_available_voices() -> list[str]:
    """Curated voice names this provider knows shortcuts for.

    Unlike Piper, pocket-tts has no local "downloaded voices" folder to scan
    — any `hf://...` path or local WAV file also works as a voice_name even
    if it isn't in this list.
    """
    return sorted(set(BUILTIN_VOICES) | set(VOICE_ALIASES))


def speak(sentence: str, voice_name: str = DEFAULT_VOICE) -> Path:
    """Synthesize `sentence`, return the path to a temp WAV file the caller owns."""
    import numpy as np

    model = _get_model()
    voice_state = _get_voice_state(voice_name or DEFAULT_VOICE)

    audio = model.generate_audio(voice_state, sentence)  # [channels, samples] float
    samples = audio.numpy().astype(np.float32).flatten()
    pcm16 = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

    fd, path_str = tempfile.mkstemp(suffix=".wav", prefix="voice_gesture_kyutai_")
    path = Path(path_str)
    with wave.open(path_str, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(model.sample_rate)
        wav_file.writeframes(pcm16.tobytes())
    os.close(fd)

    return path


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or "Hello, I am Reachy Mini."
    out_path = speak(text, "announcer")
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
