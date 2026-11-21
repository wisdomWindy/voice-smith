param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Repo = 'wisdomWindy/voice-smith',
    [string]$WheelsCore = "$PSScriptRoot\..\.cache\wheels-core",
    [string]$WheelsTorch = "$PSScriptRoot\..\.cache\wheels-torch",
    [string]$WeightsRoot = $(
        if ($env:VOICE_SMITH_WEIGHTS_SRC) { $env:VOICE_SMITH_WEIGHTS_SRC }
        elseif (Test-Path 'D:\program\GPT-SoVITS-v5') { 'D:\program\GPT-SoVITS-v5' }
        else { "$env:APPDATA\com.voicesmith.desktop\engine\GPT-SoVITS" }
    ),
    [string]$AsrRoot = "$env:APPDATA\com.voicesmith.desktop\models\faster-whisper",
    [string]$ReleaseDir = "$PSScriptRoot\..\.cache\tauri-target\release",
    [string]$OutDir = "$PSScriptRoot\..\dist-assets",
    [string]$PythonVersion = '3.11.9',
    [switch]$SkipBuild,
    [switch]$SkipPacks
)

$ErrorActionPreference = 'Stop'
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (!(Test-Path $iscc)) { throw "Inno Setup not found: $iscc" }
if ((gh auth status 2>&1) -match 'not logged') { throw "gh is not logged in" }

if (!$SkipBuild) {
    pnpm tauri build --no-bundle
    if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }
    & $iscc "$PSScriptRoot\voicesmith.iss" "/DReleaseDir=$ReleaseDir" "/DOutputDir=$OutDir" "/DMyAppVersion=$Version"
    if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }
}
if (!$SkipPacks) {
    & "$PSScriptRoot\build-runtime-base.ps1" -OutFile "$OutDir\VoiceSmith-Runtime-base.7z" -PythonVersion $PythonVersion
    if ($LASTEXITCODE -ne 0) { throw "runtime base build failed" }
    & "$PSScriptRoot\build-deps-pack.ps1" -Kind core -WheelsDir $WheelsCore -OutFile "$OutDir\VoiceSmith-Deps-core.7z"
    if ($LASTEXITCODE -ne 0) { throw "core deps build failed" }
    & "$PSScriptRoot\build-deps-pack.ps1" -Kind torch -WheelsDir $WheelsTorch -OutFile "$OutDir\VoiceSmith-Deps-torch.7z"
    if ($LASTEXITCODE -ne 0) { throw "torch deps build failed" }
    & "$PSScriptRoot\build-assets-pack.ps1" -WeightsRoot $WeightsRoot -AsrRoot $AsrRoot -Version $Version -OutFile "$OutDir\VoiceSmith-Offline-Assets.7z"
    if ($LASTEXITCODE -ne 0) { throw "assets pack build failed" }
}
& "$PSScriptRoot\split-release-assets.ps1" -Version $Version -OutDir $OutDir -Repo $Repo

$setup = Join-Path $OutDir "VoiceSmith-$Version-Setup.exe"
if (!(Test-Path $setup)) { throw "missing setup: $setup" }
$upload = @($setup)
$upload += Get-ChildItem $OutDir -File | Where-Object {
    $_.Name -match '^(runtime-base|deps-core|deps-torch|assets)\.part\d+$' -or
    $_.Name -match '^(runtime-base|deps-core|deps-torch|assets)-manifest\.json$' -or
    $_.Name -eq 'runtime-bundle.json'
} | Select-Object -ExpandProperty FullName
$notes = @"
VoiceSmith $Version

- Thin installer: UI + vendored GPT-SoVITS engine source + sidecar launcher + 7zr
- Runtime bundle: embedded Python base + core wheels + torch/CUDA wheels
- First launch: runtime-bundle.json -> base/core/torch manifests -> bootstrap pip install -> sidecar app.py
- Offline assets: weights only (GPT/SoVITS/BERT/HuBERT/SV/G2PW/UVR5/FunASR/ffmpeg) installed into <data>/assets
"@
$notesPath = Join-Path $OutDir 'release-notes.md'
$notes | Set-Content $notesPath -Encoding UTF8
$existing = gh release view "v$Version" --repo $Repo 2>$null
if ($LASTEXITCODE -eq 0) {
    gh release upload "v$Version" $upload --repo $Repo --clobber
    if ($LASTEXITCODE -ne 0) { throw "gh release upload failed" }
} else {
    gh release create "v$Version" $upload --repo $Repo --title "VoiceSmith $Version" --notes-file $notesPath
    if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }
}
Write-Host "published v$Version"
