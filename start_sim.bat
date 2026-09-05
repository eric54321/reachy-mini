@echo off
REM Starts the Reachy Mini simulator daemon in its own window, with the
REM MuJoCo viewer visible (no --headless).
REM Port 8090 (not the default 8000) because port 8000 is unreliable on this
REM machine — see SETUP.md's "Running the daemon" section.
call conda activate reachy
start "Reachy Mini Sim Daemon" reachy-mini-daemon --sim --fastapi-port 8090

pause
