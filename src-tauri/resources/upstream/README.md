# Staged engine source (generated)

This directory is filled by `pnpm stage:engine` (scripts/stage-engine.mjs) at
build time and installed as `<app>/resources/upstream`.

- `GPT-SoVITS/` — copy of `vendor/GPT-SoVITS` **without** weights or runtime.
- Model/tool weights live in `<data>/assets` and are mounted into the engine at
  runtime by `sidecar/engine_paths.py`; they are never placed here.

Keep this README tracked: Tauri validates the `resources/upstream/` mapping at
compile time, and an empty/missing directory makes `cargo check` fail on a fresh
clone. Do not commit the staged `GPT-SoVITS/` copy (it is gitignored).
