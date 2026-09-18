@echo off
cd /d "%~dp0..\backend"
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
"%PY%" setup_local_ai.py
exit /b %errorlevel%
