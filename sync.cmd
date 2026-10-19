@echo off
REM Sinkronisasi reaksi saja: ringan, aman dijalankan tiap beberapa jam.
setlocal
cd /d "%~dp0"
if not exist "data\logs" mkdir "data\logs"
python -m jobhunter sync >> "data\logs\sync.log" 2>&1
endlocal
