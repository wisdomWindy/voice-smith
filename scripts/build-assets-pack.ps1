param(
    # A GPT-SoVITS tree that still contains weights (local install, or the
    # upstream source dir). Only the weight/tool subdirectories are packed;
    # engine source is bundled from vendor/GPT-SoVITS by the installer.
    [string]$WeightsRoot = $(
        if ($env:VOICE_SMITH_WEIGHTS_SRC) { $env:VOICE_SMITH_WEIGHTS_SRC }
        elseif (Test-Path 'D:\program\GPT-SoVITS-v5') { 'D:\program\GPT-SoVITS-v5' }
        else { "$env:APPDATA\com.voicesmith.desktop\engine\GPT-SoVITS" }
    ),
    [string]$AsrRoot = "$env:APPDATA\com.voicesmith.desktop\models\faster-whisper",
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\VoiceSmith-Offline-Assets.7z",
    [string]$SevenZip = "$PSScriptRoot\..\sidecar\7zr.exe",
    [string]$Version = '0.3.0',
    [switch]$SkipOptional
)

# Pack layout (installed by sidecar/asset_install.py into <data>/assets):
#   gpt-sovits/GPT_SoVITS/pretrained_models/...   BERT, HuBERT, GPT/SoVITS, SV, langdetect
#   gpt-sovits/GPT_SoVITS/text/G2PWModel/...      G2PW frontend
#   gpt-sovits/tools/uvr5/uvr5_weights/...        UVR5 (optional)
#   gpt-sovits/tools/asr/models/...               FunASR (optional)
#   gpt-sovits/tools/AP_BWE_main/24kto48k/...     super sampling (optional)
#   bin/ffmpeg.exe, bin/ffprobe.exe
#   manifest.json                                 sizes + sha256
#
# The pack intentionally contains no engine source and no Python runtime.

$ErrorActionPreference = 'Stop'
if (!(Test-Path $WeightsRoot)) { throw "weights source not found: $WeightsRoot" }
if (!(Test-Path $SevenZip)) { throw "7zr not found: $SevenZip" }
if (!(Test-Path (Join-Path $WeightsRoot 'GPT_SoVITS\pretrained_models'))) {
    throw "weights source has no GPT_SoVITS/pretrained_models: $WeightsRoot"
}

$required = @(
    'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large',
    'GPT_SoVITS/pretrained_models/chinese-hubert-base',
    'GPT_SoVITS/pretrained_models/s1v3.ckpt',
    'GPT_SoVITS/pretrained_models/gsv-v5-pretrained',
    'GPT_SoVITS/pretrained_models/sv',
    'GPT_SoVITS/pretrained_models/fast_langdetect',
    'GPT_SoVITS/text/G2PWModel'
)
$optional = @(
    'tools/uvr5/uvr5_weights',
    'tools/asr/models',
    'tools/AP_BWE_main/24kto48k'
)

$outDir = Split-Path -Parent $OutFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stage = Join-Path $env:TEMP ("voicesmith-assets-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$root = Join-Path $stage 'VoiceSmith-Offline-Assets'
New-Item -ItemType Directory -Force -Path (Join-Path $root 'gpt-sovits'), (Join-Path $root 'bin'), (Join-Path $root 'models') | Out-Null

function Copy-Relative([string]$relative) {
    $source = Join-Path $WeightsRoot ($relative -replace '/', '\')
    if (!(Test-Path $source)) { return $false }
    $target = Join-Path $root ('gpt-sovits\' + ($relative -replace '/', '\'))
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    if ((Get-Item $source).PSIsContainer) {
        robocopy $source $target /E /XD __pycache__ .venv /XF *.pyc /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
    } else {
        Copy-Item $source $target -Force
    }
    return $true
}

$included = @()
$missing = @()
foreach ($rel in $required) {
    if (Copy-Relative $rel) { $included += $rel } else { $missing += $rel }
}
if ($missing.Count -gt 0) {
    throw ("required weights missing under ${WeightsRoot}: " + ($missing -join ', '))
}
if (!$SkipOptional) {
    foreach ($rel in $optional) {
        if (Copy-Relative $rel) { $included += $rel }
    }
}

# ffmpeg / ffprobe are tools, not weights: take them from the source tree or PATH.
foreach ($tool in @('ffmpeg.exe', 'ffprobe.exe')) {
    $candidate = Join-Path $WeightsRoot ('runtime\' + $tool)
    if (Test-Path $candidate) {
        Copy-Item $candidate (Join-Path $root ('bin\' + $tool)) -Force
        continue
    }
    $found = Get-Command $tool -ErrorAction SilentlyContinue
    if ($found) { Copy-Item $found.Source (Join-Path $root ('bin\' + $tool)) -Force }
}

if (Test-Path $AsrRoot) {
    robocopy $AsrRoot (Join-Path $root 'models\faster-whisper') /E /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
}

# Manifest: every packed file with size + sha256 (no engine source, no runtime).
$files = Get-ChildItem -Recurse -File $root | Sort-Object FullName
$manifestFiles = [ordered]@{}
foreach ($file in $files) {
    $rel = $file.FullName.Substring($root.Length + 1).Replace('\', '/')
    $manifestFiles[$rel] = [ordered]@{
        size = $file.Length
        sha256 = (Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLower()
    }
}
$manifest = [ordered]@{
    version = $Version
    model_version = 'v5turbo'
    created_at = (Get-Date).ToString('yyyy-MM-dd')
    layout = 'gpt-sovits/ + bin/ (weights and tools only; engine source ships with the app)'
    source = $WeightsRoot
    files = $manifestFiles
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $root 'manifest.json') -Encoding UTF8

& $SevenZip a -t7z -mx=3 -mmt=on $OutFile (Join-Path $root '*') | Out-Null
if ($LASTEXITCODE -ne 0) { throw "7z failed: $LASTEXITCODE" }
$hash = (Get-FileHash $OutFile -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $OutFile).Length
$fileCount = (Get-ChildItem -Recurse -File $root).Count
$uncompressed = [math]::Round(((Get-ChildItem -Recurse -File $root | Measure-Object Length -Sum).Sum / 1GB), 2)
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "assets=$OutFile"
Write-Host "files=$fileCount uncompressed=${uncompressed}GB"
Write-Host "size=$size"
Write-Host "sha256=$hash"
