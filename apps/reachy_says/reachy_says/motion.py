"""Camera-based motion detection for trick rounds ("Tricked You" feature).

Aggregate/whole-frame frame-differencing — no per-person pose tracking or
identification, matching the design doc's scope. No `cv2` dependency: neither
of this repo's Python envs has OpenCV installed, and plain numpy is plenty
for a coarse "did the frame change a lot" signal.

`watch_for_motion()` is the only impure piece (it calls `get_frame` and
`sleep_fn` in a loop); `motion_ratio` and `_downsample_gray` are pure numpy
and unit-tested directly with synthetic arrays — see `test_motion.py`.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
import numpy.typing as npt

# Starting points, not a validated calibration — tune against the physical
# robot's camera (see reachy-says-trick-detection.md's sensitivity-tuning
# open question). pixel_threshold is a 0-255 intensity delta; ratio_threshold
# is the fraction of (downsampled) pixels that must cross it.
DEFAULT_PIXEL_THRESHOLD = 25
DEFAULT_RATIO_THRESHOLD = 0.03
DEFAULT_POLL_HZ = 8.0
DEFAULT_STRIDE = 4


def _downsample_gray(frame_bgr: npt.NDArray[np.uint8], stride: int = DEFAULT_STRIDE) -> npt.NDArray[np.float64]:
    """Grayscale + strided subsample.

    Cuts comparison cost and smooths out per-pixel sensor noise, which is
    what keeps small ambient movement (breathing, shifting weight) from
    registering as motion.
    """
    gray = frame_bgr.mean(axis=2)
    return gray[::stride, ::stride]


def motion_ratio(
    prev_gray: npt.NDArray[np.float64],
    curr_gray: npt.NDArray[np.float64],
    pixel_threshold: int = DEFAULT_PIXEL_THRESHOLD,
) -> float:
    """Fraction of sampled pixels whose intensity changed by more than `pixel_threshold`."""
    diff = np.abs(curr_gray.astype(np.int16) - prev_gray.astype(np.int16))
    return float(np.count_nonzero(diff > pixel_threshold)) / diff.size


def watch_for_motion(
    get_frame: Callable[[], npt.NDArray[np.uint8] | None],
    duration_seconds: float,
    *,
    poll_hz: float = DEFAULT_POLL_HZ,
    pixel_threshold: int = DEFAULT_PIXEL_THRESHOLD,
    ratio_threshold: float = DEFAULT_RATIO_THRESHOLD,
    is_active: Callable[[], bool] = lambda: True,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """Poll `get_frame()` for `duration_seconds`, watching for a motion spike.

    Returns True as soon as one frame-to-frame comparison crosses
    `ratio_threshold` (early exit). Returns False if the window elapses, or
    if `is_active()` goes False first — the caller uses that to cancel a
    watch once the round it belongs to is no longer WAITING.

    Runs a fixed number of polls (`duration_seconds * poll_hz`) rather than
    tracking wall-clock time, so it's fully deterministic under test with a
    no-op `sleep_fn` — no fake clock needed.

    A `None` frame (camera not ready/failed) just contributes no data for
    that poll rather than raising, so a camera that never comes up degrades
    silently to "no motion detected" — the trick round then falls back to
    the honor-system button confirm.
    """
    num_polls = max(1, round(duration_seconds * poll_hz))
    interval = 1.0 / poll_hz
    prev_gray: npt.NDArray[np.float64] | None = None

    for _ in range(num_polls):
        if not is_active():
            return False

        frame = get_frame()
        if frame is not None:
            curr_gray = _downsample_gray(frame)
            if prev_gray is not None and motion_ratio(prev_gray, curr_gray, pixel_threshold) >= ratio_threshold:
                return True
            prev_gray = curr_gray

        sleep_fn(interval)

    return False
