param(
  [string]$Python = "C:\Users\yangjianlin\.voicesmith\venv\Scripts\python.exe",
  [string]$Work = "C:\Users\yangjianlin\.voicesmith\pyinstaller-build",
  [string]$Dist = "C:\Users\yangjianlin\.voicesmith\pyinstaller-dist",
  [switch]$InstallToResources
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& $Python -m PyInstaller --noconfirm --clean --log-level WARN `
  --workpath $Work --distpath $Dist sidecar\voicesmith-engine.spec

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$source = Join-Path $Dist "voicesmith-engine"
Write-Host "built: $source"

if ($InstallToResources) {
  $target = Join-Path $root "sidecar\voicesmith-engine"
  if (Test-Path $target) { Remove-Item $target -Recurse -Force }
  Copy-Item $source $target -Recurse
  Write-Host "copied to: $target"
}
