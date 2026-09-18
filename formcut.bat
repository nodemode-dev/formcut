@echo off
REM formcut.bat - Windows launcher. Same sequence as ./formcut: banner, install (idempotent), boot.
REM Every step lives in setup\; this file only sequences them.
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM Boot banner. Never allowed to fail the launch.
call "%ROOT%setup\formcut_banner.bat"

call "%ROOT%setup\formcut_oc_install.bat"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: installation failed. See the messages above.
    pause
    exit /b 1
)

call "%ROOT%setup\setup_local_ai.bat"
if %ERRORLEVEL% NEQ 0 echo Local speech runtime not installed; captions and editing still work. Re-run setup\setup_local_ai.bat later.

call "%ROOT%setup\formcut_boot.bat"
endlocal
