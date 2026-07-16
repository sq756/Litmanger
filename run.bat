@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"

if "%~1"=="" goto menu
if /i "%~1"=="server" goto server
if /i "%~1"=="html" goto html
if /i "%~1"=="list" goto list
if /i "%~1"=="watch" goto watch

rem Treat argument as a URL
python -m litmanger "%~1"
goto end

:menu
echo.
echo   Litmanger
echo   ---------
echo.
echo   Type: server   to start the dashboard
echo         list     to list all papers
echo         html     to generate static HTML
echo         watch    to auto-archive downloaded PDFs
echo         ^<URL^>    to add a paper
echo.
set /p INPUT="^> "
if "!INPUT!"=="" exit /b

rem Strip "run " prefix if user typed it
set "CMD=!INPUT!"
if /i "!CMD:~0,4!"=="run " set "CMD=!CMD:~4!"

if /i "!CMD!"=="server" goto server
if /i "!CMD!"=="list"   goto list
if /i "!CMD!"=="html"   goto html
if /i "!CMD!"=="watch"  goto watch
python -m litmanger "!CMD!"
goto end

:server
start python -m litmanger server
timeout /t 2 >nul
start http://127.0.0.1:8765
goto end

:html
python -m litmanger html
start "" "%ROOT%paper_library.html"
goto end

:list
python -m litmanger list
goto end

:watch
echo Watching Downloads folder for new PDFs...
powershell -ExecutionPolicy Bypass -File "%ROOT%watch_downloads.ps1"
goto end

:end
pause
