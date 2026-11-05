@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
for %%R in ("%HERE%..") do set "ROOT=%%~fR"
set "PY=%~1"
if "%PY%"=="" ( echo [lgpl-av] usage: setup\build_lgpl_av.bat ^<engine venv python^> & exit /b 1 )
set "FFMPEG_VERSION=8.0.3"
set "FFMPEG_SHA256=6136812ea6d4e68bdba27e33c2a94382711cdf4f8602ffef056ff792bd6f9818"
set "AV_VERSION=18.1.0"
if "%LGPL_FFMPEG_PREFIX%"=="" set "LGPL_FFMPEG_PREFIX=%ROOT%\backend\.lgpl-ffmpeg"
set "WORK=%ROOT%\backend\build\lgpl-ffmpeg"
set "MSYS=C:\msys64\usr\bin\bash.exe"
if not exist "%PY%" ( echo [lgpl-av] python not found: %PY% & exit /b 1 )
where cl >nul 2>nul || (
  for /f "usebackq delims=" %%V in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath`) do call "%%V\VC\Auxiliary\Build\vcvars64.bat" >nul
)
where cl >nul 2>nul || ( echo [lgpl-av] the MSVC compiler was not found; install Visual Studio Build Tools with C++ & exit /b 1 )
set "MSVC_BIN="
for /f "delims=" %%L in ('where cl') do if not defined MSVC_BIN set "MSVC_BIN=%%~dpL"
if not exist "%MSVC_BIN%link.exe" ( echo [lgpl-av] the MSVC linker was not found beside cl.exe in %MSVC_BIN% & exit /b 1 )
if not exist "%LGPL_FFMPEG_PREFIX%\include\libavcodec\avcodec.h" (
  if not exist "%MSYS%" ( echo [lgpl-av] MSYS2 was not found at C:\msys64; install it from https://www.msys2.org & exit /b 1 )
  if not exist "%WORK%" mkdir "%WORK%" || ( echo [lgpl-av] could not create %WORK% & exit /b 1 )
  set "MSYS2_PATH_TYPE=inherit"
  "%MSYS%" -l "%HERE:\=/%build_lgpl_ffmpeg_msvc" "%MSVC_BIN%." "%WORK%" "%LGPL_FFMPEG_PREFIX%" "%FFMPEG_VERSION%" "%FFMPEG_SHA256%" || ( echo [lgpl-av] the FFmpeg build failed & exit /b 1 )
)
findstr /m /c:"libavcodec license: LGPL" "%LGPL_FFMPEG_PREFIX%\bin\avcodec-*.dll" >nul || ( echo [lgpl-av] the FFmpeg in %LGPL_FFMPEG_PREFIX% is not LGPL & exit /b 1 )
set "INCLUDE=%LGPL_FFMPEG_PREFIX%\include;%INCLUDE%"
set "LIB=%LGPL_FFMPEG_PREFIX%\lib;%LGPL_FFMPEG_PREFIX%\bin;%LIB%"
set "PATH=%LGPL_FFMPEG_PREFIX%\bin;%PATH%"
echo [lgpl-av] building PyAV %AV_VERSION% from source against it
"%PY%" -m pip install --no-binary av --no-deps --force-reinstall --no-cache-dir "av==%AV_VERSION%" || exit /b 1
"%PY%" "%HERE%vendor_av_dlls.py" "%LGPL_FFMPEG_PREFIX%" || exit /b 1
"%PY%" "%HERE%check_lgpl_av.py" "%LGPL_FFMPEG_PREFIX%" || exit /b 1
exit /b 0
