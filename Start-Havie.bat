@echo off
cd /d "%~dp0"
py -3 havie.py --gui
if errorlevel 1 pause
