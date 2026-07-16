@echo off
cd /d "%~dp0"

:: Detect Python
set "PYTHON="
for %%c in (python python3 py) do (
    where %%c >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON=%%c"
        goto :pyfound
    )
)

:: No Python - try standalone exe
if exist "Litmanger.exe" (
    echo Starting Litmanger...
    start "" "Litmanger.exe"
    start http://127.0.0.1:8766
    goto :end
)

echo [ERROR] Python not found.
echo.
echo Option 1: Install Python 3.9+ from https://www.python.org/downloads/
echo Option 2: Download the standalone exe from the GitHub releases page
echo.
goto :end

:pyfound
echo Litmanger starting...
echo.
%PYTHON% server.py

:end
