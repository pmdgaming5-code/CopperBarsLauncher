$ErrorActionPreference = 'Stop'
python -m pip install --upgrade pip
python -m pip install pyinstaller pytest
pytest -q
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name CopperBarsLauncher launcher.py
if (-not (Test-Path 'dist/CopperBarsLauncher.exe')) { throw 'Launcher EXE üretilemedi.' }
