"""Map an emotion tag to a real Reachy Mini gesture and play it.

Gestures come from Pollen Robotics' built-in emotions library
(``pollen-robotics/reachy-mini-emotions-library``, loaded via
``reachy_mini.motion.recorded_move.RecordedMoves``) — we don't animate
anything custom here, just call what already exists.

Run this file directly (with a robot/sim reachable) to print every move name
currently in the library, e.g. to extend EMOTION_TO_MOVE:

    python -m voice_gesture.emotion_to_gesture --list
"""

from __future__ import annotations

import threading

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import DEFAULT_EMOTIONS_DATASET, RecordedMoves

# Our manual emotion tags (used in message text, e.g. "[happy] Hi!") mapped
# to a move name from the emotions library. Add tags here as needed; run
# with --list to see every move name available to map onto.
EMOTION_TO_MOVE: dict[str, str] = {
    "happy": "cheerful1",
    "sad": "sad1",
    "excited": "enthusiastic1",
    "curious": "curious1",
    "confused": "confused1",
    "surprised": "surprised1",
    "angry": "furious1",
    "scared": "scared1",
    "tired": "tired1",
    "proud": "proud1",
    "shy": "shy1",
    "loving": "loving1",
    "bored": "boredom1",
    "grateful": "grateful1",
    "annoyed": "irritated1",
    "laughing": "laughing1",
    "thoughtful": "thoughtful1",
    "disgusted": "disgusted1",
    "relieved": "relief1",
    "lonely": "lonely1",
}

# Fallback move for a tag we don't have a mapping for (or no tag at all).
DEFAULT_MOVE = "attentive1"


def list_emotions() -> list[str]:
    """Our manual emotion tags usable in message text (e.g. "[happy]"), sorted."""
    return sorted(EMOTION_TO_MOVE.keys())


class GestureLibrary:
    """Loads the emotions move library once, plays gestures by emotion tag."""

    def __init__(self) -> None:
        self._moves = RecordedMoves(DEFAULT_EMOTIONS_DATASET)

    def list_move_names(self) -> list[str]:
        """All move names available in the library."""
        return sorted(self._moves.list_moves())

    def move_name_for(self, emotion: str | None) -> str:
        """Resolve an emotion tag to a move name (falls back to DEFAULT_MOVE)."""
        if emotion is None:
            return DEFAULT_MOVE
        return EMOTION_TO_MOVE.get(emotion, DEFAULT_MOVE)

    def play(
        self,
        reachy_mini: ReachyMini,
        emotion: str | None,
        *,
        sound: bool = False,
        blocking: bool = True,
    ) -> threading.Thread | None:
        """Play the gesture mapped to ``emotion`` on ``reachy_mini``.

        Args:
            reachy_mini: connected ReachyMini instance.
            emotion: our manual emotion tag (e.g. "happy"), or None.
            sound: whether to also play the library's own sidecar sound for
                the move. Usually False here, since our own TTS audio plays
                the actual speech.
            blocking: if True, waits for the gesture to finish before
                returning. If False, plays it on a background thread so it
                can run concurrently with TTS audio.

        Returns:
            The background Thread if ``blocking=False``, so the caller can
            join it before disconnecting — a gesture is often longer than
            its sentence's audio, and closing the connection out from under
            a still-running gesture throws mid-move. ``None`` when blocking.

        """
        move_name = self.move_name_for(emotion)
        move = self._moves.get(move_name)

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
