# Thin distribution

VoiceSmith ships a thin installer plus separately downloaded runtime and weight
packs. The installer now also carries the **vendored GPT-SoVITS engine source**,
so the app no longer depends on a monolithic `v5-engine` release. Windows runtime
is split into three components so each manifest/part can be verified and resumed
independently.

| Artifact | Size | Contents |
|---|---:|---|
| `VoiceSmith-<v>-Setup.exe` | ~55MB | Tauri UI, **GPT-SoVITS engine source** (`resources/upstream`), licenses, `7zr.exe` |
| `runtime-bundle.json` | <1KB | Entry point: base/core/torch manifests + sha256 |
| `runtime-base.part01` + `runtime-base-manifest.json` | ~14MB | Embedded CPython 3.11 + pip + sidecar sources |
| `deps-core.part01` + `deps-core-manifest.json` | ~104MB | FastAPI/uvicorn + audio DSP wheels |
| `deps-torch.part01..N` + `deps-torch-manifest.json` | ~3.05GiB | torch/torchaudio cu128 wheels |
| `assets.partNN` + `assets-<platform>-manifest.json` | ~5.5GB | Weights/tools only: GPT/SoVITS/BERT/HuBERT/SV/G2PW, FunASR, UVR5, ffmpeg |

First launch:

1. `runtime_missing` -> one **首次设置** dialog that lists runtime, offline asset
   pack and usage terms; a single confirmation installs them in order.
2. Fetch `runtime-bundle.json`, then each component manifest.
3. Download parts, verify part sizes and the assembled archive sha256.
4. Extract base into `runtime` (flattening `python/`), core/torch into
   `runtime/deps/{core,torch}`.
5. Run `runtime\python.exe sidecar\bootstrap.py` to install the offline wheels.
6. Start `runtime\python.exe sidecar\app.py`; the same dialog then continues with
   the weights pack into `<data>/assets` and mounts it into
   `resources\upstream\GPT-SoVITS` (engine source stays untouched).

The Rust installer accepts both the new bundle and the legacy single-pack
manifest (used by the macOS runtime): a JSON without a `components` array is
treated as one archive and extracted without bootstrap.

## Build and split

```powershell
pnpm stage:engine                     # vendor/GPT-SoVITS -> src-tauri/resources/upstream
scripts\build-runtime-base.ps1
scripts\build-deps-pack.ps1 -Kind core  -WheelsDir .cache\wheels-core
scripts\build-deps-pack.ps1 -Kind torch -WheelsDir .cache\wheels-torch
scripts\build-assets-pack.ps1 -WeightsRoot D:\program\GPT-SoVITS-v5
scripts\split-release-assets.ps1 -Version 0.3.0
```

`split-release-assets.ps1` writes the three runtime component manifests, the
`assets` manifest/parts and `runtime-bundle.json`; `publish-release.ps1` uploads
them together with the installer. `release-all.yml` publishes installers and
runtime; the weight pack is published by `release-packs.yml` (self-hosted runner
with a weights tree), which is why `release-all` no longer reads `v5-engine`.

See [runtime-split.md](runtime-split.md) for the manifest schema and installer
internals.

## Notes

- GitHub allows **at most 2GB per asset**, so packs are split at 1.8GiB; parts
  above 900MB are downloaded with two parallel Range requests.
- The installer never hard-codes a runtime/asset URL in the app binary; the
  frontend builds them from the release tag (`src/lib/release.ts`).
- Weight directories are mounted, not copied: `<data>/assets` remains the only
  copy, and `git`/installer payload never contains model weights.
- macOS runtime still uses the PyInstaller single-pack path
  (`runtime-macos-*-manifest.json`) until it is split as well.
