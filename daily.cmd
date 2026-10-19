@echo off
REM Daily pipeline: pull -> enrich -> analyze -> digest -> notify.
REM Double-click this file, or point Windows Task Scheduler at it.
cd /d "%~dp0"

echo [1/6] menarik lowongan...
python -m jobhunter discover --per-board 40 --limit 900

echo [2/6] mengunduh deskripsi lengkap...
python -m jobhunter enrich --limit 30 --min-score 60

echo [3/6] analisis kecocokan...
python -m jobhunter analyze --limit 15 --min-score 75

echo [4/6] menyusun digest...
python -m jobhunter digest --limit 12 --min-fit 60 --open

echo [5/6] notifikasi desktop...
python -m jobhunter toast --min-fit 75

echo [6/6] kirim ke Discord (kalau DISCORD_WEBHOOK_URL terisi)...
python -m jobhunter discord --only-new --limit 5 --min-fit 75

echo.
echo Selesai. Digest ada di data\digest\
pause
