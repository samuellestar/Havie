@echo off
cd /d "%~dp0"
py -3 havie.py --phone --host 0.0.0.0
if errorlevel 1 pause
