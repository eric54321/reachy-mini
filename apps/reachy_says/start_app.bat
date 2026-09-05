@echo off
REM Starts the Reachy Says game app in its own window. Settings UI ends up
REM at http://localhost:8043. Needs `pip install -e .` already run once in
REM this folder (see README.md).
REM
REM To stop: Ctrl-C in that window (graceful shutdown — main.py handles
REM KeyboardInterrupt itself, putting the robot back to sleep). stop_app.bat
REM is a force-kill fallback if the window isn't handy.
cd /d %~dp0
call conda activate reachy
start "Reachy Says App" python -m reachy_says.main

pause
