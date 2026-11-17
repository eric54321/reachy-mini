"""Hear: record from Reachy's microphone and transcribe it locally (Phase 2).

    python scripts/hear.py              # push-to-talk: Enter to start, Enter to stop
    python scripts/hear.py --seconds 8  # fixed window, no keyboard needed

`listen(mini, ...)` is meant to be imported by the conversation loop (Phase 3).
Speech-to-text is faster-whisper running on this PC (free, offline, no key).

Notes from testing:
  * The robot mic is 16 kHz stereo, but both channels are identical (mono).
  * Speak clearly within ~30 cm; quiet or distant speech comes back empty.
  * Same rule as everything else: one controller at a time (see CLAUDE.md).

Settings (env or repo .env): REACHY_MINI_HOST, HEAR_MODEL (default base.en).
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SAMPLE_RATE = 16000
# Biases Whisper toward the robot's name ("Reachy" otherwise comes out "Richie").
PROMPT_HINT = (
    "Reachy, Reachy Mini. Act happy. Look left. Look right. Look up. Look down. "
    "Nod your head. Wiggle your antennas. Say hello. Goodbye."
)

_model = None


def get_model():
    """Load the Whisper model once (first load is a few seconds)."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            os.environ.get("HEAR_MODEL", "base.en"), device="cpu", compute_type="int8"
        )
    return _model


def _cue(mini, mm) -> None:
    """Tell the user 'speak now': a short beep and antennas up.

    Audio captured while the beep plays is thrown away so it isn't transcribed.
    """
    import tempfile
    import wave

    t = np.arange(int(22050 * 0.15)) / 22050
    tone = (0.5 * np.sin(2 * np.pi * 880 * t) * np.hanning(t.size) * 32767).astype(np.int16)
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="hear_beep_")
    os.close(fd)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(tone.tobytes())
    try:
        mini.goto_target(antennas=np.deg2rad([40, -40]), duration=0.25)
        mm.play_sound(path)
        # Discard only the beep itself (0.15 s + a little latency). A longer drain
        # cut off the first word of people who start talking right on the beep.
        end = time.time() + 0.28
        while time.time() < end:  # drain (discard) what the mic hears during the beep
            mm.get_audio_sample()
            time.sleep(0.01)
    finally:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


def record(mini, seconds: float | None = None, stop: threading.Event | None = None, cue: bool = True):
    """Capture mono float32 audio from the robot until `seconds` pass or `stop` is set.

    With cue=True the robot beeps and lifts its antennas the moment it starts
    listening, so you know when to talk.
    """
    mm = mini.media_manager
    mm.start_recording()
    time.sleep(0.3)  # let the stream warm up
    if cue:
        _cue(mini, mm)
    chunks, t0 = [], time.time()
    try:
        while True:
            if seconds is not None and time.time() - t0 >= seconds:
                break
            if stop is not None and stop.is_set():
                break
            s = mm.get_audio_sample()
            if s is not None and len(s):
                chunks.append(np.asarray(s, dtype=np.float32))
            else:
                time.sleep(0.01)
    finally:
        mm.stop_recording()
        if cue:  # antennas back down: done listening
            mini.goto_target(antennas=[0.0, 0.0], duration=0.25)
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    a = np.concatenate(chunks)
    return a.mean(axis=1) if a.ndim == 2 else a


def record_auto(
    mini,
    cue: bool = True,
    max_seconds: float = 15.0,
    silence_end: float = 1.0,
    no_speech_timeout: float = 6.0,
    threshold: float | None = None,
):
    """Record until the speaker stops: no Enter key needed.

    Waits up to `no_speech_timeout` for speech to begin, then stops after
    `silence_end` seconds of quiet (or `max_seconds`). The mic's auto-gain
    keeps levels roughly constant, so a fixed loudness threshold is used
    (HEAR_THRESHOLD env var, default 0.004 RMS; raise it in a noisy room).
    """
    if threshold is None:
        threshold = float(os.environ.get("HEAR_THRESHOLD", "0.004"))
    mm = mini.media_manager
    mm.start_recording()
    time.sleep(0.3)
    if cue:
        _cue(mini, mm)
    chunks, t0 = [], time.time()
    started, last_voice = False, 0.0
    try:
        while True:
            now = time.time()
            if now - t0 >= max_seconds:
                break
            if not started and now - t0 >= no_speech_timeout:
                break
            if started and now - last_voice >= silence_end:
                break
            s = mm.get_audio_sample()
            if s is None or not len(s):
                time.sleep(0.01)
                continue
            s = np.asarray(s, dtype=np.float32)
            chunks.append(s)
            if float(np.sqrt((s**2).mean())) > threshold:
                started, last_voice = True, now
    finally:
        mm.stop_recording()
        if cue:
            mini.goto_target(antennas=[0.0, 0.0], duration=0.25)
    if not chunks or not started:
        return np.zeros(0, dtype=np.float32)
    a = np.concatenate(chunks)
    return a.mean(axis=1) if a.ndim == 2 else a


def transcribe(audio: np.ndarray) -> str:
    """Normalize quiet audio and transcribe it. Returns '' if nothing was heard."""
    if audio.size < SAMPLE_RATE * 0.3:
        return ""
    peak = float(np.abs(audio).max())
    if peak < 0.01:  # essentially silence: skip, Whisper hallucinates on noise
        return ""
    audio = (audio / peak * 0.7).astype(np.float32)
    segments, _ = get_model().transcribe(
        audio, language="en", vad_filter=True, initial_prompt=PROMPT_HINT
    )
    return " ".join(s.text.strip() for s in segments).strip()


def listen(mini, seconds: float | None = None, auto: bool = False) -> str:
    """Record once and return the transcript.

    auto=True stops by itself when you stop talking; seconds=N uses a fixed
    window; otherwise push-to-talk (Enter to start, Enter to stop).
    """
    if auto:
        audio = record_auto(mini)
    elif seconds is None:
        input("Press Enter, then speak. Press Enter again when done... ")
        stop = threading.Event()
        threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()
        print("listening (wait for the beep)...")
        audio = record(mini, stop=stop)
    else:
        print(f"listening for {seconds:g}s after the beep...")
        audio = record(mini, seconds=seconds)
    t = time.perf_counter()
    text = transcribe(audio)
    print(f"[heard in {time.perf_counter() - t:.1f}s] {text!r}")
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, help="fixed recording window instead of push-to-talk")
    ap.add_argument("--auto", action="store_true", help="stop automatically when you stop talking")
    args = ap.parse_args()

    from reachy_mini import ReachyMini

    host = os.environ.get("REACHY_MINI_HOST", "192.168.50.216")
    get_model()  # warm up before the robot connection so first listen is fast
    try:
        mini_ctx = ReachyMini(host=host, connection_mode="network")
        mini = mini_ctx.__enter__()
    except Exception as e:
        sys.exit(f"Could not connect to Reachy at {host}: {e}")
    try:
        mini.enable_motors()  # the cue moves the antennas
        time.sleep(1.0)
        listen(mini, seconds=args.seconds, auto=args.auto)
    finally:
        mini_ctx.__exit__(None, None, None)


if __name__ == "__main__":
    main()
