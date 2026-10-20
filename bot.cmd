@echo off
REM Start bot di background (tanpa jendela menganggur).
REM Tutup jendela ini tidak mematikan bot.
cd /d "%~dp0"

echo Mendaftarkan /cari (aman diulang)...
python -m jobhunter bot --register

echo.
echo Menjalankan bot...
python -m jobhunter bot --start

timeout /t 5 >nul
echo.
python -m jobhunter bot --status

echo.
echo Perintah lain:
echo   python -m jobhunter bot --stop     hentikan
echo   python -m jobhunter bot --status   cek hidup
pause
