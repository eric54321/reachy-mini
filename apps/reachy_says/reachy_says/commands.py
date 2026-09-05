"""Static command library for Reachy Says — the "Simon says" action list.

Each command pairs a spoken action phrase with a move name from Pollen
Robotics' built-in emotions library (`pollen-robotics/reachy-mini-emotions-library`,
played via `reachy_says.gestures.GestureLibrary`). It's an *emotions* library,
not an *actions* library, so pairings here are the best available visual
flair for each command, not literal mimicry (e.g. "look up" pairs with a move
that tilts the head up/back, not a precise imitation).

Run `python -m reachy_says.gestures --list` to see every move name available
if you want to remap or add commands.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    phrase: str  # lowercase action phrase, e.g. "touch your nose"
    move_name: str


COMMANDS: tuple[Command, ...] = (
    Command("touch_nose", "touch your nose", "curious1"),
    Command("spin", "do a little spin", "dance1"),
    Command("look_up", "look up at the ceiling", "amazed1"),
    Command("bow", "take a bow", "welcoming1"),
    Command("thumbs_up", "give a thumbs up", "proud1"),
    Command("strike_pose", "strike a pose", "proud2"),
    Command("shake_no", "shake your head no", "no1"),
    Command("big_smile", "flash a big smile", "cheerful1"),
    Command("clap", "clap your hands", "enthusiastic1"),
    Command("touch_toes", "touch your toes", "downcast1"),
    Command("wave_hello", "wave hello", "welcoming2"),
    Command("one_foot", "stand on one foot", "uncertain1"),
    Command("cover_eyes", "cover your eyes", "shy1"),
    Command("tiptoe", "tiptoe in place", "calming1"),
    Command("jump", "jump", "electric1"),
    Command("stretch_tall", "stretch as tall as you can", "relief1"),
    Command("cross_arms", "cross your arms", "contempt1"),
)
