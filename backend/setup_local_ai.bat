@echo off
cd /d "%~dp0"
python setup_local_ai.py
if errorlevel 1 pause
