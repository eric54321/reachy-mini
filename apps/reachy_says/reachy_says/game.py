"""Reachy Says game state machine — round/timer/trick/score, no I/O.

Pure state transitions only; `main.py` drives this and performs the actual
TTS/gesture side effects when `tick()` reports an event. Keeping this
side-effect-free is what makes it unit-testable without a robot, without
real time.sleep()s, and without mocking threads (see `test_game.py`).

A game starts with INTRO (main.py speaks the greeting, pauses, then calls
begin_first_round()). From there each round flows: ANNOUNCING (main.py
speaks the command + plays its gesture) -> begin_waiting() -> WAITING
(countdown running, /confirm active) -> tick() resolves it -> RESULT
(main.py plays a success/gotcha reaction, paused for RESULT_PAUSE_SECONDS)
-> tick() either starts the next round (ANNOUNCING) or ends the game
(GAME_OVER).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from reachy_says.commands import COMMANDS, Command

MIN_TIMER_SECONDS = 2.0
MAX_TIMER_SECONDS = 15.0
DEFAULT_TIMER_SECONDS = 2.0
MIN_ROUNDS = 1
MAX_ROUNDS = 20
DEFAULT_MAX_ROUNDS = 5
TRICK_CHANCE = 0.30
RESULT_PAUSE_SECONDS = 2.0


class Status(str, Enum):
    IDLE = "idle"
    INTRO = "intro"
    ANNOUNCING = "announcing"
    WAITING = "waiting"
    RESULT = "result"
    GAME_OVER = "game_over"


@dataclass
class GameState:
    timer_seconds: float = DEFAULT_TIMER_SECONDS
    max_rounds: int = DEFAULT_MAX_ROUNDS
    status: Status = Status.IDLE
    round_number: int = 0
    score: int = 0
    current_command: Command | None = None
    is_trick: bool = False
    confirmed: bool = False
    round_deadline: float | None = None
    result_deadline: float | None = None
    last_result: str | None = None  # "success" | "survived_trick" | "gotcha" | None
    last_trick_round: bool = False

    _rng: random.Random = field(default_factory=random.Random, repr=False)
    _time_fn: Callable[[], float] = field(default=time.monotonic, repr=False)
    _last_command_name: str | None = field(default=None, repr=False)

    def configure(self, timer_seconds: float, max_rounds: int) -> None:
        """Set the round timer and number of rounds. Only meaningful before/between games."""
        if not (MIN_TIMER_SECONDS <= timer_seconds <= MAX_TIMER_SECONDS):
            raise ValueError(
                f"timer_seconds must be between {MIN_TIMER_SECONDS} and {MAX_TIMER_SECONDS}"
            )
        if not (MIN_ROUNDS <= max_rounds <= MAX_ROUNDS):
            raise ValueError(f"max_rounds must be between {MIN_ROUNDS} and {MAX_ROUNDS}")
        self.timer_seconds = timer_seconds
        self.max_rounds = max_rounds

    def start(self) -> None:
        """Begin a new game (from IDLE or GAME_OVER) — enters INTRO first;
        main.py plays the greeting (see main.py's INTRO_TEXT), pauses, then
        calls begin_first_round()."""
        self.round_number = 0
        self.score = 0
        self.last_result = None
        self.last_trick_round = False
        self._last_command_name = None
        self.status = Status.INTRO

    def begin_first_round(self) -> None:
        """Call once main.py's intro greeting (speak + pause) is done."""
        self._begin_round()

    def reset(self) -> None:
        """Stop whatever's happening and return to IDLE."""
        self.status = Status.IDLE
        self.round_number = 0
        self.score = 0
        self.current_command = None
        self.is_trick = False
        self.confirmed = False
        self.round_deadline = None
        self.result_deadline = None
        self.last_result = None
        self.last_trick_round = False

    def confirm(self) -> None:
        """Kid pressed "I did it!" — only takes effect while WAITING."""
        if self.status == Status.WAITING:
            self.confirmed = True

    def time_remaining(self) -> float:
        if self.status != Status.WAITING or self.round_deadline is None:
            return 0.0
        return max(0.0, self.round_deadline - self._time_fn())

    def begin_waiting(self) -> None:
        """Call once main.py's announce side effect (speak + gesture) is done."""
        self.round_deadline = self._time_fn() + self.timer_seconds
        self.status = Status.WAITING

    def tick(self) -> str | None:
        """Advance WAITING/RESULT if their deadline has passed.

        Returns an event string telling main.py which side effect to run:
        "result" (just resolved a round — play the success/gotcha reaction),
        "announce" (the next round just began — speak + gesture it), or
        "game_over" (play the closing reaction). None if nothing changed.
        """
        if self.status == Status.WAITING:
            if self.confirmed or self.time_remaining() <= 0:
                self._resolve_round()
                return "result"
        elif self.status == Status.RESULT:
            if self.result_deadline is not None and self._time_fn() >= self.result_deadline:
                self._advance_after_result()
                return "game_over" if self.status == Status.GAME_OVER else "announce"
        return None

    def to_public_dict(self) -> dict:
        """JSON-safe snapshot for the /state endpoint. Never leaks is_trick
        while a round is still in progress — only via last_result, once
        resolved."""
        showing_result = self.status in (Status.RESULT, Status.GAME_OVER)
        return {
            "status": self.status.value,
            "round_number": self.round_number,
            "max_rounds": self.max_rounds,
            "score": self.score,
            "timer_seconds": self.timer_seconds,
            "time_remaining": round(self.time_remaining(), 1),
            "last_result": self.last_result if showing_result else None,
            "won": self.status == Status.GAME_OVER and self.last_result != "gotcha",
        }

    def _begin_round(self) -> None:
        self.round_number += 1
        choices = [c for c in COMMANDS if c.name != self._last_command_name] or list(COMMANDS)
        self.current_command = self._rng.choice(choices)
        self._last_command_name = self.current_command.name
        self.is_trick = (
            self.round_number > 1
            and not self.last_trick_round
            and self._rng.random() < TRICK_CHANCE
        )
        self.confirmed = False
        self.status = Status.ANNOUNCING

    def _resolve_round(self) -> None:
        self.last_trick_round = self.is_trick
        if self.is_trick and self.confirmed:
            self.last_result = "gotcha"
        elif self.is_trick:
            self.last_result = "survived_trick"
            self.score += 1
        else:
            # No camera verification in V1 — a real round always counts as a
            # pass, whether confirmed in time or not (the game must not
            # stall waiting on a press that may never come).
            self.last_result = "success"
            self.score += 1
        self.status = Status.RESULT
        self.result_deadline = self._time_fn() + RESULT_PAUSE_SECONDS

    def _advance_after_result(self) -> None:
        if self.last_result == "gotcha" or self.round_number >= self.max_rounds:
            self.status = Status.GAME_OVER
        else:
            self._begin_round()
