# Reachy Mini Dev Environment Setup (Windows)

Captures what it actually took to get this working on this machine, so it can be
repeated elsewhere without re-discovering the same bugs.

There are two separate Python environments in play, kept isolated on purpose:

| Env | Purpose | Location |
|---|---|---|
| `reachy` (conda) | Your own scripts (`hello_world.py`, `test_movements.py`) | `conda env` named `reachy` |
| `reachy-mini-mcp/.venv` (uv) | The MCP server Claude Code/Desktop talks to | `../reachy-mini-mcp/.venv` (sibling of this folder, not nested inside it) |

Kept separate so the MCP server's extra deps (`torch` + `pocket-tts` for TTS, ~600MB+)
don't bloat the conda env you actually write code in. Downside: both environments
need the fixes below applied independently, and both need `reachy_mini` kept in sync
if you ever upgrade one.

## Prerequisites

- Python 3.10–3.12 (`uv python install 3.12 --default` if using `uv`)
- `uv` (https://astral.sh/uv) for the MCP server env
- Git + Git LFS
- Same network as the robot if using a wireless Reachy Mini, OR run in simulation
  (`--sim`) if no physical robot is reachable

## A. Direct SDK env (conda)

```bash
conda create -n reachy python=3.12 -y
conda activate reachy
pip install "reachy-mini[mujoco]"   # [mujoco] only needed if you'll run simulation
```

Test with `hello_world.py`:

```python
from reachy_mini import ReachyMini

with ReachyMini() as mini:
    mini.goto_target(antennas=[0.5, -0.5], duration=0.5)
```

## B. MCP server env (isolated uv venv)

```bash
cd reachy-mini-mcp   # sibling of reachy-mini, not nested inside it
uv venv --python 3.10
.venv\Scripts\activate
uv pip install -e .
uv pip install -e ".[tts]"
```

**Note:** the MCP server's own README says `.[speech]` for the TTS extra — that's
stale. Check `pyproject.toml`'s `[project.optional-dependencies]`; the extra is
actually named `tts` (`pocket-tts` + `scipy`).

## Known bug: `libexpat.dll` crash (Windows only)

**Symptom:** importing `reachy_mini`, or running `reachy-mini-daemon`, crashes on
`pyexpat` (part of the Python stdlib) failing to load its DLL — no Python traceback,
looks like a corrupted install.

**Root cause:** the `gstreamer_libs` package (a `reachy_mini` dependency) bundles its
own `libexpat.dll` and ships a `.pth` file (`gstreamer_bundle.pth`) that prepends its
`bin/` directory onto `PATH` at every interpreter startup. Windows then resolves
`pyexpat`'s DLL load to GStreamer's copy instead of the interpreter's own — and that
build is incompatible, so it crashes.

**Fix:** rename the shadowing DLL so the loader falls back to the correct one. This
must be done in **every** environment that has `reachy_mini` installed — fixing one
doesn't fix the other:

```
<conda_envs_dir>\reachy\Lib\site-packages\gstreamer_libs\bin\libexpat.dll   -> libexpat.dll.bak
reachy-mini-mcp\.venv\Lib\site-packages\gstreamer_libs\bin\libexpat.dll     -> libexpat.dll.bak
```

Reversible (rename back if something regresses). It **will recur** if `gstreamer_libs`
(or a package that pulls it in) is reinstalled/upgraded in either env — same one-line
rename fixes it again. See `fix_libexpat.ps1` in this folder to apply it automatically.

## Running the daemon

**Wireless Reachy Mini:** nothing to do — the daemon runs on-device automatically
when the robot powers on. Your computer just needs to be on the same network; the
SDK's `connection_mode="auto"` finds it via mDNS (hostname `reachy-mini`).

**Simulation (no physical robot, or local testing):**

```bash
reachy-mini-daemon --sim --headless --fastapi-port 8090
```

Or from the repo root: `start_sim.bat` (opens it in its own window, viewer visible — no
`--headless`). To stop it, Ctrl-C in that window (graceful shutdown); `stop_sim.bat` is a
force-kill fallback for when you don't have the window handy.

- `--headless` is only needed in a non-interactive shell (no display) — without it there,
  MuJoCo tries to open a GUI/OpenGL window and crashes. `start_sim.bat` runs interactively,
  so it leaves the viewer window on.
- Don't assume port 8000 is free. On this machine it's blocked by Windows' IP Helper
  service (`WinError 10013`, access-denied rather than "in use") and separately has a
  `netsh portproxy` rule forwarding it to WSL2. Check `netstat -ano | findstr :8000`
  (and whatever port you pick) before committing to it — 8090 was free here, but that's
  machine-specific.
- Verify with `http://localhost:<port>/docs`.
- Runs in the foreground — needs its own terminal window kept open (or a
  Task Scheduler/NSSM entry if you want it persistent across reboots).

## Registering the MCP server

Add to the project's `.mcp.json`:

```json
"reachy-mini": {
  "type": "stdio",
  "command": "<absolute-path-to>\\reachy-mini-mcp\\.venv\\Scripts\\reachy-mini-mcp.exe",
  "env": {
    "REACHY_MINI_ROBOT_NAME": "reachy-mini",
    "REACHY_MINI_ENABLE_CAMERA": "false"
  }
}
```

**Restart Claude Code with a brand-new session** (not "resume/continue") after editing
`.mcp.json` — MCP servers connect once at session startup, and a resumed session
won't pick up a new entry.

## Known bug: `uv` trampoline breaks if the venv's folder moves/renames

**Symptom:** running any exe in `reachy-mini-mcp/.venv/Scripts/` (e.g.
`reachy-mini-mcp.exe`) fails with `error: uv trampoline failed to canonicalize
script path`. In Claude Code this shows up as the `reachy-mini` MCP server
failing to connect (`CONNECTION_CLOSED`).

**Root cause:** `uv`'s generated exe shims embed an absolute path to the
installed package at install time. If the containing folder is later moved or
renamed, the shim can't resolve it anymore.

**Fix:** reinstall in place so `uv` regenerates the shims with the current path:

```bash
cd reachy-mini-mcp
uv pip install -e . --python .venv/Scripts/python.exe --reinstall-package reachy-mini-mcp
```

Needed again any time this folder (or `reachy-mini/`, if nested differently)
is moved.

## Gotchas

- **One controller at a time.** Don't run a direct script (`hello_world.py`) while the
  MCP server also has an active connection — both send target poses to the robot
  concurrently and will fight, causing jittery motion.
- A version-string mismatch warning (e.g. SDK reports `1.10.0`, daemon self-reports
  `1.9.0`) has been harmless in practice here — check both installed package versions
  actually match before assuming a real problem.
