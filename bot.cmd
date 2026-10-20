@echo off
REM Jalankan bot slash-command. Biarkan jendela ini terbuka selama mau dipakai.
REM Tutup jendela = bot mati = /cari berhenti menjawab.
cd /d "%~dp0"

echo Mendaftarkan /cari (aman diulang)...
python -u -m jobhunter bot --register

echo.
echo Bot jalan. Tekan Ctrl+C untuk berhenti.
python -u -m jobhunter bot
pause
