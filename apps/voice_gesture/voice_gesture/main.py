import os
import threading
import time

import requests
from pydantic import BaseModel, Field
from reachy_mini import ReachyMini, ReachyMiniApp

from voice_gesture.emotion_to_gesture import GestureLibrary, list_emotions
from voice_gesture.tts import DEFAULT_VOICE_ID, list_available_voices, speak
from voice_gesture.split_message import split_message


def say(reachy_mini: ReachyMini, gestures: GestureLibrary, text: str, voice_id: str = DEFAULT_VOICE_ID) -> None:
    """Run one message through the full pipeline: split -> speak -> gesture.

    For each sentence, in order:
      - synthesize its audio (TTS)
      - start playing it
      - fire the matching gesture at the same time (non-blocking, so it runs
        concurrently with the audio)
      - wait for the audio to finish before moving to the next sentence
    """
    gesture_thread = None
    for segment in split_message(text):
        audio_path = speak(segment.sentence, voice_id)
        try:
            reachy_mini.media_manager.play_sound(str(audio_path))
            gesture_thread = gestures.play(reachy_mini, segment.emotion, sound=False, blocking=False)
            # media_manager.play_sound is fire-and-forget; wait out the clip's
            # own duration so sentences don't overlap. Piper WAVs are 22.05kHz
            # mono 16-bit, so duration = frames / sample_rate.
            duration = _wav_duration_seconds(audio_path)
            time.sleep(duration)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                # Windows can still hold the file open briefly (e.g. the
                # LOCAL/GStreamer backend reading it for playback) even after
                # our duration-based sleep. It's a temp file either way — not
                # worth failing the whole message over.
                pass

    # A gesture often runs longer than its sentence's audio. Wait for the
    # last one to finish before returning, so callers don't disconnect (or
    # start another gesture) out from under a still-running move.
    if gesture_thread is not None:
        gesture_thread.join()


def _wav_duration_seconds(path) -> float:
    import wave

    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


class VoiceGesture(ReachyMiniApp):
    # Optional: URL to a custom configuration page for the app
    custom_app_url: str | None = "http://0.0.0.0:8042"
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        gestures = GestureLibrary()
        reachy_mini.enable_motors()  # no-op if already on; commands silently do nothing without it
        reachy_mini.wake_up()

        # Voice picker state: which voice /say uses when a request doesn't
        # name one explicitly. Starts on whatever voice is actually
        # downloaded, falling back to DEFAULT_VOICE_ID if nothing's there yet.
        available_voices = list_available_voices()
        current_voice_id = DEFAULT_VOICE_ID if DEFAULT_VOICE_ID in available_voices else (
            available_voices[0] if available_voices else DEFAULT_VOICE_ID
        )

        say_requested: tuple[str, str] | None = None
        state_lock = threading.Lock()

        class SayRequest(BaseModel):
            text: str
            voice_id: str | None = None  # None = use the currently picked voice

        class VoiceRequest(BaseModel):
            voice_id: str

        class VolumeRequest(BaseModel):
            volume: int = Field(..., ge=0, le=100)

        @self.settings_app.get("/emotions")
        def get_emotions():
            return {"emotions": list_emotions()}

        @self.settings_app.get("/volume")
        def get_volume():
            # Speaker volume is a robot/OS-level setting served by the
            # daemon's own HTTP API, not the reachy_mini SDK client.
            try:
                resp = requests.get(f"{reachy_mini._daemon_http_url}/api/volume/current", timeout=5)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": f"Failed to read volume: {e}"}

        @self.settings_app.post("/volume")
        def set_volume(req: VolumeRequest):
            try:
                resp = requests.post(
                    f"{reachy_mini._daemon_http_url}/api/volume/set",
                    json={"volume": req.volume},
                    timeout=5,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": f"Failed to set volume: {e}"}

        @self.settings_app.get("/voices")
        def get_voices():
            return {"voices": list_available_voices(), "current": current_voice_id}

        @self.settings_app.post("/voice")
        def set_voice(req: VoiceRequest):
            nonlocal current_voice_id
            if req.voice_id not in list_available_voices():
                return {"error": f"Unknown voice '{req.voice_id}'", "current": current_voice_id}
            with state_lock:
                current_voice_id = req.voice_id
            return {"current": current_voice_id}

        @self.settings_app.post("/say")
        def request_say(req: SayRequest):
            nonlocal say_requested
            with state_lock:
                voice_id = req.voice_id or current_voice_id
                say_requested = (req.text, voice_id)
            return {"queued": req.text, "voice_id": voice_id}

        # Main control loop: idle, waiting for a /say request.
        while not stop_event.is_set():
            with state_lock:
                pending = say_requested
                say_requested = None

            if pending:
                text, voice_id = pending
                try:
                    say(reachy_mini, gestures, text, voice_id)
                except Exception:
                    # A network hiccup or a transient robot/daemon error
                    # shouldn't take the whole app down — log it and stay
                    # alive for the next /say request.
                    self.logger.exception("say() failed for text=%r voice_id=%r", text, voice_id)

            time.sleep(0.05)

        reachy_mini.goto_sleep()


def _connection_kwargs() -> dict:
    """Physical robot vs. simulator, from .env (see .env.example).

    mDNS ("reachy-mini.local") doesn't resolve on this network, so both
    branches connect by IP/host + port explicitly rather than relying on
    ReachyMiniApp.wrapped_run()'s own localhost auto-detect (which only ever
    checks port 8000 — no good here since port 8000 is blocked on this
    machine, so a sim daemon has to run on an alternate port anyway).
    """
    from dotenv import load_dotenv

    load_dotenv()
    mode = os.environ.get("REACHY_MINI_MODE", "physical")

    if mode == "sim":
        return {
            "host": os.environ.get("REACHY_MINI_SIM_HOST", "localhost"),
            "port": int(os.environ.get("REACHY_MINI_SIM_PORT", "8090")),
        }
    return {"host": os.environ.get("REACHY_MINI_HOST", "192.168.50.216")}


if __name__ == "__main__":
    connection_kwargs = _connection_kwargs()

    if os.environ.get("REACHY_MINI_MODE", "physical") == "sim":
        # wrapped_run() always passes media_backend itself (from
        # request_media_backend, read in ReachyMiniApp.__init__), so it can't
        # be overridden via connection_kwargs without a duplicate-keyword
        # error. Sim runs on this same machine, so force the LOCAL backend
        # (GStreamer IPC) here instead of the WEBRTC backend wrapped_run
        # would otherwise pick — its own "am I local?" check only ever looks
        # at port 8000, which is blocked on this machine (see SETUP.md), so
        # it always assumes "remote" for our sim daemon's alternate port.
        VoiceGesture.request_media_backend = "local"

    app = VoiceGesture()
    try:
        app.wrapped_run(**connection_kwargs)
    except KeyboardInterrupt:
        app.stop()
