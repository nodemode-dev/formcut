@echo off
REM formcut boot (Windows): the engine and the interface, each in its own window.
REM Lives in setup\; resolves the repo root itself.
setlocal EnableDelayedExpansion
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "VER="
for /F "tokens=2 delims=:" %%v in ('findstr /C:"\"version\"" "%ROOT%\frontend\package.json"') do if not defined VER set "VER=%%v"
set "VER=%VER:"=%"
set "VER=%VER:,=%"
set "VER=%VER: =%"

echo ===========================================
echo formcut v%VER% - Boot
echo ===========================================
echo.

if not exist "%ROOT%\backend\venv" (
    echo ERROR: the engine is not installed. Run setup\formcut_oc_install.bat
    pause
    exit /b 1
)
if not exist "%ROOT%\frontend\node_modules" (
    echo ERROR: the interface is not installed. Run setup\formcut_oc_install.bat
    pause
    exit /b 1
)

REM Keys and paths reach the engine through the environment, never the interface.
if exist "%ROOT%\.env" (
    for /F "usebackq tokens=1,* delims==" %%a in ("%ROOT%\.env") do (
        echo %%a| findstr /b "#" >nul || if not "%%a"=="" set "%%a=%%b"
    )
) else (
    echo No .env found. Copy example.env to .env for keys and paths; both are optional.
    echo.
)

echo Booting the engine...
start "formcut engine" cmd /k "cd /d "%ROOT%\backend" && boot_backend.bat"

timeout /t 2 /nobreak >nul

echo Booting the interface...
start "formcut interface" cmd /k "cd /d "%ROOT%\frontend" && boot_frontend.bat"

echo.
echo ===========================================
echo     Services running:
echo     - Engine:    http://127.0.0.1:8040
echo     - Interface: http://localhost:3040
echo ===========================================
echo.
echo Close either window to stop that half.
endlocal
exit /b 0
