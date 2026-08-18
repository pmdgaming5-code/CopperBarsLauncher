$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot
)

$programInfo = Join-Path $SourceRoot 'program_info\CMakeLists.txt'
if (-not (Test-Path $programInfo)) { throw "Prism program_info/CMakeLists.txt not found." }

$text = Get-Content $programInfo -Raw
$replacements = @(
    @('set(Launcher_CommonName "PrismLauncher")', 'set(Launcher_CommonName "CopperBarsLauncher")'),
    @('set(Launcher_DisplayName "Prism Launcher")', 'set(Launcher_DisplayName "CopperBars Launcher")'),
    @('set(Launcher_AppID "org.prismlauncher.PrismLauncher")', 'set(Launcher_AppID "com.copperbars.launcher")'),
    @('set(Launcher_Domain "prismlauncher.org")', 'set(Launcher_Domain "copperbarslauncher.dev")'),
    @('set(Launcher_Git "https://github.com/PrismLauncher/PrismLauncher")', 'set(Launcher_Git "https://github.com/pmdgaming5-code/CopperBarsLauncher")'),
    @('set(Launcher_ENVName "PRISMLAUNCHER" PARENT_SCOPE)', 'set(Launcher_ENVName "COPPERBARSLAUNCHER" PARENT_SCOPE)'),
    @('set(Launcher_Authors "MultiMC & Prism Launcher Contributors")', 'set(Launcher_Authors "CopperBars Launcher Contributors")')
)
foreach ($pair in $replacements) {
    if (-not $text.Contains($pair[0])) { throw "Expected Prism branding line not found: $($pair[0])" }
    $text = $text.Replace($pair[0], $pair[1])
}

Set-Content -Path $programInfo -Value $text -Encoding UTF8
Write-Host 'CopperBars branding applied.' -ForegroundColor Green
