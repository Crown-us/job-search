@echo off
REM Daily pipeline: pull -> enrich -> analyze -> digest -> notify.
REM Double-click this file, or point Windows Task Scheduler at it.
cd /d "%~dp0"

set DEV_CHANNEL=1561725081095250023
set KREATIF_CHANNEL=1561730155158966363
set REMOTE_CHANNEL=1561733022368407623

echo [1/9] menarik lowongan...
python -m jobhunter discover --per-board 40 --limit 900

echo [2/9] mengunduh deskripsi lengkap...
python -m jobhunter enrich --limit 30 --min-score 60

echo [3/9] analisis kecocokan...
python -m jobhunter analyze --limit 15 --min-score 75

echo [4/9] menyusun digest...
python -m jobhunter digest --limit 12 --min-fit 60 --open

echo [5/9] notifikasi desktop...
python -m jobhunter toast --min-fit 75

echo [6/9] feed publik: dev-it...
python -m jobhunter discord --per-job --public --only-new --exclude-feeds --max-age-days 30 --limit 3 --min-fit 70 --tracks fullstack,it_support,ai_junior,admin_data --channel %DEV_CHANNEL%

echo [7/9] feed publik: kreatif...
python -m jobhunter discord --per-job --public --only-new --exclude-feeds --max-age-days 30 --limit 2 --min-fit 75 --tracks marketing,video_editor,graphic_design,social_media --channel %KREATIF_CHANNEL%

echo [8/9] feed publik: remote...
python -m jobhunter discord --per-job --public --only-new --feeds-only --max-age-days 45 --limit 3 --min-fit 60 --tracks fullstack,it_support,ai_junior,marketing,video_editor,graphic_design,social_media --channel %REMOTE_CHANNEL%

echo [9/9] baca reaksi Discord...
python -m jobhunter sync

echo.
echo Selesai. Digest ada di data\digest\
pause
