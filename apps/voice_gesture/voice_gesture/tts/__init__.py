"""TTS provider registry.

Every provider module exposes `speak(sentence, voice_name) -> Path` and
`list_available_voices() -> list[str]` (see `tts.base.TTSProvider`). This
`__init__` is the only place that knows about specific providers — the rest
of the app only ever imports from `voice_gesture.tts`.

`voice_id` strings are namespaced as `"<provider>:<voice_name>"`, e.g.
`"piper:en_US-lessac-medium"` or `"kyutai:announcer"`, so callers (the
picker UI, the `/say` endpoint) never need to know which provider is behind
a given voice.

To reuse this package in another app: copy the `tts/` folder wholesale (it
has no dependency on anything else in `voice_gesture`), keep the providers
you want in `_PROVIDERS` below and drop the ones you don't — each provider's
heavy dependencies (e.g. `torch` for pocket-tts) are only imported lazily
inside that provider's own `speak()`, so an unregistered provider's
dependencies don't even need to be installed.
"""

from __future__ import annotations

from pathlib import Path

from voice_gesture.tts import piper_provider, pocket_tts_provider

_PROVIDERS = {
    "piper": piper_provider,
    "kyutai": pocket_tts_provider,
}

DEFAULT_VOICE_ID = f"piper:{piper_provider.DEFAULT_VOICE}"


def list_available_voices() -> list[str]:
    """All usable `"<provider>:<voice_name>"` ids across every registered provider."""
    return sorted(
        f"{prefix}:{voice_name}"
        for prefix, provider in _PROVIDERS.items()
        for voice_name in provider.list_available_voices()
    )


def speak(sentence: str, voice_id: str = DEFAULT_VOICE_ID) -> Path:
    """Synthesize `sentence` with the given `"<provider>:<voice_name>"` id.

    Returns the path to a temp WAV file; the caller is responsible for
    playing it (e.g. via `reachy_mini.media_manager.play_sound(path)`) and
    may delete it afterwards.
    """
    prefix, sep, voice_name = voice_id.partition(":")
    provider = _PROVIDERS.get(prefix) if sep else None
    if provider is None:
        raise ValueError(
            f"Unknown voice_id '{voice_id}' — expected '<provider>:<voice_name>', "
            f"provider must be one of: {', '.join(_PROVIDERS)}"
        )
    return provider.speak(sentence, voice_name)
