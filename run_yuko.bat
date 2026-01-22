@echo off
cd /d "%~dp0"
call .venv_whisper\Scripts\activate.bat
python main.py