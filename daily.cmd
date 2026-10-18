@echo off
REM Daily pipeline: pull -> enrich -> analyze -> digest.
REM Double-click this file, or point Windows Task Scheduler at it.
cd /d "%~dp0"

echo [1/4] menarik lowongan...
python -m jobhunter discover --per-board 40 --limit 900

echo [2/4] mengunduh deskripsi lengkap...
python -m jobhunter enrich --limit 30 --min-score 60

echo [3/4] analisis kecocokan...
python -m jobhunter analyze --limit 15 --min-score 75

echo [4/4] menyusun digest...
python -m jobhunter digest --limit 12 --min-fit 60 --open

echo.
echo Selesai. Digest ada di data\digest\
pause
