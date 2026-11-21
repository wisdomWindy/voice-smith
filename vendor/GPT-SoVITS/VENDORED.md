# Vendored GPT-SoVITS engine source

VoiceSmith keeps the GPT-SoVITS **engine source** in this directory so the app
does not depend on a monolithic `v5-engine` release any more:

| Layer | Where it lives |
| --- | --- |
| Engine source (Python modules, configs, text frontend code) | this directory, committed to git |
| Model / tool weights (BERT, HuBERT, GPT/SoVITS, G2PW, UVR5, ASR, ffmpeg) | `<data>/assets/`, downloaded or imported at first run |
| Python runtime (CPython + torch wheels) | `<install>/runtime/`, downloaded separately |

`sidecar/engine_paths.py` mounts the weight directories from `<data>/assets`
into the engine tree as directory junctions/symlinks at startup, so upstream
relative lookups (`GPT_SoVITS/pretrained_models`, `GPT_SoVITS/text/G2PWModel`,
`tools/uvr5/uvr5_weights`, `tools/asr/models`, `runtime/ffmpeg.exe`) keep working
without copying a single weight byte into the versioned source.

## Provenance

- Upstream project: <https://github.com/RVC-Boss/GPT-SoVITS> (MIT, see `LICENSE`).
- Snapshot source: local `D:\program\GPT-SoVITS-v5` working tree (V5 Turbo line,
  default `weight.json` points at `s1v3.ckpt` + `gsv-v5-pretrained/s2Gv5turbo.pth`).
- Copied on 2026-11-21. `VENDOR_MANIFEST.json` records every vendored file with
  its size and sha256 so drift is detectable.

## What is intentionally excluded

Runtime and model payloads are **assets**, not source. Excluded from this copy:

- `.venv/`, `runtime/`, `TEMP/`, `output/`, `__pycache__/`, `*.pyc`
- `GPT_SoVITS/pretrained_models/` (BERT, HuBERT, s1v3, gsv-v2/v3/v4/v5 weights,
  BigVGAN, SV, fast_langdetect)
- `GPT_SoVITS/text/G2PWModel/` (`g2pW.onnx` and friends)
- `GPT_SoVITS/Accel/vendor/` (bundled CUDA runtime DLLs)
- `tools/uvr5/uvr5_weights/`, `tools/asr/models/`,
  `tools/AP_BWE_main/24kto48k/` (UVR5 / FunASR / super-sampling weights)
- `GPT_SoVITS/BigVGAN/demo/`, `GPT_SoVITS/BigVGAN/filelists/` (upstream demo and
  training file lists, not used at runtime)
- `tools/denoise-model/` (weight drop directory)
- `GPT_weights*/`, `SoVITS_weights*/` (user training output directories)
- binary model extensions and `*_cache.pickle` caches

`tools/AP_BWE_main/24kto48k/config.json` is part of that weight directory and is
also delivered by the asset pack; the engine still degrades gracefully
(`sr_model_not_exist`) when super-sampling assets are absent.

## Git note

Upstream ships `GPT_SoVITS/configs/.gitignore` with `*.yaml`, but the configs are
runtime inputs (`tts_infer.yaml` is read by the worker to seed device/version,
`s1*.yaml` / `train.yaml` are training presets). They are force-added:

```powershell
git add -f vendor/GPT-SoVITS/GPT_SoVITS/configs/*.yaml
```

## Updating the vendored source

1. Copy a new upstream tree with the same exclusions (see
   `scripts/build-assets-pack.ps1` and this file).
2. Re-generate `VENDOR_MANIFEST.json` (`scripts/stage-engine.ps1 -WriteManifest`).
3. Run the regression checks: `cargo check`, `python -m py_compile sidecar/*.py`,
   `pnpm build`, plus a smoke synthesis if weights are installed.
4. Record the change in `docs/GPT-SoVITS-integration.md` and release notes.

Do not edit upstream source in place. When VoiceSmith needs a different
behaviour, patch it from `sidecar/` (env vars, generated configs) or copy the
script into the data/workspace directory first.
