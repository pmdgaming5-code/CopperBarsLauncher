$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$UpstreamDir = Join-Path $RepoRoot '.upstream\PrismLauncher'
$BuildDir = Join-Path $RepoRoot '.upstream\build'
$InstallDir = Join-Path $RepoRoot 'dist\CopperBarsLauncher'
$Commit = (Get-Content (Join-Path $RepoRoot 'UPSTREAM_PRISM_COMMIT') -Raw).Trim()

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command git
Require-Command cmake
Require-Command ninja

if (-not (Test-Path $UpstreamDir)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $UpstreamDir) | Out-Null
    git clone --recursive https://github.com/PrismLauncher/PrismLauncher.git $UpstreamDir
}

Push-Location $UpstreamDir
try {
    git fetch --tags origin develop
    git checkout --detach $Commit
    git submodule sync --recursive
    git submodule update --init --recursive
} finally {
    Pop-Location
}

if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$qt = $env:COPPERBARS_QT
if (-not $qt) { $qt = 'C:\Qt\6.9.2\msvc2022_64' }

$cmakeArgs = @(
    '-S', $UpstreamDir,
    '-B', $BuildDir,
    '-G', 'Ninja',
    '-DCMAKE_BUILD_TYPE=Release',
    "-DCMAKE_PREFIX_PATH=$qt",
    '-DLauncher_APP_BINARY_NAME=copperbarslauncher',
    '-DLauncher_BUILD_PLATFORM=copperbars-windows',
    '-DLauncher_UPDATER_GITHUB_REPO=https://github.com/pmdgaming5-code/CopperBarsLauncher',
    '-DLauncher_BUILD_ARTIFACT=CopperBarsLauncher-Windows-x64',
    '-DLauncher_META_URL=',
    '-DLauncher_IMGUR_CLIENT_ID=',
    '-DLauncher_MSA_CLIENT_ID=',
    '-DLauncher_CURSEFORGE_API_KEY=',
    '-DLauncher_BUG_TRACKER_URL=https://github.com/pmdgaming5-code/CopperBarsLauncher/issues',
    '-DLauncher_NEWS_RSS_URL=',
    '-DLauncher_NEWS_OPEN_URL=https://github.com/pmdgaming5-code/CopperBarsLauncher',
    '-DLauncher_WIKI_URL=https://github.com/pmdgaming5-code/CopperBarsLauncher/wiki',
    '-DLauncher_TRANSLATIONS_URL=',
    '-DLauncher_TRANSLATION_FILES_URL=',
    '-DLauncher_MATRIX_URL=',
    '-DLauncher_DISCORD_URL=',
    '-DLauncher_SUBREDDIT_URL=',
    '-DLauncher_ENABLE_JAVA_DOWNLOADER=ON',
    '-DBUILD_TESTING=ON'
)

Write-Host "Configuring CopperBars Launcher from Prism commit $Commit" -ForegroundColor Cyan
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw "CMake configuration failed." }

Write-Host 'Building CopperBars Launcher...' -ForegroundColor Cyan
& cmake --build $BuildDir --config Release --parallel
if ($LASTEXITCODE -ne 0) { throw "Build failed." }

Write-Host 'Installing portable build...' -ForegroundColor Cyan
& cmake --install $BuildDir --config Release --component portable --prefix $InstallDir
if ($LASTEXITCODE -ne 0) { throw "Install failed." }

$exe = Get-ChildItem -Path $InstallDir -Filter 'copperbarslauncher*.exe' -Recurse | Select-Object -First 1
if (-not $exe) { throw "Build succeeded but CopperBars executable was not found." }

Write-Host "SUCCESS: $($exe.FullName)" -ForegroundColor Green
