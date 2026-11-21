# Thin distribution

VoiceSmith ships a thin installer plus separately downloaded runtime and asset
packs. Windows runtime is split into three components so each manifest/part can
be verified and resumed independently.

| Artifact | Size | Contents |
|---|---:|---|
| `VoiceSmith-<v>-Setup.exe` | ~3.5MB | Tauri UI, licenses, `7zr.exe` |
| `runtime-bundle.json` | <1KB | Entry point: base/core/torch manifests + sha256 |
| `runtime-base.part01` + `runtime-base-manifest.json` | ~14MB | Embedded CPython 3.11 + pip + sidecar sources |
| `deps-core.part01` + `deps-core-manifest.json` | ~104MB | FastAPI/uvicorn + audio DSP wheels |
| `deps-torch.part01..N` + `deps-torch-manifest.json` | ~3.05GiB | torch/torchaudio cu128 wheels |
| `VoiceSmith-Offline-Assets.7z` / split parts | ~3.02GiB | GPT-SoVITS engine, V4 weights, ASR, UVR5, ffmpeg |

First launch:

1. `runtime_missing` -> **安装运行时** dialog.
2. Fetch `runtime-bundle.json`, then each component manifest.
3. Download parts, verify part sizes and the assembled archive sha256.
4. Extract base into `runtime` (flattening `python/`), core/torch into
   `runtime/deps/{core,torch}`.
5. Run `runtime\python.exe sidecar\bootstrap.py` to install the offline wheels.
6. Start `runtime\python.exe sidecar\app.py`; then the assets dialog downloads
   and installs the engine pack.

The Rust installer accepts both the new bundle and the legacy single-pack
manifest (used by the macOS runtime): a JSON without a `components` array is
treated as one archive and extracted without bootstrap.

## Build and split

```powershell
scripts\build-runtime-base.ps1
scripts\build-deps-pack.ps1 -Kind core  -WheelsDir .cache\wheels-core
scripts\build-deps-pack.ps1 -Kind torch -WheelsDir .cache\wheels-torch
scripts\split-release-assets.ps1 -Version 0.2.3
```

`split-release-assets.ps1` writes the three component manifests and
`runtime-bundle.json`; `publish-release.ps1` uploads them together with the
installer. See [runtime-split.md](runtime-split.md) for the manifest schema and
installer internals.

## Notes

- GitHub allows **at most 2GB per asset**, so packs are split at 1.8GiB; parts
  above 900MB are downloaded with two parallel Range requests.
- The installer never hard-codes a runtime URL in the app binary; the frontend
  builds it from the release tag (`src/lib/release.ts`).
- macOS runtime still uses the PyInstaller single-pack path
  (`runtime-macos-*-manifest.json`) until it is split as well.
