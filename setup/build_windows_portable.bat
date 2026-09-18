@echo off
REM on PATH by policy; they are checked at launch, never bundled.
REM UNTESTED-HERE: authored on Linux; run on a real Windows machine.
setlocal
cd /d %~dp0
set OUT=formcut-portable

echo [1/4] frontend
cd frontend
call npm ci --no-audit --no-fund || exit /b 1
call npm run build || exit /b 1
cd ..

echo [2/4] engine venv
python -m venv backend\.venv-portable || exit /b 1
call backend\.venv-portable\Scripts\pip install --upgrade pip
call backend\.venv-portable\Scripts\pip install -r backend\requirements.txt pyinstaller || exit /b 1

echo [3/4] freeze
cd backend
call .venv-portable\Scripts\python prepare_cv.py || exit /b 1
call .venv-portable\Scripts\python freeze.py || exit /b 1
cd ..

echo [4/4] assemble
if exist %OUT%\engine\portable (echo Move the existing portable folder before rebuilding to preserve its data. & exit /b 1)
if exist %OUT% rmdir /s /q %OUT%
mkdir %OUT%
xcopy /e /i /q backend\dist\formcut-engine %OUT%\engine >nul
mkdir %OUT%\engine\portable
REM The launcher pins FORMCUT_PORT to 8040 for simplicity; the set line must
REM precede the engine start or the pin never reaches the process.
(
echo @echo off
echo where ffmpeg ^>nul 2^>nul ^|^| ^(echo formcut needs ffmpeg on PATH ^& pause ^& exit /b 1^)
echo set FORMCUT_PORT=8040
echo start "formcut engine" /min "%%~dp0engine\formcut-engine.exe"
echo timeout /t 3 ^>nul
echo start http://127.0.0.1:8040
) > %OUT%\formcut.bat
echo portable folder ready: %OUT%
