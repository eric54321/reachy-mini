"""Unit tests for camera motion detection — no camera, no real sleeping.

`watch_for_motion` takes injectable `get_frame`/`sleep_fn` for exactly this
reason (see motion.py's docstring)."""

import numpy as np
import pytest

from reachy_says.motion import _downsample_gray, motion_ratio, watch_for_motion


def make_frame(value: int, shape=(32, 32, 3)) -> np.ndarray:
    return np.full(shape, value, dtype=np.uint8)


def test_motion_ratio_is_zero_for_identical_frames():
    gray = _downsample_gray(make_frame(100))
    assert motion_ratio(gray, gray) == 0.0


def test_motion_ratio_is_high_for_a_large_change():
    before = _downsample_gray(make_frame(0))
    after = _downsample_gray(make_frame(255))
    assert motion_ratio(before, after) == pytest.approx(1.0)


def test_motion_ratio_ignores_small_deltas_under_threshold():
    before = _downsample_gray(make_frame(100))
    after = _downsample_gray(make_frame(105))  # small ambient flicker
    assert motion_ratio(before, after, pixel_threshold=25) == 0.0


class FakeSleep:
    def __init__(self):
        self.calls = 0

    def __call__(self, seconds: float) -> None:
        self.calls += 1


def test_watch_for_motion_detects_a_spike_and_exits_early():
    frames = [make_frame(100)] * 3 + [make_frame(255)] + [make_frame(100)] * 20
    it = iter(frames)
    sleep_fn = FakeSleep()

    result = watch_for_motion(
        lambda: next(it, None),
        duration_seconds=3.0,
        poll_hz=8,
        sleep_fn=sleep_fn,
    )

    assert result is True
    # Should have stopped well before exhausting the full window (24 polls).
    assert sleep_fn.calls < 24


def test_watch_for_motion_returns_false_when_nothing_changes():
    sleep_fn = FakeSleep()

    result = watch_for_motion(
        lambda: make_frame(100),
        duration_seconds=1.0,
        poll_hz=8,
        sleep_fn=sleep_fn,
    )

    assert result is False
    assert sleep_fn.calls == 8


def test_watch_for_motion_stops_early_when_inactive():
    call_count = {"n": 0}

    def is_active():
        call_count["n"] += 1
        return call_count["n"] <= 2

    sleep_fn = FakeSleep()
    result = watch_for_motion(
        lambda: make_frame(100),
        duration_seconds=3.0,
        poll_hz=8,
        is_active=is_active,
        sleep_fn=sleep_fn,
    )

    assert result is False
    assert sleep_fn.calls == 2


def test_watch_for_motion_tolerates_missing_frames():
    sleep_fn = FakeSleep()

    result = watch_for_motion(
        lambda: None,
        duration_seconds=0.5,
        poll_hz=8,
        sleep_fn=sleep_fn,
    )

    assert result is False
    assert sleep_fn.calls == 4
