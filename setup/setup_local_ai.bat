@echo off
cd /d "%~dp0backend"
python setup_local_ai.py
exit /b %errorlevel%
