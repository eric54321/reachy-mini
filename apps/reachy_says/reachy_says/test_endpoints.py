"""Exercise /state, /start, /confirm, /reset, /config with a fake robot (no
hardware needed) — run() registers the routes on self.settings_app before
entering its control loop, so we can hit them via FastAPI's TestClient
directly, mirroring voice_gesture/test_picker_endpoints.py. Real Piper TTS
still runs (it's fast and needs no hardware); only the robot side is faked.
Run with: pytest test_endpoints.py
"""

import threading
import time

from fastapi.testclient import TestClient

from reachy_says.main import ReachySays


class FakeMediaManager:
    def play_sound(self, path):
        pass


class FakeReachyMini:
    def __init__(self):
        self.media_manager = FakeMediaManager()
        self._daemon_http_url = "http://fake-daemon:8000"

    def enable_motors(self):
        pass

    def wake_up(self):
        pass

    def goto_sleep(self):
        pass

    def play_move(self, move, sound=False):
        pass


def make_running_app():
    app = ReachySays()
    # Use app.stop_event itself (not an independent Event) — this is what
    # wrapped_run() actually passes to run() in production, and it's what
    # self.stop() (called by the /connection route on a mode switch) sets.
    stop_event = app.stop_event
    t = threading.Thread(target=app.run, args=(FakeReachyMini(), stop_event), daemon=True)
    t.start()
    time.sleep(1.0)  # let run() register routes before we hit them
    return app, stop_event, t


def wait_for_status(client, status, timeout=15.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = client.get("/state").json()
        if last["status"] == status:
            return last
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for status={status!r}, last state={last}")


def test_state_starts_idle():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        resp = client.get("/state")
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_config_is_rejected_out_of_range():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        resp = client.post("/config", json={"timer_seconds": 1.0, "max_rounds": 5})
        assert resp.status_code == 422

        resp = client.post("/config", json={"timer_seconds": 3.0, "max_rounds": 0})
        assert resp.status_code == 422
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_start_confirm_advances_to_the_next_round():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        config_resp = client.post("/config", json={"timer_seconds": 3.0, "max_rounds": 7})
        assert config_resp.json().get("error") is None
        assert client.post("/start").json().get("error") is None

        state = wait_for_status(client, "waiting")
        assert state["round_number"] == 1
        assert state["max_rounds"] == 7

        assert client.post("/confirm").status_code == 200

        # Round 1 is never a trick, so confirming succeeds and the game
        # moves straight on to round 2.
        state = wait_for_status(client, "announcing")
        assert state["round_number"] == 2
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_reset_returns_to_idle_mid_game():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        client.post("/config", json={"timer_seconds": 3.0, "max_rounds": 5})
        client.post("/start")
        wait_for_status(client, "waiting")

        resp = client.post("/reset")
        assert resp.json()["status"] == "idle"
        assert client.get("/state").json()["status"] == "idle"
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_cannot_start_while_a_game_is_already_running():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        client.post("/config", json={"timer_seconds": 3.0, "max_rounds": 5})
        client.post("/start")
        wait_for_status(client, "waiting")

        resp = client.post("/start")
        assert "error" in resp.json()
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_cannot_change_timer_mid_game():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        client.post("/config", json={"timer_seconds": 3.0, "max_rounds": 5})
        client.post("/start")
        wait_for_status(client, "waiting")

        resp = client.post("/config", json={"timer_seconds": 5.0, "max_rounds": 5})
        assert "error" in resp.json()
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_voices_endpoint_lists_downloaded_voices():
    from reachy_says.tts import list_available_voices

    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        resp = client.get("/voices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["voices"] == list_available_voices()
        assert data["current"] in data["voices"]
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_set_voice_updates_current_and_rejects_unknown():
    from reachy_says.tts import list_available_voices

    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        voices = list_available_voices()
        other_voice = next(v for v in voices if v != client.get("/voices").json()["current"])

        resp = client.post("/voice", json={"voice_id": other_voice})
        assert resp.json()["current"] == other_voice
        assert client.get("/voices").json()["current"] == other_voice

        resp = client.post("/voice", json={"voice_id": "not-a-real-voice"})
        assert "error" in resp.json()
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_volume_endpoints_degrade_gracefully_without_a_real_daemon():
    # FakeReachyMini points at a non-existent daemon URL, so these should
    # fail to reach it and report an error rather than crashing the app.
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        get_resp = client.get("/volume")
        assert "error" in get_resp.json()

        set_resp = client.post("/volume", json={"volume": 50})
        assert "error" in set_resp.json()

        # Out-of-range volume is rejected before any network call.
        bad_resp = client.post("/volume", json={"volume": 150})
        assert bad_resp.status_code == 422
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_connection_endpoint_reports_current_mode_and_rejects_bad_ones(monkeypatch):
    monkeypatch.setenv("REACHY_MINI_MODE", "sim")
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        assert client.get("/connection").json() == {"mode": "sim"}

        # Same mode: acknowledged, no restart triggered.
        resp = client.post("/connection", json={"mode": "sim"})
        assert resp.json() == {"mode": "sim", "restarting": False}
        assert app.pending_mode is None

        resp = client.post("/connection", json={"mode": "not-a-mode"})
        assert "error" in resp.json()
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_connection_endpoint_switching_mode_stops_the_run_loop(monkeypatch):
    # A real mode switch calls self.stop() (see main.py's /connection route)
    # rather than reconnecting in place — that reconnect is __main__'s job,
    # outside of run(). Here we only verify run()'s side: it requests the
    # switch and cleanly exits.
    monkeypatch.setenv("REACHY_MINI_MODE", "sim")
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        resp = client.post("/connection", json={"mode": "physical"})
        assert resp.json() == {"mode": "physical", "restarting": True}
        assert app.pending_mode == "physical"

        t.join(timeout=2)
        assert not t.is_alive()
    finally:
        stop_event.set()
        t.join(timeout=2)
