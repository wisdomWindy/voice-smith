param(
    [string]$EngineRoot = "$env:APPDATA\com.voicesmith.desktop\engine\GPT-SoVITS",
    [string]$AsrRoot = "$env:APPDATA\com.voicesmith.desktop\models\faster-whisper",
    [string]$OutFile = "$PSScriptRoot\..\dist-assets\VoiceSmith-Offline-Assets.7z",
    [string]$SevenZip = "$env:USERPROFILE\.voicesmith\7ztools\7zr.exe"
)

$ErrorActionPreference = 'Stop'
if (!(Test-Path $EngineRoot)) { throw "engine not found: $EngineRoot" }
if (!(Test-Path $SevenZip)) { throw "7zr not found: $SevenZip" }
$outDir = Split-Path -Parent $OutFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stage = Join-Path $env:TEMP ("voicesmith-assets-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$root = Join-Path $stage 'VoiceSmith-Offline-Assets'
New-Item -ItemType Directory -Force -Path (Join-Path $root 'engine'), (Join-Path $root 'models') | Out-Null
robocopy $EngineRoot (Join-Path $root 'engine\GPT-SoVITS') /E /XD .git __pycache__ /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
if (Test-Path $AsrRoot) {
    robocopy $AsrRoot (Join-Path $root 'models\faster-whisper') /E /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
}

$manifest = [ordered]@{
    version = '0.1.0'
    model_version = 'v4'
    created_at = (Get-Date).ToString('yyyy-MM-dd')
    files = [ordered]@{}
}
$keys = [ordered]@{
    bert = 'engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large/pytorch_model.bin'
    hubert = 'engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/chinese-hubert-base/pytorch_model.bin'
    s1 = 'engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/s1v3.ckpt'
    s2_v4 = 'engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/gsv-v4-pretrained/s2Gv4.pth'
    vocoder_v4 = 'engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/gsv-v4-pretrained/vocoder.pth'
    sv = 'engine/GPT-SoVITS/GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt'
    g2pw = 'engine/GPT-SoVITS/GPT_SoVITS/text/G2PWModel/g2pW.onnx'
    uvr5 = 'engine/GPT-SoVITS/tools/uvr5/uvr5_weights/HP2_all_vocals.pth'
}
foreach ($name in $keys.Keys) {
    $path = Join-Path $root $keys[$name]
    if (Test-Path $path) {
        $manifest.files[$name] = [ordered]@{
            path = $keys[$name]
            size = (Get-Item $path).Length
            sha256 = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
        }
    }
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $root 'manifest.json') -Encoding UTF8
& $SevenZip a -t7z -mx=3 -mmt=on $OutFile (Join-Path $root '*')
if ($LASTEXITCODE -ne 0) { throw "7z failed: $LASTEXITCODE" }
$hash = (Get-FileHash $OutFile -Algorithm SHA256).Hash.ToLower()
$size = (Get-Item $OutFile).Length
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "assets=$OutFile"
Write-Host "size=$size"
Write-Host "sha256=$hash"
