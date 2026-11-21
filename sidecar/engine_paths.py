"""Path contract between the vendored engine source and downloadable assets.

VoiceSmith splits GPT-SoVITS into three layers:

1. **engine source** - committed under ``vendor/GPT-SoVITS`` (development) or
   bundled as ``resources/upstream/GPT-SoVITS`` (installed). Read-only in
   spirit: VoiceSmith never rewrites upstream files.
2. **model / tool weights** - live in ``<data>/assets`` and are downloaded or
   imported at first run (BERT, HuBERT, GPT/SoVITS, G2PW, UVR5, FunASR, ffmpeg).
3. **runtime** - CPython + torch wheels under ``<install>/runtime``.

GPT-SoVITS resolves several weight paths *relative to the process working
directory or to its own package directory* (``GPT_SoVITS/pretrained_models``,
``GPT_SoVITS/text/G2PWModel``, ``tools/uvr5/uvr5_weights``,
``tools/asr/models``, ``tools/AP_BWE_main/24kto48k`` and ``runtime/ffmpeg.exe``
from ``tools/portable_runtime``). Rather than patching upstream source, the
weight directories from ``<data>/assets`` are mounted into the engine tree as
directory junctions (Windows) / symlinks (POSIX) by :func:`ensure_mounts`.

The mounts are links only: no weight byte is copied into the vendored tree and
``.gitignore`` keeps them out of the repository. If the engine tree is not
writable (read-only app bundle), the source is copied once to
``<data>/engine/GPT-SoVITS-src`` and the mounts are created there.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ENGINE_ENV = "VOICE_SMITH_ENGINE"
ASSETS_ENV = "VOICE_SMITH_ASSETS_DIR"
DATA_ENV = "VOICE_SMITH_DATA_DIR"

#: engine-relative directory -> directory below the asset store (``<data>/assets/gpt-sovits``)
WEIGHT_MOUNTS: dict[str, str] = {
    "GPT_SoVITS/pretrained_models": "GPT_SoVITS/pretrained_models",
    "GPT_SoVITS/text/G2PWModel": "GPT_SoVITS/text/G2PWModel",
    "tools/uvr5/uvr5_weights": "tools/uvr5/uvr5_weights",
    "tools/asr/models": "tools/asr/models",
    "tools/AP_BWE_main/24kto48k": "tools/AP_BWE_main/24kto48k",
}

#: ``tools/portable_runtime`` looks for ``<engine>/runtime/ffmpeg.exe``.
BIN_MOUNT = "runtime"

COPY_DIR_NAME = "GPT-SoVITS-src"
MARKER_NAME = ".voicesmith-source.json"

_SOURCE_IGNORE = {
    "__pycache__",
    ".venv",
    "runtime",
    "TEMP",
    "output",
    "GPT_SoVITS/pretrained_models",
    "GPT_SoVITS/text/G2PWModel",
    "GPT_SoVITS/Accel/vendor",
    "GPT_SoVITS/BigVGAN/demo",
    "GPT_SoVITS/BigVGAN/filelists",
    "tools/uvr5/uvr5_weights",
    "tools/asr/models",
    "tools/AP_BWE_main/24kto48k",
    "tools/denoise-model",
}


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def data_root() -> Path:
    """Data directory (DB, voices, outputs, assets). Rust passes ``--data-dir``."""
    explicit = _env_path(DATA_ENV)
    if explicit is not None:
        return explicit
    return PROJECT_ROOT / ".data"


def assets_root() -> Path:
    """Root of downloadable assets: ``<data>/assets`` (env overridable)."""
    explicit = _env_path(ASSETS_ENV)
    if explicit is not None:
        return explicit
    return data_root() / "assets"


def weights_root() -> Path:
    """Engine-shaped weight tree inside the asset store."""
    return assets_root() / "gpt-sovits"


def bin_root() -> Path:
    """Standalone tools (ffmpeg/ffprobe), mounted as ``<engine>/runtime``."""
    return assets_root() / "bin"


def legacy_engine_root() -> Path:
    """Pre-vendor layout: one offline pack installed source *and* weights here."""
    return data_root() / "engine" / "GPT-SoVITS"


def copy_engine_root() -> Path:
    """Writable fallback copy of the engine source."""
    return data_root() / "engine" / COPY_DIR_NAME


def engine_source() -> Path:
    """Canonical source location, ignoring env overrides."""
    return PROJECT_ROOT / "vendor" / "GPT-SoVITS"


def _has_engine(path: Path) -> bool:
    return (path / "GPT_SoVITS" / "TTS_infer_pack" / "TTS.py").is_file()


def engine_root() -> Path:
    """Engine source root: env override, vendored source, then legacy/fallback."""
    explicit = _env_path(ENGINE_ENV)
    if explicit is not None and explicit.exists():
        return explicit
    for candidate in (engine_source(), legacy_engine_root(), copy_engine_root()):
        if _has_engine(candidate):
            return candidate
    return engine_source()


def ffmpeg_path() -> Path | None:
    """Bundled ffmpeg, falling back to PATH."""
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = bin_root() / name
        if candidate.is_file():
            return candidate
    mounted = engine_root() / BIN_MOUNT
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = mounted / name
        if candidate.is_file():
            return candidate
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def _is_dir_link(path: Path) -> bool:
    """True for symlinks and Windows directory junctions."""
    if os.path.islink(path):
        return True
    if os.name != "nt":
        return False
    try:
        stat = os.lstat(path)
    except OSError:
        return False
    # IO_REPARSE_TAG_MOUNT_POINT (junction) / IO_REPARSE_TAG_SYMLINK
    return getattr(stat, "st_reparse_tag", 0) in (0xA000_0003, 0xA000_000C)


def _link_target(path: Path) -> Path | None:
    try:
        return Path(os.path.realpath(path))
    except OSError:
        return None


def _remove_dir_link(path: Path) -> None:
    try:
        os.rmdir(path)
    except OSError:
        os.unlink(path)


def _make_dir_link(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0:
            return
        # Developer mode / elevated shells allow symlinks without mklink.
        try:
            os.symlink(source, target, target_is_directory=True)
            return
        except OSError as exc:
            raise OSError(
                f"mklink failed ({completed.stderr or completed.stdout}); symlink failed: {exc}"
            ) from exc
    os.symlink(source, target, target_is_directory=True)


def _mount_one(engine: Path, rel_target: str, source: Path) -> dict[str, Any]:
    target = engine / rel_target
    entry: dict[str, Any] = {
        "path": rel_target,
        "target": str(target),
        "source": str(source),
        "status": "",
        "error": "",
    }
    if not source.is_dir():
        entry["status"] = "missing-assets"
        return entry
    if target.exists() or _is_dir_link(target):
        if _is_dir_link(target):
            resolved = _link_target(target)
            wanted = Path(os.path.realpath(source))
            if resolved == wanted:
                entry["status"] = "mounted"
                return entry
            try:
                _remove_dir_link(target)
            except OSError as exc:  # pragma: no cover - permission edge
                entry["status"] = "failed"
                entry["error"] = f"cannot replace existing link: {exc}"
                return entry
        else:
            # A real directory already exists (legacy in-place weights, user import).
            # Never delete it; just report that the asset store is not authoritative.
            entry["status"] = "unmanaged"
            return entry
    try:
        _make_dir_link(target, source)
        entry["status"] = "mounted"
    except OSError as exc:
        entry["status"] = "failed"
        entry["error"] = str(exc)
    return entry


def _mount_bin(engine: Path) -> dict[str, Any]:
    return _mount_one(engine, BIN_MOUNT, bin_root())


def _source_ignore(root: Path):
    """copytree ignore callback: drop weights/caches and runtime junctions."""
    root = root.resolve()

    def ignore(dirpath: str, names: list[str]) -> set[str]:
        rel = Path(os.path.relpath(dirpath, root)).as_posix()
        ignored: set[str] = set()
        for name in names:
            child = name if rel == "." else f"{rel}/{name}"
            if name == "__pycache__" or name.endswith(".pyc"):
                ignored.add(name)
                continue
            if child in _SOURCE_IGNORE:
                ignored.add(name)
                continue
            if _is_dir_link(Path(dirpath) / name):
                ignored.add(name)
        return ignored

    return ignore


def _marker_payload(source: Path) -> dict[str, Any]:
    payload = {"source": str(source), "copied_at": ""}
    manifest = source / "VENDOR_MANIFEST.json"
    if manifest.is_file():
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        payload["manifest_sha256"] = digest
    return payload


def _copy_source(source: Path) -> Path:
    """Copy engine source to a writable location under the data directory."""
    target = copy_engine_root()
    marker = target / MARKER_NAME
    wanted = _marker_payload(source)
    if target.is_dir() and marker.is_file():
        try:
            current = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            current = {}
        if current.get("source") == wanted.get("source") and current.get(
            "manifest_sha256"
        ) == wanted.get("manifest_sha256"):
            return target
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target, ignore=_source_ignore(source), dirs_exist_ok=True)
    wanted["copied_at"] = datetime.now(timezone.utc).isoformat()
    marker.write_text(json.dumps(wanted, indent=2), encoding="utf-8")
    return target


def _mount_all(engine: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rel_target, rel_source in WEIGHT_MOUNTS.items():
        entries.append(_mount_one(engine, rel_target, weights_root() / rel_source))
    entries.append(_mount_bin(engine))
    return entries


def ensure_mounts(engine: Path | None = None, assets: Path | None = None) -> dict[str, Any]:
    """Make weight directories visible inside the engine tree.

    Returns a JSON-serialisable report; callers can log it or expose it from
    ``/api/v1/assets``. This is idempotent and cheap, safe to call from every
    worker start.
    """
    if assets is not None:
        os.environ[ASSETS_ENV] = str(assets)
    root = Path(engine) if engine is not None else engine_root()
    report: dict[str, Any] = {
        "engine_root": str(root),
        "engine_source": str(engine_source()),
        "assets_root": str(assets_root()),
        "weights_root": str(weights_root()),
        "copied": False,
        "engine_present": _has_engine(root),
        "mounts": [],
        "error": "",
    }
    if not report["engine_present"]:
        report["error"] = f"engine source not found: {root}"
        return report

    mounts = _mount_all(root)
    failed = [entry for entry in mounts if entry["status"] == "failed"]
    if failed and root.resolve() != copy_engine_root().resolve():
        # Read-only install (e.g. macOS .app): materialise a writable source copy
        # once and mount the weights there instead of patching the bundle.
        try:
            copied = _copy_source(root)
        except OSError as exc:
            report["mounts"] = mounts
            report["error"] = f"engine tree not writable and copy failed: {exc}"
            return report
        report["copied"] = True
        report["engine_root"] = str(copied)
        mounts = _mount_all(copied)
        failed = [entry for entry in mounts if entry["status"] == "failed"]

    report["mounts"] = mounts
    if failed:
        report["error"] = "some asset mounts failed: " + ", ".join(
            entry["path"] for entry in failed
        )
    return report


def describe() -> dict[str, Any]:
    """Static view of the path contract (used by diagnostics)."""
    return {
        "project_root": str(PROJECT_ROOT),
        "data_root": str(data_root()),
        "engine_source": str(engine_source()),
        "engine_root": str(engine_root()),
        "assets_root": str(assets_root()),
        "weights_root": str(weights_root()),
        "bin_root": str(bin_root()),
        "ffmpeg": str(ffmpeg_path() or ""),
        "mounts": {rel: str(weights_root() / src) for rel, src in WEIGHT_MOUNTS.items()},
    }


if __name__ == "__main__":
    payload = ensure_mounts()
    payload["paths"] = describe()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not payload["error"] else 1)
