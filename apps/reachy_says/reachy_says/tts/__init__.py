"""TTS provider registry.

Forked from `apps/voice_gesture/voice_gesture/tts/` (that package's own
docstring explicitly designs it for this — "copy the `tts/` folder wholesale,
keep the providers you want"). Only the Piper provider is registered here
(no pocket-tts/Kyutai) — Piper's own voice catalog already covers what this
app's picker needs without the extra `torch` dependency.

`voice_id` strings stay namespaced as `"<provider>:<voice_name>"` (e.g.
`"piper:en_GB-alan-medium"`) for consistency with the source package, even
though only one provider is registered.
"""

from __future__ import annotations

from pathlib import Path

from reachy_says.tts import piper_provider

_PROVIDERS = {
    "piper": piper_provider,
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
