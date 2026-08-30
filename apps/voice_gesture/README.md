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

## Running

```bash
python -m voice_gesture.main
```

Opens a settings UI at http://localhost:8042 — pick a voice, pick an emotion tag to insert,
adjust volume, type a message like `[happy] Hi there!`, click "Say it".

## Physical robot vs. simulator

Connects to the physical robot by default. To use a local simulator instead, copy
`../../.env.example` to `../../.env` and set:

```
REACHY_MINI_MODE=sim
REACHY_MINI_SIM_PORT=8090   # whatever port your `reachy-mini-daemon --sim --headless` uses
```

(mDNS doesn't resolve `reachy-mini.local` on this network, so both modes connect by
explicit host + port rather than relying on auto-discovery — see `_connection_kwargs()`
in `voice_gesture/main.py`.)

## Tests

```bash
pytest voice_gesture/
```