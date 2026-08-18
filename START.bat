@echo off
setlocal
cd /d "%~dp0"
set "EXE=%~dp0dist\CopperBarsLauncher\copperbarslauncher.exe"

if exist "%EXE%" (
    start "CopperBars Launcher" "%EXE%"
    exit /b 0
)

where pwsh >nul 2>&1
if %errorlevel% equ 0 (
    echo CopperBars Launcher buildi baslatiliyor...
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\build-prism.ps1"
    if errorlevel 1 (
        echo.
        echo Build basarisiz oldu. Yukaridaki hatayi kontrol edin.
        pause
        exit /b 1
    )
    if exist "%EXE%" (
        start "CopperBars Launcher" "%EXE%"
        exit /b 0
    )
)

where powershell >nul 2>&1
if %errorlevel% equ 0 (
    echo CopperBars Launcher buildi baslatiliyor...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\build-prism.ps1"
    if errorlevel 1 (
        echo.
        echo Build basarisiz oldu. Yukaridaki hatayi kontrol edin.
        pause
        exit /b 1
    )
    if exist "%EXE%" (
        start "CopperBars Launcher" "%EXE%"
        exit /b 0
    )
)

echo PowerShell bulunamadi. Windows PowerShell veya PowerShell 7 gereklidir.
pause
exit /b 1
