"""Replay-clip assembly for a camera-confirmed "gotcha" (config-gated
`enable_replay_clip` feature — see main.py).

`FrameRingBuffer` is the dashcam-style rolling buffer main.py feeds
continuously while a game is active; `build_clip()` turns a snapshot of it
into a captioned, zoomed-in, slow-motion animated GIF for the browser UI to
show. Both are pure/hardware-free — no camera, no reachy_mini import here —
so they're unit-testable with synthetic numpy frames (see test_replay.py).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Sequence

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFont

REPLAY_BUFFER_SECONDS = 8.0
REPLAY_PRE_ROLL_SECONDS = 2.5
REPLAY_POST_ROLL_SECONDS = 1.0
REPLAY_POLL_HZ = 8.0
REPLAY_ZOOM_PADDING_RATIO = 0.35
# A tightly-detected motion box (e.g. just a hand) stretched up to
# REPLAY_OUTPUT_SIZE would need extreme digital magnification and look
# soft/blurry — capping how small the crop can get keeps the zoom real
# camera detail can actually support. 0.5 means never crop tighter than
# half the frame's width/height.
REPLAY_MIN_CROP_RATIO = 0.5
REPLAY_OUTPUT_SIZE = (480, 360)
REPLAY_SLOWMO_REPEAT = 2
REPLAY_FRAME_DURATION_MS = 150
REPLAY_FLASH_FRAMES = 2

REPLAY_CAPTIONS = ["OOPS!", "BUSTED!", "CAUGHT RED-HANDED!", "NICE TRY!"]

Frame = npt.NDArray[np.uint8]
BBox = tuple[int, int, int, int]  # (x0, y0, x1, y1)


class FrameRingBuffer:
    """Thread-safe rolling buffer of (timestamp, frame), dashcam-style.

    Separate from main.py's game state_lock on purpose — this is plain data,
    not game logic, and gets touched from more than one thread (the
    continuous capture loop and the trick-round motion watcher both append
    to it; main.py's game loop reads a snapshot from it).
    """

    def __init__(self, max_age_seconds: float = REPLAY_BUFFER_SECONDS):
        self._max_age = max_age_seconds
        self._lock = threading.Lock()
        self._frames: list[tuple[float, Frame]] = []

    def append(self, timestamp: float, frame: Frame | None) -> None:
        if frame is None:
            return
        with self._lock:
            self._frames.append((timestamp, frame))
            cutoff = timestamp - self._max_age
            while self._frames and self._frames[0][0] < cutoff:
                self._frames.pop(0)

    def snapshot(self, start_time: float, end_time: float) -> list[tuple[float, Frame]]:
        with self._lock:
            return [(t, f) for t, f in self._frames if start_time <= t <= end_time]

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()


def _padded_bbox(bbox: BBox, frame_shape: tuple[int, int], padding_ratio: float) -> BBox:
    height, width = frame_shape
    x0, y0, x1, y1 = bbox
    pad_x = max(1, int((x1 - x0) * padding_ratio))
    pad_y = max(1, int((y1 - y0) * padding_ratio))
    x0, y0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
    x1, y1 = min(width, x1 + pad_x), min(height, y1 + pad_y)
    return _enforce_min_crop_size((x0, y0, x1, y1), frame_shape)


def _enforce_min_crop_size(bbox: BBox, frame_shape: tuple[int, int]) -> BBox:
    """Grow `bbox` (keeping its center) up to REPLAY_MIN_CROP_RATIO of the
    frame's width/height, so a tiny motion region doesn't force an
    unreadably blurry digital zoom. Clamped to the frame's own bounds."""
    height, width = frame_shape
    x0, y0, x1, y1 = bbox
    min_w, min_h = width * REPLAY_MIN_CROP_RATIO, height * REPLAY_MIN_CROP_RATIO
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    box_w, box_h = max(x1 - x0, min_w), max(y1 - y0, min_h)
    x0, x1 = cx - box_w / 2, cx + box_w / 2
    y0, y1 = cy - box_h / 2, cy + box_h / 2

    # Slide back into frame bounds rather than clipping, so the box keeps
    # its full (enforced) size instead of shrinking again at an edge.
    if x0 < 0:
        x1 -= x0
        x0 = 0
    if x1 > width:
        x0 -= x1 - width
        x1 = width
    if y0 < 0:
        y1 -= y0
        y0 = 0
    if y1 > height:
        y0 -= y1 - height
        y1 = height

    return (int(max(0, x0)), int(max(0, y0)), int(min(width, x1)), int(min(height, y1)))


def _center_bbox(frame_shape: tuple[int, int]) -> BBox:
    """Fallback crop when there's no real motion location (e.g. a bluff
    joke-replay) — the middle 60% of the frame."""
    height, width = frame_shape
    margin_x, margin_y = int(width * 0.2), int(height * 0.2)
    return (margin_x, margin_y, width - margin_x, height - margin_y)


def _caption_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Older Pillow: load_default() takes no size argument.
        return ImageFont.load_default()


def _render_frame(frame_bgr: Frame, bbox: BBox, caption: str, flash: bool) -> Image.Image:
    x0, y0, x1, y1 = bbox
    cropped = frame_bgr[y0:y1, x0:x1, ::-1]  # BGR -> RGB for Pillow
    # LANCZOS reads noticeably sharper than the resize default when
    # upscaling a small crop this much — see REPLAY_MIN_CROP_RATIO above
    # for the other half of keeping this readable.
    image = Image.fromarray(cropped).convert("RGB").resize(REPLAY_OUTPUT_SIZE, Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(image)
    if flash:
        border = 10
        draw.rectangle(
            [0, 0, REPLAY_OUTPUT_SIZE[0] - 1, REPLAY_OUTPUT_SIZE[1] - 1],
            outline=(255, 230, 0),
            width=border,
        )

    font = _caption_font(36)
    text_bbox = draw.textbbox((0, 0), caption, font=font)
    text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    x = (REPLAY_OUTPUT_SIZE[0] - text_w) / 2
    y = REPLAY_OUTPUT_SIZE[1] - text_h - 20
    # Simple outline effect so the caption reads over any background.
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        draw.text((x + dx, y + dy), caption, font=font, fill=(0, 0, 0))
    draw.text((x, y), caption, font=font, fill=(255, 60, 60))

    return image


def build_clip(
    frames: Sequence[tuple[float, Frame]],
    bbox: BBox | None,
    caption: str,
    output_path: Path,
) -> None:
    """Assemble a captioned, zoomed-in, slow-motion GIF from buffered frames.

    `bbox` is the (x0, y0, x1, y1) region to zoom into, in the frames' own
    pixel coordinates — pass None for a center-crop fallback (used for the
    bluff mode "joke replay," which has no real motion location). Raises
    ValueError on an empty `frames` sequence; the caller (main.py) wraps
    this in try/except so a failure here just skips the replay, never
    breaks the existing voice/gesture callout.
    """
    if not frames:
        raise ValueError("build_clip() needs at least one frame")

    frame_shape = frames[0][1].shape[:2]
    crop = _padded_bbox(bbox, frame_shape, REPLAY_ZOOM_PADDING_RATIO) if bbox else _center_bbox(frame_shape)

    rendered = [
        _render_frame(frame, crop, caption, flash=i < REPLAY_FLASH_FRAMES)
        for i, (_, frame) in enumerate(frames)
    ]
    slowed = [image for image in rendered for _ in range(REPLAY_SLOWMO_REPEAT)]

    slowed[0].save(
        output_path,
        save_all=True,
        append_images=slowed[1:],
        duration=REPLAY_FRAME_DURATION_MS,
        loop=0,
    )
