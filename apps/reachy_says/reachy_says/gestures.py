"""Play a named Reachy Mini gesture (move) on demand.

Adapted from `apps/voice_gesture/voice_gesture/emotion_to_gesture.py`'s
`GestureLibrary` — same `RecordedMoves(DEFAULT_EMOTIONS_DATASET)` load and
non-blocking-thread pattern, but keyed directly by a move name (already
resolved per-command in `commands.py`) instead of an emotion tag, since
Reachy Says' "commands" aren't emotions.

Run this file directly (with a robot/sim reachable, or just the cached
dataset) to print every move name currently in the library:

    python -m reachy_says.gestures --list
"""

from __future__ import annotations

import threading

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import DEFAULT_EMOTIONS_DATASET, RecordedMoves

# Fallback move if a command's move_name ever doesn't resolve.
DEFAULT_MOVE = "attentive1"


class GestureLibrary:
    """Loads the emotions move library once, plays gestures by move name."""

    def __init__(self) -> None:
        self._moves = RecordedMoves(DEFAULT_EMOTIONS_DATASET)

    def list_move_names(self) -> list[str]:
        """All move names available in the library."""
        return sorted(self._moves.list_moves())

    def play(
        self,
        reachy_mini: ReachyMini,
        move_name: str | None,
        *,
        sound: bool = False,
        blocking: bool = True,
    ) -> threading.Thread | None:
        """Play `move_name` (falling back to DEFAULT_MOVE) on `reachy_mini`.

        Args:
            reachy_mini: connected ReachyMini instance.
            move_name: a name from the emotions library, or None.
            sound: whether to also play the library's own sidecar sound for
                the move. Usually False here, since our own TTS audio plays
                the actual speech.
            blocking: if True, waits for the gesture to finish before
                returning. If False, plays it on a background thread so it
                can run concurrently with TTS audio.

        Returns:
            The background Thread if ``blocking=False``, so the caller can
            join it before moving on — a gesture is often longer than its
            sentence's audio.

        """
        move = self._moves.get(move_name or DEFAULT_MOVE)

        if blocking:
            reachy_mini.play_move(move, sound=sound)
            return None

        thread = threading.Thread(
            target=reachy_mini.play_move,
            kwargs={"move": move, "sound": sound},
            daemon=True,
        )
        thread.start()
        return thread


if __name__ == "__main__":
    import sys

    if "--list" in sys.argv:
        lib = GestureLibrary()
        for name in lib.list_move_names():
            print(name)
    else:
        print(__doc__)
