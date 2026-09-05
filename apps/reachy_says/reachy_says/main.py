import os
import threading
import time
import wave

import requests
from pydantic import BaseModel, Field
from reachy_mini import ReachyMini, ReachyMiniApp

from reachy_says.commands import Command
from reachy_says.game import (
    MAX_ROUNDS,
    MAX_TIMER_SECONDS,
    MIN_ROUNDS,
    MIN_TIMER_SECONDS,
    GameState,
    Status,
)
from reachy_says.gestures import GestureLibrary
from reachy_says.tts import DEFAULT_VOICE_ID, list_available_voices, speak

# Piper mispronounces "Reachy" (comes out sounding like "Reaky"); this
# respelling gets it right. Confirmed by ear against this app's actual
# voice — don't "fix" the spelling back without listening first.
REACHY_SPOKEN = "Reechy"

# Spoken once at the start of a game, before round 1.
INTRO_TEXT = f"Hello everyone, let's play {REACHY_SPOKEN} Says. Ready, set, go!"
INTRO_MOVE = "enthusiastic2"
INTRO_PAUSE_SECONDS = 0.5

# Reaction line + gesture for each way a round can resolve (see game.py).
RESULT_TEXT = {
    "success": "Nice one!",
    "survived_trick": "Whew, good catch!",
    "gotcha": "Gotcha! You moved!",
}
RESULT_MOVE = {
    "success": "success1",
    "survived_trick": "success2",
    "gotcha": "laughing1",
}


def _announce_text(command: Command, is_trick: bool) -> str:
    """The line Reachy speaks for a round — omits the "Reachy says" prefix
    on a trick round, per the game's classic rule."""
    if is_trick:
        return f"{command.phrase.capitalize()}!"
    return f"{REACHY_SPOKEN} says, {command.phrase}!"


def _wav_duration_seconds(path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def _speak_and_gesture(
    reachy_mini: ReachyMini,
    gestures: GestureLibrary,
    text: str,
    move_name: str,
    voice_id: str = DEFAULT_VOICE_ID,
) -> None:
    """Speak `text` while playing `move_name` concurrently, then wait for both to finish."""
    audio_path = speak(text, voice_id)
    gesture_thread = None
    try:
        reachy_mini.media_manager.play_sound(str(audio_path))
        gesture_thread = gestures.play(reachy_mini, move_name, sound=False, blocking=False)
        # media_manager.play_sound is fire-and-forget; wait out the clip's
        # own duration so lines don't overlap (see voice_gesture/main.py).
        time.sleep(_wav_duration_seconds(audio_path))
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except OSError:
            # Windows can still hold the file open briefly past our
            # duration-based sleep — it's a temp file either way.
            pass

    # A gesture often runs longer than its line's audio; wait for it so we
    # don't start the next thing (or disconnect) out from under it.
    if gesture_thread is not None:
        gesture_thread.join()


class ReachySays(ReachyMiniApp):
    # Optional: URL to a custom configuration page for the app
    custom_app_url: str | None = "http://0.0.0.0:8043"
    request_media_backend: str | None = None
    # Set by the /connection route below when the UI requests a physical/sim
    # switch; checked by __main__'s loop after wrapped_run() returns to
    # decide whether to reconnect (new mode) or exit for good.
    pending_mode: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        gestures = GestureLibrary()
        reachy_mini.enable_motors()  # no-op if already on; commands silently do nothing without it
        reachy_mini.wake_up()

        game = GameState()
        state_lock = threading.Lock()

        # Voice picker state: which voice the app speaks with. Starts on
        # whatever voice is actually downloaded, falling back to
        # DEFAULT_VOICE_ID if nothing's there yet (mirrors voice_gesture).
        available_voices = list_available_voices()
        current_voice_id = DEFAULT_VOICE_ID if DEFAULT_VOICE_ID in available_voices else (
            available_voices[0] if available_voices else DEFAULT_VOICE_ID
        )

        class ConfigRequest(BaseModel):
            timer_seconds: float = Field(..., ge=MIN_TIMER_SECONDS, le=MAX_TIMER_SECONDS)
            max_rounds: int = Field(..., ge=MIN_ROUNDS, le=MAX_ROUNDS)

        class VoiceRequest(BaseModel):
            voice_id: str

        class VolumeRequest(BaseModel):
            volume: int = Field(..., ge=0, le=100)

        class ConnectionRequest(BaseModel):
            mode: str  # "physical" | "sim"

        @self.settings_app.get("/state")
        def get_state():
            with state_lock:
                return game.to_public_dict()

        @self.settings_app.post("/start")
        def start_game():
            with state_lock:
                if game.status not in (Status.IDLE, Status.GAME_OVER):
                    return {"error": f"Cannot start from status '{game.status.value}'"}
                game.start()
                return game.to_public_dict()

        @self.settings_app.post("/reset")
        def reset_game():
            with state_lock:
                game.reset()
                return game.to_public_dict()

        @self.settings_app.post("/confirm")
        def confirm_action():
            with state_lock:
                game.confirm()
                return game.to_public_dict()

        @self.settings_app.post("/config")
        def set_config(req: ConfigRequest):
            with state_lock:
                if game.status not in (Status.IDLE, Status.GAME_OVER):
                    return {"error": f"Cannot change the timer during status '{game.status.value}'"}
                game.configure(req.timer_seconds, req.max_rounds)
                return game.to_public_dict()

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

        @self.settings_app.get("/connection")
        def get_connection():
            return {"mode": os.environ.get("REACHY_MINI_MODE", "physical")}

        @self.settings_app.post("/connection")
        def set_connection(req: ConnectionRequest):
            if req.mode not in ("physical", "sim"):
                return {"error": f"Unknown mode '{req.mode}', expected 'physical' or 'sim'"}
            current_mode = os.environ.get("REACHY_MINI_MODE", "physical")
            if req.mode == current_mode:
                return {"mode": current_mode, "restarting": False}
            # There's no way to swap the live ReachyMini connection under
            # wrapped_run() (it's opened once and held for the app's whole
            # lifetime), so switching modes means: stop this run cleanly
            # (goto_sleep, disconnect), let wrapped_run() return, and have
            # __main__'s loop reconnect with the new mode using a fresh
            # ReachySays instance (see the bottom of this file).
            self.pending_mode = req.mode
            self.stop()
            return {"mode": req.mode, "restarting": True}

        # Main control loop: advances the game state machine and performs
        # its speak+gesture side effects (see game.py's tick() docstring for
        # the event protocol).
        while not stop_event.is_set():
            with state_lock:
                status = game.status
                command = game.current_command
                is_trick = game.is_trick
                voice_id = current_voice_id

            try:
                if status == Status.INTRO:
                    _speak_and_gesture(reachy_mini, gestures, INTRO_TEXT, INTRO_MOVE, voice_id)
                    time.sleep(INTRO_PAUSE_SECONDS)
                    with state_lock:
                        if game.status == Status.INTRO:
                            # Guard against a /reset that landed while we
                            # were mid-greeting (blocking on TTS/gesture).
                            game.begin_first_round()
                elif status == Status.ANNOUNCING:
                    _speak_and_gesture(
                        reachy_mini, gestures, _announce_text(command, is_trick), command.move_name, voice_id
                    )
                    with state_lock:
                        if game.status == Status.ANNOUNCING:
                            # Guard against a /reset that landed while we
                            # were mid-announce (blocking on TTS/gesture).
                            game.begin_waiting()
                else:
                    with state_lock:
                        event = game.tick()
                        last_result = game.last_result
                        score = game.score

                    if event == "result":
                        text = RESULT_TEXT.get(last_result, "")
                        move = RESULT_MOVE.get(last_result, "attentive1")
                        if text:
                            _speak_and_gesture(reachy_mini, gestures, text, move, voice_id)
                    elif event == "game_over":
                        if last_result == "gotcha":
                            text = f"Game over! You made it through {score} round{'s' if score != 1 else ''}."
                            move = "welcoming1"
                        else:
                            text = f"You did it! You survived all {score} rounds. Great job!"
                            move = "cheerful1"
                        _speak_and_gesture(reachy_mini, gestures, text, move, voice_id)
            except Exception:
                # A transient TTS/robot hiccup shouldn't take the whole app
                # down. Reset to IDLE (rather than leaving a half-finished
                # round) and stay alive for the next /start.
                self.logger.exception("Game loop step failed at status=%r", status)
                with state_lock:
                    game.reset()

            time.sleep(0.05)

        reachy_mini.goto_sleep()


def _connection_kwargs() -> dict:
    """Physical robot vs. simulator, from .env (see .env.example).

    Copied from voice_gesture/main.py: mDNS ("reachy-mini.local") doesn't
    resolve on this network, so both branches connect by IP/host + port
    explicitly rather than relying on ReachyMiniApp.wrapped_run()'s own
    localhost auto-detect (which only ever checks port 8000 — blocked on
    this machine, so a sim daemon has to run on an alternate port anyway).
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


def _make_app() -> ReachySays:
    """Build a fresh ReachySays configured for whatever REACHY_MINI_MODE is
    currently set. Used both for the initial launch and for every
    physical/sim reconnect (see the loop below) — a *fresh* instance each
    time is what avoids double-registering routes on a stale settings_app.
    """
    if os.environ.get("REACHY_MINI_MODE", "physical") == "sim":
        # wrapped_run() always passes media_backend itself, so it can't be
        # overridden via connection_kwargs. Force the LOCAL backend for a
        # same-machine sim daemon (see voice_gesture/main.py for the full
        # explanation of why the WEBRTC auto-detect fails here).
        ReachySays.request_media_backend = "local"
    else:
        ReachySays.request_media_backend = None

    app = ReachySays()

    if os.environ.get("REACHY_MINI_MODE", "physical") == "physical":
        # ReachyMiniApp.__init__ decides connection_mode itself by probing
        # whether *anything* accepts a TCP connect on localhost:8000 — on
        # this dev machine that port is sometimes held by an unrelated
        # Windows service (see SETUP.md), which false-positives the check
        # and forces "localhost_only", silently ignoring our host kwarg
        # below. There's no public hook for this (unlike request_media_
        # backend above), so override the instance attribute directly.
        app.daemon_on_localhost = False

    return app


if __name__ == "__main__":
    # Runs wrapped_run() repeatedly rather than once: a /connection request
    # (see the route above) sets pending_mode and calls stop(), which makes
    # wrapped_run() return normally (robot disconnected, settings_app torn
    # down). We then flip REACHY_MINI_MODE and go again with a brand-new
    # ReachySays — same port, same terminal, no wrapper script needed. A
    # real Ctrl+C (KeyboardInterrupt) or a run that never asked to switch
    # modes just exits the loop.
    while True:
        # _connection_kwargs() calls load_dotenv(), which is also what puts
        # REACHY_MINI_MODE into os.environ on first launch (it only lives in
        # .env until then). _make_app() reads that same var to decide the
        # media backend, so it must run *after* this — otherwise the first
        # loop iteration silently misses the sim media-backend override
        # below and falls through to the fragile WEBRTC audio path instead.
        connection_kwargs = _connection_kwargs()
        app = _make_app()
        try:
            app.wrapped_run(**connection_kwargs)
        except KeyboardInterrupt:
            app.stop()
            break

        if app.pending_mode is None:
            break
        os.environ["REACHY_MINI_MODE"] = app.pending_mode
