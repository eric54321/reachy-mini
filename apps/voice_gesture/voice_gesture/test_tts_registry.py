"""Tests for the provider registry/dispatch in tts/__init__.py.

Uses a fake provider instead of the real Piper/pocket-tts backends, so these
run without downloaded voice models, torch, or network access.
Run with: pytest test_tts_registry.py
"""

from pathlib import Path

import pytest

from voice_gesture import tts


class FakeProvider:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def list_available_voices(self) -> list[str]:
        return ["one", "two"]

    def speak(self, sentence: str, voice_name: str) -> Path:
        self.calls.append((sentence, voice_name))
        return Path(f"/tmp/{voice_name}.wav")


@pytest.fixture
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setitem(tts._PROVIDERS, "fake", provider)
    return provider


def test_list_available_voices_namespaces_by_provider(fake_provider):
    voices = tts.list_available_voices()
    assert "fake:one" in voices
    assert "fake:two" in voices
    assert voices == sorted(voices)


def test_speak_dispatches_to_the_right_provider(fake_provider):
    path = tts.speak("hello", "fake:one")
    assert path == Path("/tmp/one.wav")
    assert fake_provider.calls == [("hello", "one")]


def test_speak_rejects_an_unknown_provider_prefix():
    with pytest.raises(ValueError, match="Unknown voice_id"):
        tts.speak("hello", "not-a-real-provider:whatever")


def test_speak_rejects_a_voice_id_with_no_provider_prefix():
    with pytest.raises(ValueError, match="Unknown voice_id"):
        tts.speak("hello", "no-colon-here")
