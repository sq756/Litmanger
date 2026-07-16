@echo off
setlocal

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
echo   run server     Start dashboard
echo   run list       List all papers
echo   run html       Generate static HTML
echo   run watch      Auto-archive downloaded PDFs
echo   run ^<URL^>      Add a paper
echo.
set /p URL="Paste paper URL (or command): "
if "%URL%"=="" exit /b

if /i "%URL%"=="server" goto server
if /i "%URL%"=="list"   goto list
if /i "%URL%"=="html"   goto html
if /i "%URL%"=="watch"  goto watch
python -m litmanger "%URL%"
goto end

:server
start python -m litmanger server
timeout /t 2 >nul
start http://127.0.0.1:8765
goto end

:html
python -m litmanger --html
start "" "%ROOT%paper_library.html"
goto end

:list
python -m litmanger --list
goto end

:watch
echo Watching Downloads folder for new PDFs...
powershell -ExecutionPolicy Bypass -File "%ROOT%watch_downloads.ps1"
goto end

:end
pause
