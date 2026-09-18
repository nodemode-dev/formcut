@echo off
REM formcut Windows installation. Idempotent: safe to run on every boot.
REM Lives in setup\; resolves the repo root itself, so it works from anywhere.
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "VER="
for /F "tokens=2 delims=:" %%v in ('findstr /C:"\"version\"" "%ROOT%\frontend\package.json"') do if not defined VER set "VER=%%v"
set "VER=%VER:"=%"
set "VER=%VER:,=%"
set "VER=%VER: =%"

echo ===========================================
echo formcut v%VER% - Windows Installation
echo ===========================================
echo.

where ffmpeg >nul 2>&1 || echo WARNING: ffmpeg is not on PATH. Import, preview and export need it.
where ffprobe >nul 2>&1 || echo WARNING: ffprobe is not on PATH. Import, preview and export need it.

echo ^>^> Setting up the engine...
cd /d "%ROOT%\backend"
call oc_install.bat
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: engine installation failed.
    exit /b 1
)

echo.
echo ^>^> Setting up the interface...
cd /d "%ROOT%\frontend"
call oc_install.bat
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: interface installation failed.
    exit /b 1
)

cd /d "%ROOT%"
if not exist "%ROOT%\.env" if exist "%ROOT%\example.env" (
    copy /Y "%ROOT%\example.env" "%ROOT%\.env" >nul
    echo.
    echo ^>^> Created .env from example.env. Keys go there; it is ignored by git.
)

echo.
echo ===========================================
echo Installation complete
echo ===========================================
echo.
echo Next steps:
echo   1. Add any keys to .env (PEXELS_API_KEY, ELEVENLABS_API_KEY); both are optional
echo   2. Run: formcut.bat
echo.
echo Optional extras:
echo   - setup\setup_local_ai.bat   local speech runtime, then install the voice model in Studio
echo   - Captions fetch their model in the browser on first use
echo.
endlocal
exit /b 0
