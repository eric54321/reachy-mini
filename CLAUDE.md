# Reachy Mini — Claude Code Context

## What This Is
A wireless Reachy Mini robot (Pollen Robotics / Hugging Face) dev environment and
collection of experiments, kept as one repo for simplicity while learning the SDK
together. Not yet a "finished app" — if something here matures into a real
publishable app, it'll get split out into its own repo (each `apps/<name>/`
subfolder is already self-contained for exactly that reason).

## Team
- **Dad (Eric)** — env setup, SDK plumbing, MCP server integration
- **Sons** — experiments in `scripts/`, `apps/`, `web/`

## Setup
See [SETUP.md](SETUP.md) for the full Windows dev environment writeup (two
isolated Python envs, the `libexpat.dll` Windows bug and its fix, daemon/port
gotchas, MCP server registration). Run `fix_libexpat.ps1` after any fresh
`reachy_mini` install on Windows.

## Environment variables
Don't hardcode per-machine values (robot hostname override, ports, tokens if any
API integration is added later). Copy [.env.example](.env.example) to `.env`
(gitignored) and read overrides from there instead. Nothing currently requires
one — the SDK finds the robot via mDNS by default (`connection_mode="auto"`,
hostname `reachy-mini`).

## Project Structure
```
scripts/          Loose experiment scripts run directly against the SDK
  hello_world.py       minimal connect + move
  test_movements.py    antenna/head/body movement sweep
  inspect_sdk.py       introspect SDK function signatures/source
  go_to_sleep.py        sleep pose
apps/             One self-contained app per subfolder (CLI-generated,
                  Hugging Face Spaces-compatible structure). Empty for now.
web/              Browser/WebRTC experiments (JS SDK). Empty for now.
SETUP.md          Full environment setup + known-bug writeups
fix_libexpat.ps1  Automates the libexpat.dll Windows fix
.env.example      Template for any future per-machine config
```

## Adding a new experiment
- One-off script: drop it in `scripts/`.
- A real app (visual identity, meant to be shared/published later): scaffold it
  with the Reachy Mini app-builder CLI into its own folder under `apps/<name>/`
  so it stays self-contained and splittable into its own repo later.
- Browser/WebRTC experiment: put it under `web/`.

## Gotchas (see SETUP.md for full detail)
- **One controller at a time** — don't run a direct script while the MCP server
  also holds a connection; both will fight over target poses.
- `libexpat.dll` Windows bug recurs any time `gstreamer_libs` is reinstalled in
  either Python env — rerun `fix_libexpat.ps1`.
- Moving/renaming `reachy-mini-mcp/` (sibling repo, not part of this one) breaks
  its `uv` exe shims — see SETUP.md's "uv trampoline" section to fix.

## Git Workflow
```powershell
git pull                          # always pull first
# make your changes
git add .
git commit -m "what you changed"
git push
```
