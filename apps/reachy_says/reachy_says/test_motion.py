"""Unit tests for camera motion detection — no camera, no real sleeping.

`watch_for_motion` takes injectable `get_frame`/`sleep_fn` for exactly this
reason (see motion.py's docstring)."""

import numpy as np
import pytest

from reachy_says.motion import (
    _downsample_gray,
    motion_bounding_box,
    motion_ratio,
    watch_for_motion,
)


def make_frame(value: int, shape=(32, 32, 3)) -> np.ndarray:
    return np.full(shape, value, dtype=np.uint8)


def make_patch_frame(base: int, patch: int, box, shape=(32, 32, 3)) -> np.ndarray:
    """A uniform frame with a rectangular sub-region set to a different
    value — used to test localized (not full-frame) motion."""
    frame = make_frame(base, shape)
    x0, y0, x1, y1 = box
    frame[y0:y1, x0:x1, :] = patch
    return frame


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


def test_motion_bounding_box_is_none_for_identical_frames():
    gray = _downsample_gray(make_frame(100))
    assert motion_bounding_box(gray, gray) is None


def test_motion_bounding_box_is_the_whole_frame_for_a_global_change():
    before = _downsample_gray(make_frame(0))
    after = _downsample_gray(make_frame(255))
    height, width = before.shape
    assert motion_bounding_box(before, after) == (0, 0, width, height)


def test_motion_bounding_box_localizes_a_patch_of_change():
    # No downsampling here (stride=1) so the box lines up exactly with the
    # patch coordinates we drew.
    before = make_frame(100).mean(axis=2)
    after = make_patch_frame(100, 200, box=(4, 6, 10, 12)).mean(axis=2)
    assert motion_bounding_box(before, after) == (4, 6, 10, 12)


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


def test_watch_for_motion_calls_on_frame_for_every_frame_read():
    frames = [make_frame(100)] * 3
    it = iter(frames)
    seen = []

    watch_for_motion(
        lambda: next(it, None),
        duration_seconds=3.0,
        poll_hz=8,
        sleep_fn=FakeSleep(),
        on_frame=lambda t, f: seen.append(f),
    )

    assert len(seen) == 3


def test_watch_for_motion_reports_bbox_on_detection():
    # Patch covers a quarter of the 32x32 frame, comfortably past the
    # default 3% ratio_threshold.
    frames = [make_frame(100), make_patch_frame(100, 200, box=(4, 4, 20, 20))]
    it = iter(frames)
    detected_bbox = []

    result = watch_for_motion(
        lambda: next(it, None),
        duration_seconds=3.0,
        poll_hz=8,
        stride=1,
        sleep_fn=FakeSleep(),
        on_motion_detected=detected_bbox.append,
    )

    assert result is True
    assert detected_bbox == [(4, 4, 20, 20)]
