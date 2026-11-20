param(
    [string]$RuntimeDir = "$PSScriptRoot\..\.cache\pyinstaller-dist\voicesmith-engine",
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\VoiceSmith-Runtime.7z",
    [string]$SevenZip = "$env:USERPROFILE\.voicesmith\7ztools\7zr.exe"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path (Join-Path $RuntimeDir 'voicesmith-engine.exe'))) { throw "sidecar not found: $RuntimeDir" }
if (!(Test-Path $SevenZip)) { throw "7zr not found: $SevenZip" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
Copy-Item "$PSScriptRoot\..\sidecar\7zr.exe" (Join-Path $RuntimeDir '7zr.exe') -Force
& $SevenZip a -t7z -mx=3 -mmt=on $OutFile (Join-Path $RuntimeDir '*')
if ($LASTEXITCODE -ne 0) { throw "7z failed: $LASTEXITCODE" }
$hash = (Get-FileHash $OutFile -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $OutFile).Length
Write-Host "runtime=$OutFile"
Write-Host "size=$size"
Write-Host "sha256=$hash"

