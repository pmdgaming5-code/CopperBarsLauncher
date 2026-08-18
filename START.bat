@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 launcher.py
    exit /b %errorlevel%
)
where python >nul 2>&1
if %errorlevel% equ 0 (
    python launcher.py
    exit /b %errorlevel%
)
echo Python 3.11 veya daha yeni bir surum bulunamadi.
echo https://www.python.org/downloads/ adresinden Python kurup tekrar deneyin.
pause
