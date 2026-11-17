"""PoC: a Strands agent that drives Reachy Mini from plain English.

    python scripts/strands_reachy.py                       # interactive chat (remembers context)
    python scripts/strands_reachy.py "nod, then say hi"    # one-shot
    python scripts/strands_reachy.py --dry-run "nod twice" # no robot, prints only

Settings come from the environment, or from the repo's gitignored .env:
    REACHY_ANTHROPIC_KEY   Anthropic API key (system env var; never commit it)
    LLM_MODEL              model id (default: claude-haiku-5-5)
    REACHY_MINI_HOST       robot IP (default 192.168.50.216; mDNS and SDK
                           auto-discovery don't work on this network)
    REACHY_VOLUME          speaker volume 0-100, set on connect (default 40)
    LLM_PROVIDER           anthropic (default) | ollama (deferred, untested)

Each turn prints how long the first tool call and the whole reply took, and
appends a row to logs/strands_latency.csv for comparing changes over time.

One controller at a time: don't run this while the reachy-mini MCP server is
connected to the robot (see CLAUDE.md gotchas).
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from strands import Agent, tool

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

SYSTEM_PROMPT = (
    "You control a small expressive robot named Reachy Mini. Do what the user "
    "asks by calling your tools, in order. Only call tools that were asked for. "
    "Use the speak tool only when asked to say something, and keep anything you "
    "say to one or two short sentences. Use play_emotion for feelings and "
    "wiggle/look/nod for simple moves. Reply in one short sentence when done."
)

DRY_RUN = False
_mini = None  # shared ReachyMini connection (one controller only)
_gestures = None  # lazily-loaded emotion library
_turn_start = 0.0
_first_tool_at = None  # seconds into the turn when the first tool began


def _mark() -> None:
    """Record when the first tool of the current turn starts (latency metric)."""
    global _first_tool_at
    if _first_tool_at is None:
        _first_tool_at = time.perf_counter() - _turn_start


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
    _mark()
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
    _mark()
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
    _mark()
    for _ in range(max(1, min(times, 5))):
        _move("nod down", head=None if DRY_RUN else _pose(pitch=15), duration=0.5)
        _move("nod up", head=None if DRY_RUN else _pose(pitch=-5), duration=0.5)
    return _move("head neutral", head=None if DRY_RUN else _pose(), duration=0.5)


def _emotion_names() -> list[str]:
    from voice_gesture.emotion_to_gesture import list_emotions

    return list_emotions()


@tool
def play_emotion(emotion: str) -> str:
    """Act out an emotion with Reachy's built-in expressive animations.

    Args:
        emotion: One of happy, sad, excited, curious, confused, surprised, angry,
            scared, tired, proud, shy, loving, bored, grateful, annoyed, laughing,
            thoughtful, disgusted, relieved, lonely.
    """
    _mark()
    global _gestures
    print(f"  -> emotion: {emotion}")
    if emotion not in _emotion_names():
        return f"Unknown emotion {emotion!r}; choose from: {', '.join(_emotion_names())}."
    if DRY_RUN:
        return f"(dry run) emotion {emotion}"
    if _gestures is None:
        from voice_gesture.emotion_to_gesture import GestureLibrary

        _gestures = GestureLibrary()
    _gestures.play(_mini, emotion, sound=False, blocking=True)
    return f"Done: {emotion}"


@tool
def speak(text: str) -> str:
    """Say something out loud through Reachy's speaker.

    Args:
        text: What to say. Keep it to one or two short sentences.
    """
    _mark()
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
    _mark()
    print("  -> sleep")
    if DRY_RUN:
        return "(dry run) sleep"
    _mini.goto_sleep()
    return "Reachy is asleep."


TOOLS = [wiggle_antennas, look, nod, play_emotion, speak, go_to_sleep]


def make_model():
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("LLM_MODEL", "qwen3:8b"),
        )
    key = os.environ.get("REACHY_ANTHROPIC_KEY")
    if not key:
        sys.exit(
            "REACHY_ANTHROPIC_KEY is not set. Set it as a user environment variable "
            "(then open a new terminal) or put it in the repo's .env."
        )
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args={"api_key": key},
        model_id=os.environ.get("LLM_MODEL", "claude-haiku-5-5"),
        max_tokens=1024,
    )


def set_volume(mini, volume: int) -> None:
    """Speaker volume lives on the robot's daemon (0-100), not on this PC."""
    import requests

    base = getattr(mini, "_daemon_http_url", None) or f"http://{mini.host}:8000"
    try:
        requests.post(f"{base}/api/volume/set", json={"volume": volume}, timeout=5)
    except requests.RequestException as e:
        print(f"(could not set volume: {e})")


def log_latency(prompt: str, first_tool: float | None, total: float) -> None:
    path = REPO_ROOT / "logs" / "strands_latency.csv"
    path.parent.mkdir(exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "model", "first_tool_s", "total_s", "prompt"])
        w.writerow(
            [
                time.strftime("%Y-%m-%d %H:%M:%S"),
                os.environ.get("LLM_MODEL", "claude-haiku-5-5"),
                "" if first_tool is None else f"{first_tool:.2f}",
                f"{total:.2f}",
                prompt,
            ]
        )


def run_turn(agent: Agent, prompt: str) -> None:
    """One user turn. The agent object keeps memory across turns."""
    global _turn_start, _first_tool_at
    _turn_start, _first_tool_at = time.perf_counter(), None
    try:
        agent(prompt)
    except Exception as e:  # network/API/tool failure: report, keep the chat alive
        print(f"\n[error] {type(e).__name__}: {e}")
        return
    total = time.perf_counter() - _turn_start
    ft = "none" if _first_tool_at is None else f"{_first_tool_at:.1f}s"
    print(f"\n[time] first tool {ft}, total {total:.1f}s")
    log_latency(prompt, _first_tool_at, total)


def chat(agent: Agent, first_prompt: str | None) -> None:
    if first_prompt:
        run_turn(agent, first_prompt)
        return
    print("Chat with Reachy. Empty line or Ctrl+C to quit.")
    while True:
        try:
            prompt = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt:
            break
        run_turn(agent, prompt)


def main() -> None:
    global DRY_RUN, _mini
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", help="one-shot request; omit for chat mode")
    ap.add_argument("--dry-run", action="store_true", help="don't touch the robot")
    args = ap.parse_args()
    DRY_RUN = args.dry_run

    agent = Agent(model=make_model(), system_prompt=SYSTEM_PROMPT, tools=TOOLS)

    if DRY_RUN:
        chat(agent, args.prompt)
        return

    from reachy_mini import ReachyMini

    # Connect by IP: auto-discovery false-positives on a Windows service
    # holding localhost:8000 and silently drives nothing (see SETUP.md).
    host = os.environ.get("REACHY_MINI_HOST", "192.168.50.216")
    try:
        mini_ctx = ReachyMini(host=host, connection_mode="network")
        mini = mini_ctx.__enter__()
    except Exception as e:
        sys.exit(
            f"Could not connect to Reachy at {host}: {e}\n"
            "Check the robot is on, the daemon is running, and that the "
            "reachy-mini MCP server or another script isn't holding it."
        )
    try:
        _mini = mini
        # Motors can be left disabled (e.g. after sleep); commands are then
        # accepted but nothing moves.
        mini.enable_motors()
        time.sleep(1.0)
        set_volume(mini, int(os.environ.get("REACHY_VOLUME", "40")))
        chat(agent, args.prompt)
    finally:
        mini_ctx.__exit__(None, None, None)


if __name__ == "__main__":
    main()
