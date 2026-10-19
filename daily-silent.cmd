@echo off
REM Versi tanpa jeda untuk Task Scheduler: tidak ada "pause", semua output
REM masuk ke data\logs\daily-YYYY-MM-DD.log
setlocal
cd /d "%~dp0"

if not exist "data\logs" mkdir "data\logs"
for /f "tokens=1-3 delims=/- " %%a in ('date /t') do set TODAY=%%c%%b%%a
set LOG=data\logs\daily-%TODAY%.log

set DEV_CHANNEL=1561725081095250023
set KREATIF_CHANNEL=1561730155158966363
set REMOTE_CHANNEL=1561733022368407623

echo ==== mulai %date% %time% ==== >> "%LOG%"

python -m jobhunter discover --per-board 40 --limit 900 >> "%LOG%" 2>&1
python -m jobhunter enrich --limit 30 --min-score 60 >> "%LOG%" 2>&1
python -m jobhunter analyze --limit 15 --min-score 75 >> "%LOG%" 2>&1
python -m jobhunter digest --limit 12 --min-fit 60 >> "%LOG%" 2>&1
python -m jobhunter toast --min-fit 75 >> "%LOG%" 2>&1
python -m jobhunter discord --per-job --public --only-new --exclude-feeds --limit 3 --min-fit 70 --tracks fullstack,it_support,ai_junior,admin_data --channel %DEV_CHANNEL% >> "%LOG%" 2>&1
python -m jobhunter discord --per-job --public --only-new --exclude-feeds --limit 2 --min-fit 75 --tracks marketing,video_editor,graphic_design,social_media --channel %KREATIF_CHANNEL% >> "%LOG%" 2>&1
python -m jobhunter discord --per-job --public --only-new --feeds-only --limit 3 --min-fit 60 --tracks fullstack,it_support,ai_junior,marketing,video_editor,graphic_design,social_media --channel %REMOTE_CHANNEL% >> "%LOG%" 2>&1
python -m jobhunter sync >> "%LOG%" 2>&1

echo ==== selesai %date% %time% ==== >> "%LOG%"
endlocal
