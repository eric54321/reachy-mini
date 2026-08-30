"""Try the voice_gesture app's full pipeline (split -> speak -> gesture)
directly against a connected Reachy Mini, without running the full app server.

Usage:
    python scripts/test_voice_gesture.py
    python scripts/test_voice_gesture.py "[happy] Hi there! [curious] What's up?"

See CLAUDE.md gotchas: don't run this while the MCP server also holds a
connection to the robot — only one controller at a time.
"""

import sys
from pathlib import Path

# apps/voice_gesture isn't pip-installed; import it straight from the repo.
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "voice_gesture"))

from reachy_mini import ReachyMini  # noqa: E402

from voice_gesture.emotion_to_gesture import GestureLibrary  # noqa: E402
from voice_gesture.main import say  # noqa: E402

DEFAULT_MESSAGE = "[happy] Hi there! I'm Reachy Mini. [curious] What should we do today?"


def main() -> None:
    text = " ".join(sys.argv[1:]) or DEFAULT_MESSAGE
    print(f"Message: {text!r}")

    gestures = GestureLibrary()

    # mDNS discovery ("reachy-mini.local") isn't resolving on this network;
    # connect by IP instead (see scripts/test_movements_ip.py for precedent).
    with ReachyMini(host="192.168.50.216", connection_mode="network") as mini:
        mini.enable_motors()  # no-op if already on; commands silently do nothing without it
        print("Waking up...")
        mini.wake_up()
        say(mini, gestures, text)
        print("Going back to sleep...")
        mini.goto_sleep()


if __name__ == "__main__":
    main()
