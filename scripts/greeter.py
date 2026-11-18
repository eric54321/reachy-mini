"""Reachy starts the conversation: notices someone, looks, introduces himself, asks.

    python scripts/greeter.py

Idle loop: Reachy watches the camera with a free, local motion check (no API
calls, nothing leaves the PC). When someone moves into view for a moment, he
takes ONE picture, asks Claude for a short friendly opener based on what the
person is doing, speaks it, and then carries on as a normal conversation
(converse.py's loop). After the chat he waits a cooldown before greeting again.

The picture is only sent to Claude when motion triggers a greeting, and is not
saved. He is told not to identify anyone by their face.

Settings (env or .env):
    GREET_MOTION     motion sensitivity, mean pixel change 0-255 (default 1.0; lower = jumpier)
    GREET_COOLDOWN   seconds before greeting again after a chat (default 120)
    REACHY_VOLUME, REACHY_MINI_HOST, REACHY_ANTHROPIC_KEY  as in the other scripts

Ctrl+C to stop. One controller at a time (see CLAUDE.md).
"""

import io
import logging
import os
import sys
import time

import numpy as np
from PIL import Image
from strands import Agent

os.environ.setdefault("REACHY_VOLUME", "80")  # greeter default; must be set before importing converse

import converse
import hear
import strands_reachy as sr

PERSONA = converse.PERSONA + (
    " You are a friendly, curious robot who sometimes starts conversations. Never "
    "say who a person is or guess their identity from how they look; describing "
    "what they are doing or wearing is fine."
)

OPENER_PROMPT = (
    "Someone just moved into view of your camera (picture attached). Start a "
    "conversation: say hi, introduce yourself as Reachy Mini in a few words, "
    "mention one thing you notice them doing, and ask one short friendly question "
    "about it. Two short sentences at most. If you can't see a person, just say "
    "hi and ask who is there."
)

MOTION = float(os.environ.get("GREET_MOTION", "1.0"))
COOLDOWN = float(os.environ.get("GREET_COOLDOWN", "120"))
HITS_NEEDED = 2  # consecutive motion checks, so one flicker doesn't trigger
CHECK_EVERY = 0.5


def small_gray(jpeg: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(jpeg)).convert("L").resize((64, 48))
    return np.asarray(img, dtype=np.float32)


def wait_for_motion(mini) -> None:
    """Block until the camera sees sustained movement."""
    prev, hits = None, 0
    while True:
        jpeg = mini.media_manager.get_frame_jpeg()
        if jpeg:
            cur = small_gray(jpeg)
            if prev is not None:
                diff = float(np.abs(cur - prev).mean())
                hits = hits + 1 if diff > MOTION else 0
                if hits >= HITS_NEEDED:
                    return
            prev = cur
        time.sleep(CHECK_EVERY)


def main() -> None:
    from reachy_mini import ReachyMini

    for name in list(logging.root.manager.loggerDict):
        if name.startswith("reachy_mini"):
            logging.getLogger(name).setLevel(logging.CRITICAL)

    model = sr.make_model()
    hear.get_model()

    host = os.environ.get("REACHY_MINI_HOST", "192.168.50.216")
    try:
        ctx = ReachyMini(host=host, connection_mode="network")
        mini = ctx.__enter__()
    except Exception as e:
        sys.exit(f"Could not connect to Reachy at {host}: {e}")

    try:
        sr._mini = mini
        sr.DRY_RUN = False
        mini.enable_motors()
        time.sleep(1.0)
        sr.set_volume(mini, int(os.environ.get("REACHY_VOLUME", "50")))
        sr.rest_pose(mini)  # a previous run may have left the head tilted (dark camera)

        speaker = converse.Speaker(mini)
        handler = converse.StreamHandler(speaker)
        agent = Agent(
            model=model, system_prompt=PERSONA, tools=converse.TOOLS, callback_handler=handler
        )
        print(f"Watching for someone (sensitivity {MOTION:g}, cooldown {COOLDOWN:g}s). Ctrl+C to stop.")
        while True:
            wait_for_motion(mini)
            print("[someone is here]")
            frame = sr.look_at_camera()  # one picture, as an image content block
            if frame.get("status") != "success":
                time.sleep(5)
                continue
            mini.goto_target(antennas=[0.35, -0.1], duration=0.3)  # perk up
            speaker.first_audio_at = None
            print("reachy> ", end="", flush=True)
            try:
                agent([{"text": OPENER_PROMPT}, frame["content"][1]])
                handler.flush()
            except Exception as e:
                handler.buf = ""
                print(f"\n[error] {type(e).__name__}: {e}")
                time.sleep(10)
                continue
            speaker.wait()
            converse.MOVES.wait()
            converse.converse_loop(mini, agent, speaker, handler, end_on_silence=False)  # only stop/goodbye ends it
            sr.rest_pose(mini)
            print(f"\n[cooldown {COOLDOWN:g}s]")
            time.sleep(COOLDOWN)
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        converse.MOVES.wait()
        sr.rest_pose(mini)
        ctx.__exit__(None, None, None)


if __name__ == "__main__":
    main()
