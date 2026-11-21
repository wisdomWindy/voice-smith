# VoiceSmith Offline Assets

## Artifact

- File: `C:\Users\yangjianlin\.voicesmith\offline-pack\VoiceSmith-Offline-Assets.7z`
- Size: 3,244,469,305 bytes (3.02 GiB)
- SHA256: `35bfe73266a5dfb5fbfdce1b5fbaa61580a07bafb9b09df06cb5a2a48ea968b8`
- Uncompressed: 3.48GB

Contents:

```text
engine/GPT-SoVITS/                 GPT-SoVITS source, runtime ffmpeg, configs
  GPT_SoVITS/pretrained_models/    BERT, HuBERT, s1v3, s2Gv4, vocoder, SV
  GPT_SoVITS/text/G2PWModel/       g2pW.onnx
  tools/uvr5/uvr5_weights/         HP2_all_vocals.pth
models/faster-whisper/             faster-whisper small cache
manifest.json                      key file sizes + sha256
```

## Hosting

Upload `VoiceSmith-Offline-Assets.7z` to a release/CDN and expose its HTTPS URL.
Then either:

- paste the URL into the first-run **安装离线资产** dialog, or
- set `VOICE_SMITH_ASSETS_URL=<https-url>` before launching, or
- set `VOICE_SMITH_ASSETS_SHA256=<sha256>` to enforce pack integrity.

No URL is hard-coded in the build, because the asset pack is not hosted by VoiceSmith.

## Install flow

1. Thin installer: `VoiceSmith-<version>-Setup.exe` (see `thin-distribution.md`).
2. First launch -> usage terms -> **安装离线资产** dialog.
3. Paste URL -> **下载并安装离线资产**.
4. Sidecar downloads to `%APPDATA%\com.voicesmith.desktop\asset-pack.7z`,
   verifies sha256 (if configured), extracts with bundled `7zr.exe`, copies:
   - `engine/GPT-SoVITS` -> `%APPDATA%\com.voicesmith.desktop\engine\GPT-SoVITS`
   - `models/faster-whisper` -> `%APPDATA%\com.voicesmith.desktop\models\faster-whisper`
5. App restarts the sidecar and doctor/inference/training become available.

## Verified

Local HTTP end-to-end test:

- URL: `http://127.0.0.1:8900/VoiceSmith-Offline-Assets.7z`
- download + sha256 + 7zr extract + install: **done**
- installed 3.48GB under a clean data dir
- `s2Gv4.pth` and faster-whisper cache present
