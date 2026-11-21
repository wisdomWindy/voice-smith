param(
    [Parameter(Mandatory = $true)][ValidateSet('core', 'torch')][string]$Kind,
    [Parameter(Mandatory = $true)][string]$WheelsDir,
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\VoiceSmith-Deps-$Kind.7z",
    [string]$SevenZip = "$PSScriptRoot\..\sidecar\7zr.exe"
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path $WheelsDir)) { throw "wheels not found: $WheelsDir" }
$wheels = Get-ChildItem $WheelsDir -Filter '*.whl' -File
if (!$wheels) { throw "no .whl files in $WheelsDir" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
$stage = Join-Path $env:TEMP ("voicesmith-deps-$Kind-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force -Path (Join-Path $stage $Kind) | Out-Null
Copy-Item $wheels.FullName (Join-Path $stage $Kind)
& $SevenZip a -t7z -mx=3 $OutFile (Join-Path $stage '*') | Out-Null
if ($LASTEXITCODE -ne 0) { throw "7z failed: $LASTEXITCODE" }
$hash = (Get-FileHash $OutFile -Algorithm SHA256).Hash.ToLower()
Write-Host "deps-$Kind=$OutFile size=$((Get-Item $OutFile).Length) sha256=$hash"
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
