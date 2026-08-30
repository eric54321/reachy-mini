---
title: Voice Gesture
emoji: 👋
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: Reachy speaks with a picked voice and moves its head to match the mood.
tags:
 - reachy_mini
 - reachy_mini_python_app
---

See [../../reachy-voice-app-plan.md](../../reachy-voice-app-plan.md) for the full plan and progress log.

## One-time setup

From this folder (`apps/voice_gesture/`), in the `reachy` conda env (see [../../SETUP.md](../../SETUP.md)):

```bash
pip install -e .
```

This installs `piper-tts`, `python-dotenv`, `requests`, etc., and lets `python -m voice_gesture.main`
run from anywhere without extra `PYTHONPATH` setup.

If the Piper voice models aren't downloaded yet (`voices/*.onnx` — gitignored, not part of the repo):

```bash
python -m piper.download_voices en_US-lessac-medium en_US-amy-medium en_US-ryan-medium en_GB-alan-medium en_US-kristin-medium --download-dir voices
```

(`en_US-lessac-medium` is the default and required; the other four are optional extras the UI's
voice dropdown will also show if present.)

## Starting the app

**Against the physical robot** (default — nothing extra needed, assuming the robot is powered on
and reachable):

```bash
python -m voice_gesture.main
```

**Against a local simulator instead:** first start a sim daemon in its own terminal —

```bash
reachy-mini-daemon --sim --fastapi-port 8090
```

(drop `--fastapi-port 8090` and use the default 8000 if that port is free on your machine — see
[../../SETUP.md](../../SETUP.md)'s "Running the daemon" section for why 8090 is used here. Add
`--headless` if you don't want the MuJoCo viewer window to pop up.)

Then copy [../../.env.example](../../.env.example) to `../../.env` and set:

```
REACHY_MINI_MODE=sim
REACHY_MINI_SIM_PORT=8090   # match whatever port you started the sim daemon on
```

...and run the app the same way:

```bash
python -m voice_gesture.main
```

Switch back to the physical robot later by setting `REACHY_MINI_MODE=physical` in `.env` (or
just deleting `.env`, since physical is the default).

In either mode, once running, the app:
- wakes the robot up (or sim) on startup
- prints `Uvicorn running on http://0.0.0.0:8042` once the settings UI is ready
- puts it back to sleep when you stop the app (Ctrl+C)

## Using the UI

Open the settings page in a browser:

- `http://localhost:8042` on the machine running the app
- `http://<that machine's LAN IP>:8042` from another device on the same WiFi (e.g. a phone)

On the page:

1. **Voice** — pick which downloaded Piper voice to speak with.
2. **Volume** — drag the slider to set the robot's speaker volume (0–100).
3. **Insert emotion tag** — pick one of the 20 emotion tags from the dropdown and click
   **Insert** to drop `[tag] ` into the message box at the cursor. Available tags: `angry`,
   `annoyed`, `bored`, `confused`, `curious`, `disgusted`, `excited`, `grateful`, `happy`,
   `laughing`, `lonely`, `loving`, `proud`, `relieved`, `sad`, `scared`, `shy`, `surprised`,
   `thoughtful`, `tired`.
4. **Message box** — type what you want Reachy to say. Tag any part of it with `[tag]` to set
   the mood for the sentences that follow, e.g. `[happy] Hi there! [curious] What's up?` — each
   sentence gets its own gesture.
5. **Say it** — sends the message. The status line below confirms which voice it queued with.

## Tests

```bash
pytest voice_gesture/
```
