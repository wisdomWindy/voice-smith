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

## GitHub Release limitation

GitHub Releases allow **at most 2GB per asset**. Runtime (2.34GiB) and assets (3.02GiB) cannot be uploaded as single assets.

Required next step: split each pack into <2GB parts and publish a small manifest:

```json
{
  "sha256": "<whole pack sha256>",
  "parts": [
    { "url": ".../VoiceSmith-Runtime.7z.part01", "size": 1200000000 },
    { "url": ".../VoiceSmith-Runtime.7z.part02", "size": 1200000000 }
  ]
}
```

The downloader must download all parts, concatenate, verify the whole sha256, then extract.
