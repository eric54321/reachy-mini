"""Exercise the /voices, /voice, /say settings endpoints with a fake robot
(no hardware needed) — run() registers the routes on self.settings_app before
entering its control loop, so we can hit them via FastAPI's TestClient
directly. Run with: pytest test_picker_endpoints.py
"""

import threading
import time

from fastapi.testclient import TestClient

from voice_gesture.main import VoiceGesture
from voice_gesture.tts import list_available_voices


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
    app = VoiceGesture()
    stop_event = threading.Event()
    t = threading.Thread(target=app.run, args=(FakeReachyMini(), stop_event), daemon=True)
    t.start()
    time.sleep(1.0)  # let run() register routes before we hit them
    return app, stop_event, t


def test_voices_endpoint_lists_downloaded_voices():
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


def test_say_endpoint_queues_with_current_voice_by_default():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        current = client.get("/voices").json()["current"]

        resp = client.post("/say", json={"text": "[happy] Hi!"})
        assert resp.json() == {"queued": "[happy] Hi!", "voice_id": current}
    finally:
        stop_event.set()
        t.join(timeout=2)


def test_emotions_endpoint_lists_known_tags():
    app, stop_event, t = make_running_app()
    try:
        client = TestClient(app.settings_app)
        resp = client.get("/emotions")
        assert resp.status_code == 200
        emotions = resp.json()["emotions"]
        assert "happy" in emotions
        assert "sad" in emotions
        assert emotions == sorted(emotions)
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
