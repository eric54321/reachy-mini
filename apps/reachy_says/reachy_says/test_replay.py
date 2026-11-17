"""Unit tests for replay-clip assembly — no camera, no reachy_mini import.

`FrameRingBuffer` and `build_clip()` are pure/hardware-free by design (see
replay.py's docstring), so these tests just use synthetic numpy frames and a
scratch temp file."""

import numpy as np
import pytest
from PIL import Image

from reachy_says.replay import (
    REPLAY_FRAME_DURATION_MS,
    REPLAY_MIN_CROP_RATIO,
    REPLAY_SLOWMO_REPEAT,
    FrameRingBuffer,
    _padded_bbox,
    build_clip,
)


def make_frame(value: int, shape=(60, 80, 3)) -> np.ndarray:
    return np.full(shape, value, dtype=np.uint8)


def total_gif_duration_ms(path) -> int:
    with Image.open(path) as gif:
        total = 0
        for i in range(gif.n_frames):
            gif.seek(i)
            total += gif.info.get("duration", 0)
        return total


class TestFrameRingBuffer:
    def test_snapshot_returns_frames_within_the_time_window(self):
        buf = FrameRingBuffer(max_age_seconds=100)
        buf.append(1.0, make_frame(1))
        buf.append(2.0, make_frame(2))
        buf.append(3.0, make_frame(3))

        snap = buf.snapshot(1.5, 3.0)
        assert [t for t, _ in snap] == [2.0, 3.0]

    def test_append_evicts_frames_older_than_max_age(self):
        buf = FrameRingBuffer(max_age_seconds=5.0)
        buf.append(0.0, make_frame(1))
        buf.append(10.0, make_frame(2))  # more than max_age later

        snap = buf.snapshot(0.0, 100.0)
        assert [t for t, _ in snap] == [10.0]

    def test_append_ignores_none_frames(self):
        buf = FrameRingBuffer()
        buf.append(1.0, None)
        assert buf.snapshot(0.0, 100.0) == []

    def test_clear_empties_the_buffer(self):
        buf = FrameRingBuffer()
        buf.append(1.0, make_frame(1))
        buf.clear()
        assert buf.snapshot(0.0, 100.0) == []


class TestPaddedBbox:
    def test_grows_a_tiny_box_up_to_the_minimum_crop_ratio(self):
        frame_shape = (200, 400)  # (height, width)
        tiny_box = (190, 95, 210, 105)  # a 20x10 patch near the center

        x0, y0, x1, y1 = _padded_bbox(tiny_box, frame_shape, padding_ratio=0.35)

        height, width = frame_shape
        assert (x1 - x0) >= width * REPLAY_MIN_CROP_RATIO - 1  # -1 for int rounding
        assert (y1 - y0) >= height * REPLAY_MIN_CROP_RATIO - 1

    def test_stays_within_frame_bounds_near_an_edge(self):
        frame_shape = (200, 400)
        corner_box = (0, 0, 10, 10)

        x0, y0, x1, y1 = _padded_bbox(corner_box, frame_shape, padding_ratio=0.35)

        assert 0 <= x0 < x1 <= frame_shape[1]
        assert 0 <= y0 < y1 <= frame_shape[0]

    def test_does_not_shrink_a_box_already_bigger_than_the_minimum(self):
        frame_shape = (200, 400)
        big_box = (20, 20, 380, 180)  # already most of the frame

        x0, y0, x1, y1 = _padded_bbox(big_box, frame_shape, padding_ratio=0.0)

        assert (x1 - x0) >= (380 - 20)
        assert (y1 - y0) >= (180 - 20)


class TestBuildClip:
    def test_raises_on_empty_frames(self, tmp_path):
        with pytest.raises(ValueError):
            build_clip([], bbox=None, caption="OOPS!", output_path=tmp_path / "clip.gif")

    def test_builds_a_valid_multi_frame_gif_with_a_bbox(self, tmp_path):
        # Distinct values per frame so slow-mo duplicates merge (same visual
        # content -> Pillow sums their duration) but the frames themselves
        # don't all collapse into one.
        frames = [(float(i), make_frame(100 + i)) for i in range(4)]
        output_path = tmp_path / "clip.gif"

        build_clip(frames, bbox=(10, 10, 40, 40), caption="BUSTED!", output_path=output_path)

        assert output_path.exists()
        with Image.open(output_path) as gif:
            assert 1 <= gif.n_frames <= len(frames) * REPLAY_SLOWMO_REPEAT
        # Total playback time reflects the slow-mo repeat even when Pillow
        # merges pixel-identical consecutive frames to shrink the file.
        assert total_gif_duration_ms(output_path) == len(frames) * REPLAY_SLOWMO_REPEAT * REPLAY_FRAME_DURATION_MS

    def test_builds_a_valid_gif_with_center_crop_fallback(self, tmp_path):
        frames = [(float(i), make_frame(50 + i)) for i in range(3)]
        output_path = tmp_path / "clip.gif"

        build_clip(frames, bbox=None, caption="NICE TRY!", output_path=output_path)

        assert output_path.exists()
        assert total_gif_duration_ms(output_path) == len(frames) * REPLAY_SLOWMO_REPEAT * REPLAY_FRAME_DURATION_MS
