param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Repo = 'wisdomWindy/voice-smith',
    [string]$RuntimeDir = "$PSScriptRoot\..\.cache\pyinstaller-dist\voicesmith-engine",
    [string]$EngineRoot = "$env:APPDATA\com.voicesmith.desktop\engine\GPT-SoVITS",
    [string]$AsrRoot = "$env:APPDATA\com.voicesmith.desktop\models\faster-whisper",
    [string]$ReleaseDir = "$PSScriptRoot\..\.cache\tauri-target\release",
    [string]$OutDir = "$PSScriptRoot\..\dist-assets",
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
    & "$PSScriptRoot\build-runtime-pack.ps1" -RuntimeDir $RuntimeDir -OutFile "$OutDir\VoiceSmith-Runtime.7z"
    & "$PSScriptRoot\build-assets-pack.ps1" -EngineRoot $EngineRoot -AsrRoot $AsrRoot -OutFile "$OutDir\VoiceSmith-Offline-Assets.7z"
}
& "$PSScriptRoot\split-release-assets.ps1" -Version $Version -OutDir $OutDir -Repo $Repo

$setup = Join-Path $OutDir "VoiceSmith-$Version-Setup.exe"
if (!(Test-Path $setup)) { throw "missing setup: $setup" }
$upload = @($setup)
$upload += Get-ChildItem $OutDir -File | Where-Object {
    $_.Name -match '^(runtime|assets)\.part\d+$' -or $_.Name -match '^(runtime|assets)-manifest\.json$'
} | Select-Object -ExpandProperty FullName
$notes = @"
VoiceSmith $Version

- Thin installer: UI + sidecar launcher + 7zr
- Runtime pack: 2 parts, installs Python/PyTorch/CUDA sidecar
- Offline assets: 2 parts, GPT-SoVITS engine + V4 weights + ASR + UVR5 + ffmpeg
- First launch: runtime manifest -> assets manifest
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
