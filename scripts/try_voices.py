"""Play a short sample line with each downloaded Piper voice, back to back,
so you can hear the differences on the real robot.

Usage:
    python scripts/try_voices.py
    python scripts/try_voices.py "Custom line to say" voice1 voice2 ...
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "voice_gesture"))

from reachy_mini import ReachyMini  # noqa: E402

from voice_gesture.speak import VOICES_DIR, speak  # noqa: E402

DEFAULT_LINE = "Hi, this is my voice. What do you think?"

DEFAULT_VOICES = [
    "en_US-lessac-medium",
    "en_US-amy-medium",
    "en_US-ryan-medium",
    "en_GB-alan-medium",
    "en_US-kristin-medium",
]


def main() -> None:
    args = sys.argv[1:]
    if args and not (VOICES_DIR / f"{args[0]}.onnx").exists() and " " in args[0]:
        # First arg looks like a custom line, not a voice id.
        line, voices = args[0], (args[1:] or DEFAULT_VOICES)
    elif args:
        line, voices = DEFAULT_LINE, args
    else:
        line, voices = DEFAULT_LINE, DEFAULT_VOICES

    with ReachyMini(host="192.168.50.216", connection_mode="network") as mini:
        mini.enable_motors()
        mini.wake_up()

        for voice_id in voices:
            print(f"-> {voice_id}")
            audio_path = speak(line, voice_id)
            try:
                mini.media_manager.play_sound(str(audio_path))
                import wave

                with wave.open(str(audio_path), "rb") as wav_file:
                    duration = wav_file.getnframes() / wav_file.getframerate()
                time.sleep(duration + 0.8)
            finally:
                audio_path.unlink(missing_ok=True)

        mini.goto_sleep()


if __name__ == "__main__":
    main()
