param(
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\VoiceSmith-Runtime-base.7z",
    [string]$SevenZip = "$PSScriptRoot\..\sidecar\7zr.exe",
    [string]$PythonVersion = '3.11.9'
)

$ErrorActionPreference = 'Stop'
$stage = Join-Path $env:TEMP ("voicesmith-runtime-base-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$py = Join-Path $stage 'python'
$sidecar = Join-Path $stage 'sidecar'
New-Item -ItemType Directory -Force -Path $py, $sidecar | Out-Null

$zip = Join-Path $env:TEMP "python-$PythonVersion-embed-amd64.zip"
if (!(Test-Path $zip)) {
    Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile $zip
}
Expand-Archive $zip -DestinationPath $py -Force

# Enable site-packages and local dependency installs.
$pth = Get-ChildItem $py -Filter 'python*._pth' | Select-Object -First 1
if ($pth) {
    $lines = Get-Content $pth.FullName
    if ($lines -notcontains 'Lib\site-packages') { Add-Content $pth.FullName 'Lib\site-packages' }
    if ($lines -notcontains '..\sidecar') { Add-Content $pth.FullName '..\sidecar' }
}

# sidecar source (no virtualenv, no PyInstaller).
Copy-Item "$PSScriptRoot\..\sidecar\*.py" $sidecar -Force
Copy-Item "$PSScriptRoot\..\sidecar\*.txt" $sidecar -Force -ErrorAction SilentlyContinue
Copy-Item "$PSScriptRoot\..\sidecar\7zr.exe" $sidecar -Force

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
& $SevenZip a -t7z -mx=3 $OutFile (Join-Path $stage '*') | Out-Null
if ($LASTEXITCODE -ne 0) { throw "7z failed: $LASTEXITCODE" }
$hash = (Get-FileHash $OutFile -Algorithm SHA256).Hash.ToLower()
Write-Host "runtime-base=$OutFile size=$((Get-Item $OutFile).Length) sha256=$hash"
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
