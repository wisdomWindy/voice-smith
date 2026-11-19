param(
  [string]$Release = "C:\Users\yangjianlin\.voicesmith\tauri-target\release",
  [string]$Dest = "C:\Users\yangjianlin\.voicesmith\VoiceSmith-portable"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path (Join-Path $Release "voice-smith.exe"))) {
  throw "release exe not found: $Release\voice-smith.exe"
}
$engine = Join-Path $Release "voicesmith-engine"
if (-not (Test-Path $engine)) {
  throw "frozen sidecar not found: $engine"
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item (Join-Path $Release "voice-smith.exe") $Dest -Force
if (Test-Path (Join-Path $Dest "voicesmith-engine")) {
  Remove-Item (Join-Path $Dest "voicesmith-engine") -Recurse -Force
}
Copy-Item $engine (Join-Path $Dest "voicesmith-engine") -Recurse

@"
VoiceSmith portable build

1. Put the GPT-SoVITS engine at:
   %APPDATA%\com.voicesmith.desktop\engine\GPT-SoVITS
   or set VOICE_SMITH_ENGINE to its absolute path.
2. Put weights under the engine's GPT_SoVITS/pretrained_models (see docs/packaging.md).
3. Run voice-smith.exe.

This portable layout is for testing; it has no installer/uninstaller.
"@ | Set-Content (Join-Path $Dest "README.txt") -Encoding UTF8

Write-Host "portable package: $Dest"
