param(
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\VoiceSmith-Runtime-base.7z",
    [string]$SevenZip = "$PSScriptRoot\..\sidecar\7zr.exe",
    [string]$PythonVersion = '3.11.9',
    [string]$PipVersion = '25.2'
)

# Runtime base = embedded CPython + pip + sidecar sources.
# The Rust installer flattens python/ into <install>\runtime and keeps
# sidecar/ as <install>\runtime\sidecar, then runs
#   runtime\python.exe sidecar\bootstrap.py
#   runtime\python.exe sidecar\app.py
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

# Enable site-packages and the sibling sidecar directory for the flat runtime
# layout (python.exe lives next to sidecar\ after installation).
$pth = Get-ChildItem $py -Filter 'python*._pth' | Select-Object -First 1
if ($pth) {
    $lines = @(Get-Content $pth.FullName | Where-Object { $_.Trim() -ne '..\sidecar' })
    if ($lines -notcontains 'Lib\site-packages') { $lines += 'Lib\site-packages' }
    if ($lines -notcontains 'sidecar') { $lines += 'sidecar' }
    Set-Content -Path $pth.FullName -Value $lines -Encoding ascii
}

# bootstrap.py shells out to `python -m pip`; the embeddable distribution does
# not ship pip, so install it into the staged runtime.
$pythonExe = Join-Path $py 'python.exe'
$getPip = Join-Path $env:TEMP 'voicesmith-get-pip.py'
if (!(Test-Path $getPip)) {
    Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile $getPip
}
& $pythonExe $getPip --no-warn-script-location --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip install failed: $LASTEXITCODE" }
if ($PipVersion) {
    & $pythonExe -m pip install --no-warn-script-location --disable-pip-version-check "pip==$PipVersion"
    if ($LASTEXITCODE -ne 0) { throw "pip pin failed: $LASTEXITCODE" }
}
& $pythonExe -m pip --version
if ($LASTEXITCODE -ne 0) { throw "pip is not usable in the staged runtime" }

# sidecar source (no virtualenv, no PyInstaller).
Copy-Item "$PSScriptRoot\..\sidecar\*.py" $sidecar -Force
Copy-Item "$PSScriptRoot\..\sidecar\*.txt" $sidecar -Force -ErrorAction SilentlyContinue
Copy-Item "$PSScriptRoot\..\sidecar\7zr.exe" $sidecar -Force
Copy-Item "$PSScriptRoot\..\sidecar\builtin_voices" $sidecar -Recurse -Force

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
& $SevenZip a -t7z -mx=3 $OutFile (Join-Path $stage '*') | Out-Null
if ($LASTEXITCODE -ne 0) { throw "7z failed: $LASTEXITCODE" }
$hash = (Get-FileHash $OutFile -Algorithm SHA256).Hash.ToLower()
Write-Host "runtime-base=$OutFile size=$((Get-Item $OutFile).Length) sha256=$hash"
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
