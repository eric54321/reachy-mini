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

**Optional: pocket-tts (Kyutai) voices**, e.g. the `announcer` voice for quiz-show-style apps —
free and local like Piper, but pulls in `torch` so it's kept as an extra:

```bash
pip install -e ".[kyutai]"
```

No separate download step — voices are fetched from Hugging Face and cached automatically the
first time each one is used. The 26 built-in voices (`kyutai:alba`, `kyutai:marius`, etc.) work
immediately. Character voices like `kyutai:announcer` clone a real audio sample and need the
gated voice-cloning weights: accept the terms at https://huggingface.co/kyutai/pocket-tts and run
`uvx hf auth login`, or they'll raise a `ValueError` and pocket-tts silently falls back to the
non-cloning weights.

## TTS architecture

Text-to-speech lives in `voice_gesture/tts/`, structured to be reusable in other apps, not just
this one:

- `tts/piper_provider.py`, `tts/pocket_tts_provider.py` — one module per backend, each exposing
  `speak(sentence, voice_name) -> Path` and `list_available_voices() -> list[str]`. Neither module
  imports anything from the rest of `voice_gesture`, and each provider's heavy dependencies
  (e.g. `torch`) are only imported lazily inside `speak()` — so a provider you don't use doesn't
  need to be installed.
- `tts/base.py` — the `TTSProvider` protocol both modules follow (documentation/typing only).
- `tts/__init__.py` — the registry the rest of the app actually calls. Voice ids are namespaced as
  `"<provider>:<voice_name>"` (e.g. `"piper:en_US-lessac-medium"`, `"kyutai:announcer"`), so the
  picker UI and `/say` endpoint never need to know which backend is behind a given voice.

To reuse this in another app, copy the `tts/` folder wholesale and edit the `_PROVIDERS` dict in
`tts/__init__.py` to the backends you want.

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

1. **Voice** — pick which voice to speak with, shown as `provider:voice_name` (e.g.
   `piper:en_US-lessac-medium`, `kyutai:announcer`).
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
