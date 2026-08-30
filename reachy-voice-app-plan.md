# Reachy voice + gesture app — plan

## What it does
Reachy talks using a voice you pick, and moves its head to match the emotion of what it's saying.

## The three pieces

1. **Voice picker** — a simple list of voices (grouped by provider: OpenAI, ElevenLabs, Grok, or a free local option like Piper). Pick one, that's your voice.

2. **Text-to-speech (TTS) adapter** — one function that takes text + a voice, and returns audio. It doesn't matter which company made the voice — the rest of the app treats them all the same way. This is what makes it easy to swap or add providers later.

3. **Gesture on speak** — Reachy moves its head to match the mood of what it's saying.

## Key decisions made so far

- **No voice cloning.** Just pick from existing voices (OpenAI, ElevenLabs, Grok, free/local). Simpler, no recording or consent flow needed.
- **Gestures: use Reachy's built-in gesture functions.** We are not building or animating custom head movements — just calling whatever gesture methods already exist in Reachy's SDK.
- **Emotion tags: manual.** You type them into the message yourself, like `[happy] Hi there!`. No extra AI call to guess emotion — keeps things simple and predictable.
- **Sync strategy: one gesture per sentence.** No timestamp matching, no precise lip-sync. Fire the gesture the moment that sentence's audio starts playing.

## How one message flows through the app

1. Split the message into segments (one sentence each, with its emotion tag).
2. For each segment, in order:
   - Generate audio for that sentence (TTS call)
   - Start playing the audio
   - Look up the emotion → call the matching Reachy gesture function
   - Wait for the audio to finish
   - Move to the next segment

## Code structure (planned)

Three small, separately testable pieces:

- `split_message(text)` → list of `{sentence, emotion}`
- `speak(sentence, voice_id)` → audio file
- `emotion_to_gesture(emotion)` → looks up which real Reachy SDK gesture function matches, and calls it

## Progress

- App scaffolded at [apps/voice_gesture/](apps/voice_gesture/) via `reachy-mini-app-assistant create`.
- `split_message(text)` done — [apps/voice_gesture/voice_gesture/split_message.py](apps/voice_gesture/voice_gesture/split_message.py), 8 passing tests in [test_split_message.py](apps/voice_gesture/voice_gesture/test_split_message.py).
- `emotion_to_gesture` done — [apps/voice_gesture/voice_gesture/emotion_to_gesture.py](apps/voice_gesture/voice_gesture/emotion_to_gesture.py). Gestures come from Pollen's real
  `pollen-robotics/reachy-mini-emotions-library` HF dataset (85 named moves, e.g. `cheerful1`, `sad1`,
  `furious1`) loaded via `reachy_mini.motion.recorded_move.RecordedMoves` and played with
  `reachy_mini.play_move(move, sound=False)`. Run `python -m voice_gesture.emotion_to_gesture --list`
  to see all 85 move names (no robot needed — it's just reading the cached dataset).
- `speak(sentence, voice_id)` done — [speak.py](apps/voice_gesture/voice_gesture/speak.py), using **Piper**
  (free/local, no API key). Voice model (`en_US-lessac-medium`, ~60MB) downloaded into
  `apps/voice_gesture/voices/` (gitignored — redownload with
  `python -m piper.download_voices en_US-lessac-medium --download-dir voices`). 2 passing tests
  in [test_speak.py](apps/voice_gesture/voice_gesture/test_speak.py).
- All three pieces wired together in [main.py](apps/voice_gesture/voice_gesture/main.py)'s `say()`
  function, run from the app's settings endpoint `POST /say {"text": "..."}`. Full 10-test suite
  passes.

- **Verified end-to-end on the physical robot** (2026-08-30) via
  [scripts/test_voice_gesture.py](scripts/test_voice_gesture.py): wake up → speak 3 sentences with
  per-emotion gestures → go to sleep, all correct. Two real bugs found and fixed along the way:
  - mDNS hostname (`reachy-mini.local`) doesn't resolve on this network — connect by IP instead
    (`192.168.50.216`, `connection_mode="network"`), same as `scripts/test_movements_ip.py`.
  - `say()` was returning (and disconnecting) while the last sentence's gesture was still
    mid-playback, since gestures often outlast their short TTS clip — killed the gesture mid-move.
    Fixed by tracking and `.join()`-ing the gesture's background thread before returning.
  - Commands succeeded with zero physical movement — turned out to be torque disabled on the
    robot (`wake_up()`/`goto_target()` don't call `enable_motors()` themselves). Fixed with an
    explicit `mini.enable_motors()` call, now added defensively to `test_voice_gesture.py` and
    `wake_up.py` before waking up.
- Added [scripts/wake_up.py](scripts/wake_up.py) (mirrors existing `go_to_sleep.py`) for
  standalone testing of the wake/sleep poses.

- **Voice picker built** — completes piece 1 of the plan. 5 Piper voices downloaded
  (`en_US-lessac-medium` default, plus `amy`, `ryan`, `kristin`, `en_GB-alan`), all auditioned
  live on the robot via [scripts/try_voices.py](scripts/try_voices.py) and confirmed sounding fine.
  Real picker UI added:
  - `GET /voices` — lists downloaded voices + which one is current
  - `POST /voice {"voice_id": "..."}` — switches the current voice (rejects unknown ids)
  - `POST /say {"text": "...", "voice_id": "..."}` — `voice_id` now optional, defaults to
    whichever voice is current (previously this field was silently ignored — a real bug, fixed
    here)
  - [static/index.html](apps/voice_gesture/voice_gesture/static/index.html) +
    [static/main.js](apps/voice_gesture/voice_gesture/static/main.js) rebuilt as an actual
    message box + voice dropdown + "Say it" button, replacing the scaffold's antenna/sound demo.
  - 14-test suite passes, including 3 new endpoint tests in
    [test_picker_endpoints.py](apps/voice_gesture/voice_gesture/test_picker_endpoints.py) (using
    FastAPI's `TestClient` against a fake robot — no hardware needed to verify picker logic).

- **Full app verified end-to-end through the real browser UI** (2026-08-30):
  `python -m voice_gesture.main` → wake up → open http://localhost:8042 → type a message, pick a
  voice, click "Say it" → Reachy speaks it with the matching gesture. Found and fixed two more
  issues along the way:
  - `main.py`'s `__main__` block wasn't passing the IP workaround to `wrapped_run()`, so the
    full app hit the same mDNS failure as the early scripts. Fixed: `app.wrapped_run(host="192.168.50.216")`.
  - The app was missing `wake_up()`/`goto_sleep()` entirely (only individual test scripts had
    them) — added `enable_motors()` + `wake_up()` at the start of `run()`, `goto_sleep()` after
    the main loop exits.
  - **Real crash bug:** an uncaught exception in `say()` (e.g. a transient network timeout
    talking to the robot's daemon) propagated all the way up through `wrapped_run()` and killed
    the *entire app process*, not just that one request. Fixed by wrapping the `say()` call in
    the main loop in try/except — a mid-session hiccup now gets logged and the app stays alive
    for the next `/say` request, rather than taking the whole service down.
  - Also hit a genuine robot-side flake mid-testing: Reachy dropped off WiFi entirely for a bit
    (unrelated to our code) — resolved on its own once physically checked/back online.
- See [[reachy-mdns-connection-workaround]] memory for the accumulated hardware-flakiness
  findings (mDNS, stuck motor-driver state + daemon restart fix) — several instances of "commands
  succeed, robot doesn't respond" turned out to be robot/daemon-side, not app bugs.

- **Volume control + emotion picklist added to the UI**, plus a **physical/sim connection
  toggle**:
  - `GET/POST /volume` proxies the daemon's own OS-level volume API
    (`http://<robot-ip>:8000/api/volume/{current,set}` — a robot/daemon endpoint, not part of
    the `reachy_mini` SDK client). UI has a slider (debounced).
  - `GET /emotions` lists the 20 usable `[tag]` names from `emotion_to_gesture.py`; UI has a
    dropdown + "Insert" button that drops `[tag] ` into the message box at the cursor.
  - Physical vs. simulator is now an `.env` toggle (`REACHY_MINI_MODE=physical|sim` +
    host/port overrides — see `.env.example` and `_connection_kwargs()` in `main.py`), instead
    of the hardcoded IP. Defaults to physical, unchanged behavior when `.env` is absent. Note:
    this machine's port 8000 is blocked (see SETUP.md), so a sim daemon needs an alternate
    port and both modes connect by explicit host+port rather than relying on the SDK's
    localhost auto-detect.
  - 20-test suite passes (added tests for `/emotions`, `/volume` degrading gracefully without
    a real daemon, and `_connection_kwargs()`'s physical/sim branching).
- Pushed to GitHub: [eric54321/reachy-mini@bb4ea99](https://github.com/eric54321/reachy-mini/commit/bb4ea99).

## Next steps

- Consider adding OpenAI/ElevenLabs/Grok as additional `speak()` backends later — the adapter
  shape (`speak(sentence, voice_id) -> Path`) is already provider-agnostic, so this is additive,
  not a rewrite. The voice picker's `/voices` list would need to merge in non-Piper voice ids too.
- Revisit the naive `time.sleep(duration)` sentence-pacing in `say()` if it drifts noticeably
  from actual audio playback with longer messages
- Sim mode is implemented but not yet tried end-to-end (needs `reachy-mini-daemon --sim
  --headless --fastapi-port <port>` running locally first)
