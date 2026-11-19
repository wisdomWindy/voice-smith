# Thin distribution

VoiceSmith now follows the same three-artifact model as `voice-generator`:

| Artifact | Size | Contents |
|---|---:|---|
| `VoiceSmith-0.1.0-Setup.exe` | 3.5MB | Tauri UI, licenses, `7zr.exe` |
| `VoiceSmith-Runtime.7z` | 2.34GiB | frozen Python/PyTorch/CUDA sidecar |
| `VoiceSmith-Offline-Assets.7z` | 3.02GiB | GPT-SoVITS engine, V4 weights, BERT/HuBERT/G2PW/SV, UVR5, faster-whisper, ffmpeg |

First launch:

1. `runtime_missing` -> **安装运行时** dialog.
2. Download runtime pack, sha256, extract to `%APPDATA%\com.voicesmith.desktop\runtime`.
3. Restart sidecar; then `assets` dialog downloads/installs the engine pack.

Verified locally with HTTP:

- thin installer 3.5MB
- runtime pack 2,508,421,281 bytes, sha256 `16830e39f5743c8020b4409111e7affddfbe36e9a0700c54a906b3ba74a2c474`
- assets pack 3,244,469,305 bytes, sha256 `35bfe73266a5dfb5fbfdce1b5fbaa61580a07bafb9b09df06cb5a2a48ea968b8`
- runtime extract -> sidecar `gpt-sovits` ready; no console window
- runtime install + V4 inference succeeded

## GitHub Release (published)

Release: https://github.com/wisdomWindy/voice-smith/releases/tag/v0.1.0

Because GitHub allows **at most 2GB per asset**, packs are split:

| Asset | Size |
|---|---:|
| `VoiceSmith-0.1.0-Setup.exe` | 3.5MB |
| `runtime.part01` | 1.8GB |
| `runtime.part02` | 592MB |
| `runtime-manifest.json` | 678B |
| `assets.part01` | 1.8GB |
| `assets.part02` | 1.29GB |
| `assets-manifest.json` | 675B |

The downloader reads the manifest, downloads all parts, concatenates, verifies the whole sha256, then extracts.
