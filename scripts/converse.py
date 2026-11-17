"""Talk to Reachy: listen -> Claude -> speak, with moves (Phase 3).

    python scripts/converse.py

Say something after the beep; Reachy answers out loud. Say "goodbye" (or
"stop listening") to end, or press Ctrl+C. Reuses:
    hear.py            microphone + local speech-to-text, auto end-of-speech
    strands_reachy.py  Claude model, move tools, robot connection helpers

Speed: the reply is streamed and each sentence is spoken as soon as it is
complete, while the rest is still being generated. The mic is only recording
while Reachy is NOT speaking, so it can't hear itself.

One controller at a time: don't run with the reachy-mini MCP server holding the
robot (see CLAUDE.md gotchas).
"""

import os
import queue
import re
import sys
import threading
import time
import wave

import hear
import strands_reachy as sr
from strands import Agent

PERSONA = (
    "You are Reachy Mini, a small, friendly, curious robot talking out loud with "
    "a family. Everything you write is spoken aloud, so answer in one or two short "
    "sentences, plain words, no lists, no markdown, no emoji. Use your move tools "
    "when asked, or when a feeling fits (play_emotion), but never narrate the tool "
    "calls. If you didn't understand, say so briefly."
)
EXIT_WORDS = ("goodbye", "good bye", "stop listening", "bye reachy", "quit")
MAX_EMPTY_IN_A_ROW = 3  # this many silent listens in a row ends the chat
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

TOOLS = [sr.wiggle_antennas, sr.look, sr.nod, sr.play_emotion, sr.go_to_sleep]


class Speaker:
    """Speaks sentences one after another on a background thread."""

    def __init__(self, mini) -> None:
        self.mini = mini
        self.q: queue.Queue = queue.Queue()
        self.first_audio_at: float | None = None
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str) -> None:
        text = text.strip()
        if text:
            self.q.put(text)

    def wait(self) -> None:
        """Block until everything queued has been spoken."""
        self.q.join()

    def _run(self) -> None:
        from voice_gesture.tts import speak as synthesize

        while True:
            text = self.q.get()
            try:
                path = synthesize(text)
                try:
                    with wave.open(str(path), "rb") as w:
                        duration = w.getnframes() / w.getframerate()
                    if self.first_audio_at is None:
                        self.first_audio_at = time.perf_counter()
                    self.mini.media_manager.play_sound(str(path))
                    time.sleep(duration + 0.15)
                finally:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
            except Exception as e:
                print(f"[speak error] {e}")
            finally:
                self.q.task_done()


class StreamHandler:
    """Strands callback: prints the reply and hands finished sentences to the speaker."""

    def __init__(self, speaker: Speaker) -> None:
        self.speaker = speaker
        self.buf = ""

    def __call__(self, **kw) -> None:
        tool = kw.get("event", {}).get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool:
            print(f"  [{tool['name']}]")
        data = kw.get("data", "")
        if not data:
            return
        print(data, end="", flush=True)
        self.buf += data
        parts = SENTENCE_END.split(self.buf)
        for sentence in parts[:-1]:  # all but the still-growing tail are complete
            self.speaker.say(sentence)
        self.buf = parts[-1]

    def flush(self) -> None:
        self.speaker.say(self.buf)
        self.buf = ""


def think_pose(mini) -> None:
    mini.goto_target(antennas=[0.35, -0.1], duration=0.3)


def main() -> None:
    from reachy_mini import ReachyMini

    model = sr.make_model()  # exits early with a clear message if the key is missing
    hear.get_model()  # load Whisper before connecting so the first turn is quick

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

        speaker = Speaker(mini)
        handler = StreamHandler(speaker)
        agent = Agent(model=model, system_prompt=PERSONA, tools=TOOLS, callback_handler=handler)

        speaker.say("Hi! I'm listening. Talk to me after the beep.")
        speaker.wait()
        empties = 0
        while True:
            text = hear.listen(mini, auto=True)
            if not text:
                empties += 1
                if empties >= MAX_EMPTY_IN_A_ROW:
                    speaker.say("I'll stop listening now. Talk to me any time.")
                    speaker.wait()
                    break
                continue
            empties = 0
            print(f"you> {text}")
            if any(w in text.lower() for w in EXIT_WORDS):
                speaker.say("Goodbye!")
                speaker.wait()
                break

            t0 = time.perf_counter()
            speaker.first_audio_at = None
            think_pose(mini)
            print("reachy> ", end="", flush=True)
            try:
                agent(text)
                handler.flush()
            except Exception as e:
                handler.buf = ""
                print(f"\n[error] {type(e).__name__}: {e}")
                speaker.say("Sorry, something went wrong.")
            speaker.wait()
            mini.goto_target(antennas=[0.0, 0.0], duration=0.3)
            first = speaker.first_audio_at
            print(
                f"\n[time] to first spoken word {'-' if first is None else f'{first - t0:.1f}s'}, "
                f"turn total {time.perf_counter() - t0:.1f}s"
            )
            time.sleep(0.4)  # let the room go quiet before listening again
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        ctx.__exit__(None, None, None)


if __name__ == "__main__":
    main()
