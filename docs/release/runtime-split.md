# Runtime split (Windows)

Windows runtime used to be a single PyInstaller onedir archive. It is now split
into an embedded Python base plus offline wheel packs so the downloader can
verify components independently and `pip` can provision the environment at
install time.

## Components

| Component | Archive | Extracted to | Contents |
|---|---|---|---|
| `base` | `VoiceSmith-Runtime-base.7z` | `runtime/` + `runtime/sidecar/` | CPython 3.11.9 embeddable, pip, sidecar `*.py` |
| `core` | `VoiceSmith-Deps-core.7z` | `runtime/deps/core/` | FastAPI/uvicorn, librosa/scipy/numba/soundfile wheels |
| `torch` | `VoiceSmith-Deps-torch.7z` | `runtime/deps/torch/` | torch/torchaudio cu128 wheels + torch deps |

Each component is split at 1.8GiB by `scripts/split-release-assets.ps1`:

- `runtime-base.part01` ... + `runtime-base-manifest.json`
- `deps-core.part01` ... + `deps-core-manifest.json`
- `deps-torch.part01..partNN` + `deps-torch-manifest.json`
- `runtime-bundle.json` (entry point)

## runtime-bundle.json

```json
{
  "version": "0.2.3",
  "platform": "windows-x64",
  "components": [
    { "name": "base",  "manifest": "https://.../runtime-base-manifest.json", "sha256": "...", "size": 14325240 },
    { "name": "core",  "manifest": "https://.../deps-core-manifest.json",    "sha256": "...", "size": 108743870 },
    { "name": "torch", "manifest": "https://.../deps-torch-manifest.json",   "sha256": "...", "size": 3267748358 }
  ]
}
```

- Names are restricted to `base`, `core`, `torch`; duplicates/unknown names fail.
- The bundle `sha256`/`size` must match the component manifest; a mismatch aborts
  before any download.
- All three components are required. Order is normalized to base → core → torch.

Generate it with:

```powershell
scripts\build-runtime-bundle.ps1 -Version 0.2.3 -ManifestDir dist-assets
# or as part of
scripts\split-release-assets.ps1 -Version 0.2.3
```

## Installer flow (`src-tauri/src/lib.rs`)

`install_runtime(url)` accepts a bundle URL (`.json` containing `components`):

1. Download `runtime-bundle.json`, then each component manifest.
2. Download every part to `runtime-<name>.7z`, checking each part size.
3. Verify the assembled archive size and sha256.
4. Extract base: stage `python/` and `sidecar/`, flatten `python/*` into
   `runtime/`, keep `runtime/sidecar/`.
5. Extract core/torch under `runtime/deps/`, requiring at least one `.whl` each.
6. Run `runtime\python.exe sidecar\bootstrap.py` (working dir `runtime`). The
   log is `data/logs/bootstrap.log`; on failure the log tail is returned.
7. Start `runtime\python.exe sidecar\app.py` with `--port`, `--token`,
   `--data-dir`; wait up to 30s for the port.

Progress events (`runtime-progress`) are weighted by component sizes and end at
100 after the sidecar is reachable. Before extraction the existing sidecar is
stopped so Windows does not lock `python.exe`/DLL files.

### Legacy path

A JSON without `components` (macOS `runtime-macos-*-manifest.json`) or a direct
`.7z` URL still installs as one archive:
download → verify sha256 → extract into `runtime/` → start packed engine. No
bootstrap runs. This keeps old releases and macOS working while Windows moves to
the split runtime.

## Bootstrap details

`sidecar/bootstrap.py` runs:

```text
python -m pip install --no-index --no-cache-dir <all runtime/deps/**/*.whl>
```

The embeddable CPython distribution does not ship pip, so
`scripts/build-runtime-base.ps1` installs a pinned pip (`-PipVersion`, default
`25.2`) with `get-pip.py` and enables `Lib\site-packages` in `python311._pth`.
The same `_pth` adds `sidecar` (flat layout) instead of the old `..\sidecar`.

## Build commands

```powershell
scripts\build-runtime-base.ps1
scripts\build-deps-pack.ps1 -Kind core  -WheelsDir .cache\wheels-core
scripts\build-deps-pack.ps1 -Kind torch -WheelsDir .cache\wheels-torch
scripts\split-release-assets.ps1 -Version 0.2.3 -SkipAssets
```

CI (`release-all.yml`, `runtime-windows`) downloads the core/torch wheels with
`pip download`, builds the three archives, splits them, generates
`runtime-bundle.json`, and uploads all parts, manifests, and the bundle.

## Current verification

- `cargo check` passes (`src-tauri`), including the new bundle/manifest parsing,
  per-component sha256 verification, base flattening, and deps extraction paths.
- `cargo test --lib` passes: 3 tests (bundle JSON parsing, sha/progress helpers,
  base + core/torch extraction layout using a real 7zr archive).
- `python -m py_compile sidecar/*.py scripts/**/*.py` passes (25 files).
- `pnpm build` (`vue-tsc --noEmit` + Vite) passes with the new
  `runtime-bundle.json` URL in `src/lib/release.ts`.
- Rebuilt `VoiceSmith-Runtime-base.7z` (14,325,240 bytes,
  `a69a47cd...`) and verified the installed layout:
  `runtime/python.exe` reports CPython 3.11.9 with `sys.prefix = runtime`.
- Ran `runtime\python.exe sidecar\bootstrap.py` against the local core wheel
  pack: 47 wheels installed offline, then imported fastapi/uvicorn/pydantic/
  librosa/numpy/scipy/soundfile/numba successfully.
- Started `runtime\python.exe sidecar\app.py --port 8799 --token ... --data-dir ...`
  and `GET /health` returned 200 (`status=ok`).
- `scripts/split-release-assets.ps1` generated all three component manifests and
  `runtime-bundle.json` (3 components) from local archives; recomputing sha256
  over the concatenated parts matched each manifest for base/core/torch.
- No release was published from this branch; artifacts in `dist-assets/` are
  build outputs and are git-ignored.
