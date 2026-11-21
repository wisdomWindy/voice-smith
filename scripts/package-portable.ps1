param(
  [string]$Release = "$PSScriptRoot\..\.cache\tauri-target\release",
  [string]$Dest = "$PSScriptRoot\..\.cache\VoiceSmith-portable"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Release "voice-smith.exe"))) {
  throw "release exe not found: $Release\voice-smith.exe"
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item (Join-Path $Release "voice-smith.exe") $Dest -Force
Copy-Item (Join-Path $root "sidecar\7zr.exe") $Dest -Force

# Engine source ships with the app; weights are downloaded into data/assets.
$staged = Join-Path $root "src-tauri\resources\upstream"
if (-not (Test-Path (Join-Path $staged "GPT-SoVITS"))) {
  Write-Host "staging engine source..."
  & node (Join-Path $root "scripts\stage-engine.mjs")
  if ($LASTEXITCODE -ne 0) { throw "stage-engine failed" }
}
if (Test-Path (Join-Path $Dest "resources")) {
  Remove-Item (Join-Path $Dest "resources") -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $Dest "resources") | Out-Null
Copy-Item $staged (Join-Path $Dest "resources\upstream") -Recurse

# Legacy frozen sidecar (macOS onedir) is optional for the portable layout.
$frozen = Join-Path $Release "voicesmith-engine"
if (Test-Path $frozen) {
  if (Test-Path (Join-Path $Dest "voicesmith-engine")) {
    Remove-Item (Join-Path $Dest "voicesmith-engine") -Recurse -Force
  }
  Copy-Item $frozen (Join-Path $Dest "voicesmith-engine") -Recurse
}

@"
VoiceSmith portable build

Layout
  voice-smith.exe            Tauri UI
  resources/upstream/        vendored GPT-SoVITS engine source
  data/                      runtime data root (created on first launch)
  data/assets/gpt-sovits/    weights, imported/downloaded at first launch
  data/assets/bin/           ffmpeg.exe / ffprobe.exe

1. Launch voice-smith.exe.
2. The installer dialog downloads the runtime (python + torch wheels).
3. The asset dialog downloads/imports the weights pack, or set
   VOICE_SMITH_ASSETS_URL / VOICE_SMITH_ASSETS_SHA256 before launch.
4. Overrides for troubleshooting:
   VOICE_SMITH_ENGINE        absolute engine source dir
   VOICE_SMITH_ASSETS_DIR    absolute asset store dir
   VOICE_SMITH_DATA_DIR      absolute data dir

This portable layout is for testing; it has no installer/uninstaller.
"@ | Set-Content (Join-Path $Dest "README.txt") -Encoding UTF8

Write-Host "portable package: $Dest"
