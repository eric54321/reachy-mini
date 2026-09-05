@echo off
REM Force-stops the Reachy Says app started by start_app.bat. Prefer Ctrl-C
REM in that window instead when you can — this is a fallback for when you
REM can't. Targeted by command line so it doesn't touch unrelated python.exe
REM processes (e.g. the reachy-mini-mcp server also runs as python.exe).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*reachy_says.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

pause
