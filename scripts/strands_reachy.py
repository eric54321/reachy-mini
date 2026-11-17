"""PoC: a Strands agent that drives Reachy Mini from a plain-English sentence.

    python scripts/strands_reachy.py "wiggle your antennas and look left"
    python scripts/strands_reachy.py --dry-run "nod twice"     # no robot, prints only

Model provider (env vars):
    LLM_PROVIDER=anthropic (default) | ollama
    REACHY_ANTHROPIC_KEY   Anthropic API key (system env var; never commit it)
    LLM_MODEL              override model id (default: claude-haiku-5-5 / qwen3:8b)

Robot connection: REACHY_MINI_HOST (IP; mDNS and auto-discovery don't work on
this network), default 192.168.50.216.

One controller at a time: don't run this while the reachy-mini MCP server is
connected to the robot (see CLAUDE.md gotchas).
"""

import argparse
import os
import time

import numpy as np
from strands import Agent, tool

SYSTEM_PROMPT = (
    "You control a small expressive robot named Reachy Mini. Do what the user "
    "asks by calling your tools, in order. Only call tools that were asked for. "
    "Use the speak tool only when asked to say something. "
    "Reply in one short sentence when done."
)

DRY_RUN = False
_mini = None  # shared ReachyMini connection (one controller only)


def _move(label: str, **kwargs) -> str:
    """Run one goto_target move (or just print it in dry-run mode)."""
    print(f"  -> {label}")
    if DRY_RUN:
        return f"(dry run) {label}"
    _mini.goto_target(**kwargs)
    time.sleep(kwargs.get("duration", 0.5) + 0.2)
    return f"Done: {label}"


def _pose(**kw):
    from reachy_mini.utils import create_head_pose

    return create_head_pose(**kw)


@tool
def wiggle_antennas(times: int = 2) -> str:
    """Wiggle Reachy's antennas back and forth.

    Args:
        times: How many wiggles (1-5).
    """
    for _ in range(max(1, min(times, 5))):
        _move("antennas out", antennas=np.deg2rad([35, -35]), duration=0.4)
        _move("antennas in", antennas=np.deg2rad([-35, 35]), duration=0.4)
    return _move("antennas neutral", antennas=[0.0, 0.0], duration=0.4)


@tool
def look(direction: str) -> str:
    """Turn Reachy's head to look in a direction.

    Args:
        direction: One of "left", "right", "up", "down", "center".
    """
    poses = {
        "left": dict(yaw=25),
        "right": dict(yaw=-25),
        "up": dict(pitch=-15),
        "down": dict(pitch=15),
        "center": {},
    }
    if direction not in poses:
        return f"Unknown direction {direction!r}; use left/right/up/down/center."
    head = None if DRY_RUN else _pose(**poses[direction])
    return _move(f"look {direction}", head=head, duration=1.0)


@tool
def nod(times: int = 2) -> str:
    """Nod Reachy's head yes.

    Args:
        times: How many nods (1-5).
    """
    for _ in range(max(1, min(times, 5))):
        _move("nod down", head=None if DRY_RUN else _pose(pitch=15), duration=0.5)
        _move("nod up", head=None if DRY_RUN else _pose(pitch=-5), duration=0.5)
    return _move("head neutral", head=None if DRY_RUN else _pose(), duration=0.5)


@tool
def speak(text: str) -> str:
    """Say something out loud through Reachy's speaker.

    Args:
        text: What to say. Keep it to one or two short sentences.
    """
    print(f"  -> say: {text!r}")
    if DRY_RUN:
        return f"(dry run) said: {text}"
    import wave

    # Local Piper TTS (free, no network), reused from apps/voice_gesture.
    from voice_gesture.tts import speak as synthesize

    path = synthesize(text)
    try:
        with wave.open(str(path), "rb") as w:
            duration = w.getnframes() / w.getframerate()
        _mini.media_manager.play_sound(str(path))  # fire-and-forget
        time.sleep(duration + 0.3)
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass  # Windows may still hold the temp file briefly
    return f"Said: {text}"


@tool
def go_to_sleep() -> str:
    """Put Reachy into its sleep pose."""
    print("  -> sleep")
    if DRY_RUN:
        return "(dry run) sleep"
    _mini.goto_sleep()
    return "Reachy is asleep."


def make_model():
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("LLM_MODEL", "qwen3:8b"),
        )
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args={"api_key": os.environ["REACHY_ANTHROPIC_KEY"]},
        model_id=os.environ.get("LLM_MODEL", "claude-haiku-5-5"),
        max_tokens=1024,
    )


def run_agent(prompt: str) -> None:
    agent = Agent(
        model=make_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[wiggle_antennas, look, nod, speak, go_to_sleep],
    )
    agent(prompt)
    print()


def main() -> None:
    global DRY_RUN, _mini
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", help="what you want Reachy to do")
    ap.add_argument("--dry-run", action="store_true", help="don't touch the robot")
    args = ap.parse_args()
    DRY_RUN = args.dry_run

    if DRY_RUN:
        run_agent(args.prompt)
        return

    from reachy_mini import ReachyMini

    # Connect by IP: auto-discovery false-positives on a Windows service
    # holding localhost:8000 and silently drives nothing (see SETUP.md).
    host = os.environ.get("REACHY_MINI_HOST", "192.168.50.216")
    with ReachyMini(host=host, connection_mode="network") as mini:
        _mini = mini
        # Motors can be left disabled (e.g. after sleep); commands are then
        # accepted but nothing moves.
        mini.enable_motors()
        time.sleep(1.0)
        run_agent(args.prompt)


if __name__ == "__main__":
    main()
