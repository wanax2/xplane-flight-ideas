@echo off
rem Starts the X-Plane Flight Ideas app.
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw xp_flight_ideas_gui.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw xp_flight_ideas_gui.py & exit /b)
where py >nul 2>nul && (py xp_flight_ideas_gui.py & exit /b)
where python >nul 2>nul && (python xp_flight_ideas_gui.py & exit /b)
echo Python was not found. Install it from https://www.python.org/downloads/
echo (tick "Add Python to PATH" in the installer), then run this again.
pause
