---
title: Reachy Says
emoji: 🎮
colorFrom: green
colorTo: yellow
sdk: static
pinned: false
short_description: Simon-Says-style game — Reachy calls out actions and tries to catch you out.
tags:
 - reachy_mini
 - reachy_mini_python_app
---

See [../../reachy-says-requirements.md](../../reachy-says-requirements.md) (if present locally —
it's the requirements doc this app was built from) for the full feature list and rationale.

## What it does

Reachy leads a Simon-Says game: it calls out a physical action ("Reachy says, touch your nose!"),
performs its own gesture as a visual cue, and gives you a few seconds to do it — confirmed with an
"I did it!" button in the browser UI, with a live countdown on screen. Every so often Reachy skips
the "Reachy says" prefix; pressing the button anyway is a "gotcha" that ends the game. Survive all
the rounds and you win. No camera-based move verification in V1 — it's self-reported, on the honor
system.

## One-time setup

From this folder (`apps/reachy_says/`), in the `reachy` conda env (see [../../SETUP.md](../../SETUP.md)):

```bash
pip install -e .
```

If the Piper voice models aren't downloaded yet (`voices/*.onnx` — gitignored, not part of the repo):

```bash
python -m piper.download_voices en_GB-alan-medium en_US-lessac-medium en_US-ryan-medium en_US-joe-medium en_US-bryce-medium en_US-mike-medium en_GB-northern_english_male-medium en_US-amy-medium en_US-kristin-medium --download-dir voices
```

(`en_GB-alan-medium` is the default and required; the rest are optional extras the UI's voice
dropdown will also show if present — 7 male voices (`alan`, `lessac`, `ryan`, `joe`, `bryce`,
`mike`, `northern_english_male`) and 2 female (`amy`, `kristin`). Piper's full catalog is much
bigger — `python -c "from piper.download_voices import list_voices; list_voices()"` lists every
name if you want to swap any of these out.)

## Starting the app

**Against the physical robot** (default — nothing extra needed, assuming the robot is powered on
and reachable):

```bash
python -m reachy_says.main
```

Or from this folder, `start_app.bat` (opens it in its own window). Stop it with Ctrl-C in that
window (graceful shutdown); `stop_app.bat` is a force-kill fallback if the window isn't handy.

**Against a local simulator instead:** first start a sim daemon in its own terminal — either

```bash
reachy-mini-daemon --sim --fastapi-port 8090
```

or, from the repo root, `start_sim.bat` (opens it in its own window, viewer visible). Stop it
with Ctrl-C in that window; `stop_sim.bat` is a force-kill fallback if the window isn't handy.

Then copy [../../.env.example](../../.env.example) to `../../.env` (shared across apps in this
repo) and set:

```
REACHY_MINI_MODE=sim
REACHY_MINI_SIM_PORT=8090   # match whatever port you started the sim daemon on
```

...and run the app the same way (`python -m reachy_says.main` or `start_app.bat`).

In either mode, once running, the app wakes the robot up on startup, prints
`Uvicorn running on http://0.0.0.0:8043` once the settings UI is ready, and puts it back to sleep
when you stop the app (Ctrl+C). Port 8043 (not 8042) so this can run alongside `voice_gesture` if
both are up at once.

You don't have to relaunch to switch between them, either — the **Connection** dropdown in the UI
(see below) flips `REACHY_MINI_MODE` and reconnects on the fly, no terminal needed. It doesn't
start or stop a sim daemon for you, though — that part's still `start_sim.bat`/`stop_sim.bat` (or
the raw command above), so make sure one is already running before switching to "Simulator".

## Using the UI

Open the game page in a browser:

- `http://localhost:8043` on the machine running the app
- `http://<that machine's LAN IP>:8043` from another device on the same WiFi (e.g. a phone)

1. Pick the **connection** (physical robot / simulator), a **voice**, and set the **volume** —
   these apply immediately, any time. Switching connection takes a few seconds to reconnect;
   the page recovers on its own once it's back.
2. Set the **round timer** (2–15 seconds) and **number of rounds** (1–20), then click
   **Start Game**. Reachy opens with a short greeting ("Hello everyone, let's play Reachy
   Says. Ready, set, go!") and a one-second pause before round 1 starts.
3. Listen and watch — Reachy speaks the command and plays a matching gesture.
4. Click **I did it!** once you've done the action, before the countdown runs out.
5. If Reachy skips saying "Reachy says" and you click the button anyway, that's a gotcha — game
   over. Otherwise it keeps going until you've survived every round.
6. **Reset** stops the game and returns to the start screen at any time.

## Code layout

- `commands.py` — the "Simon says" actions, each paired with a gesture move name.
- `gestures.py` — plays a named move from Pollen Robotics' built-in emotions library (forked
  from `apps/voice_gesture/voice_gesture/emotion_to_gesture.py`, keyed by move name instead of
  emotion tag).
- `game.py` — the round/timer/trick/score state machine. Pure logic, no I/O — see its own
  docstring for the event protocol `main.py` drives it with. This is what `test_game.py` exercises
  directly, with an injectable clock/rng, no real sleeping or hardware needed.
- `main.py` — the `ReachyMiniApp` itself: FastAPI routes (`/state`, `/start`, `/confirm`,
  `/reset`, `/config`, `/voices`, `/voice`, `/volume`, `/connection`) and the loop that turns
  `game.py`'s state transitions into actual TTS + gesture calls. `/connection` (physical/sim
  toggle) works by calling `stop()` and having `__main__`'s loop reconnect with a fresh
  `ReachySays` instance — see the docstrings on `_make_app()` and the `__main__` block.
- `tts/` — forked wholesale from `voice_gesture/tts/` (Piper only).

## Tests

```bash
pytest reachy_says/
```

`test_game.py` and `test_commands.py` need no hardware. `test_endpoints.py` runs the app's real
FastAPI routes against a fake robot (real TTS still runs, since it needs no hardware either).
`test_connection_kwargs.py` covers the physical/sim `.env` toggle.
