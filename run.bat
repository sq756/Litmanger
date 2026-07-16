@echo off
cd /d "%~dp0"

set "PYTHON="
for %%c in (python python3 py) do (
    where %%c >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON=%%c"
        goto :found
    )
)

echo [ERROR] Python not found on your system.
echo.
echo Please install Python 3.9+ from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo.
goto :end

:found
echo Litmanger -- starting...
echo.

%PYTHON% -m litmanger server 2>nul && goto :end
%PYTHON% server.py 2>nul && goto :end

echo [ERROR] Failed to start. Check that you are in the Litmanger directory.
echo If downloaded as ZIP, make sure to extract all files first.

:end
pause
