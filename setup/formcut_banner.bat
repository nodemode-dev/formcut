@echo off
REM formcut_banner.bat - boot banner for formcut (Windows).
REM Self-contained: pure cmd. Mirrors setup/formcut_banner.
REM   FORMCUT_BANNER=0            suppress the banner
REM   NO_COLOR=1                  monochrome
REM   FORMCUT_VERSION=v0.52.1     version shown under the wordmark (default: frontend\package.json)
setlocal EnableDelayedExpansion
if "%FORMCUT_BANNER%"=="0" exit /b 0

set "ROOT=%~dp0.."
set "ACCENT=" & set "DIM=" & set "RESET="
if not defined NO_COLOR (
    for /F "delims=" %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
    set "ACCENT=!ESC![38;2;203;245;63m"
    set "DIM=!ESC![38;2;115;115;115m"
    set "RESET=!ESC![0m"
)

set "VER=%FORMCUT_VERSION%"
if not defined VER if exist "%ROOT%\frontend\package.json" (
    for /F "tokens=2 delims=:" %%v in ('findstr /C:"\"version\"" "%ROOT%\frontend\package.json"') do (
        if not defined VER set "VER=%%v"
    )
    if defined VER (
        set "VER=!VER:"=!"
        set "VER=!VER:,=!"
        set "VER=!VER: =!"
        set "VER=v!VER!"
    )
)

echo.
echo !ACCENT!  __                                 _!RESET!
echo !ACCENT! / _^| ___  _ __ _ __ ___   ___ _   _^| ^|_!RESET!
echo !ACCENT!^| ^|_ / _ \^| '__^| '_ ` _ \ / __^| ^| ^| ^| __^|!RESET!
echo !ACCENT!^|  _^| (_) ^| ^|  ^| ^| ^| ^| ^| ^| (__^| ^|_^| ^| ^|_!RESET!
echo !ACCENT!^|_^|  \___/^|_^|  ^|_^| ^|_^| ^|_^|\___^|\__,_^|\__^|!RESET!
echo !DIM!-----------------------------------------!RESET!
if defined VER (
    echo !DIM!    local-first video editor  ^|  !VER!!RESET!
) else (
    echo !DIM!    local-first video editor!RESET!
)
echo.
endlocal
exit /b 0
