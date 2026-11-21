"""Download and install the optional offline asset pack.

The pack only carries **model / tool weights** now. Engine source ships with the
app (``resources/upstream/GPT-SoVITS``), so an asset pack no longer decides which
engine version runs.

Supported pack layouts:

  gpt-sovits/...            current layout, copied to ``<data>/assets/gpt-sovits``
  bin/...                   current layout, copied to ``<data>/assets/bin``
  engine/GPT-SoVITS/...     legacy monolithic pack: only the weight directories
                            and ffmpeg are imported, the source half is ignored
  GPT_SoVITS/...            bare weight tree, copied to ``<data>/assets/gpt-sovits``

Legacy packs are accepted on purpose so existing users can keep their download;
nothing from an old pack can overwrite the vendored engine source.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Any

import engine_paths

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "installing": False,
    "progress": 0.0,
    "stage": "idle",
    "error": "",
    "message": "",
    "url": os.environ.get("VOICE_SMITH_ASSETS_URL", ""),
    "expected_sha256": os.environ.get("VOICE_SMITH_ASSETS_SHA256", ""),
}
_DATA: Path | None = None
_ENGINE: Path | None = None

REQUIRED_WEIGHTS: tuple[str, ...] = (
    "GPT_SoVITS/pretrained_models/s1v3.ckpt",
    "GPT_SoVITS/pretrained_models/gsv-v5-pretrained/s2Gv5turbo.pth",
    "GPT_SoVITS/pretrained_models/gsv-v5-pretrained/vocoder.pth",
)


def configure(data_dir: Path, engine_root: Path | None = None) -> None:
    global _DATA, _ENGINE
    _DATA = Path(data_dir)
    os.environ[engine_paths.DATA_ENV] = str(_DATA)
    _ENGINE = Path(engine_root) if engine_root is not None else engine_paths.engine_root()
    engine_paths.ensure_mounts(_ENGINE)


def _update(**values: Any) -> None:
    with _LOCK:
        _STATE.update(values)


def _missing_weights() -> list[str]:
    root = engine_paths.weights_root()
    return [rel for rel in REQUIRED_WEIGHTS if not (root / rel).is_file()]


def status() -> dict[str, Any]:
    with _LOCK:
        data = dict(_STATE)
    missing = _missing_weights()
    data["installed"] = not missing and engine_paths.engine_root().joinpath(
        "GPT_SoVITS", "TTS_infer_pack", "TTS.py"
    ).is_file()
    data["missing"] = missing
    data["weights_root"] = str(engine_paths.weights_root())
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_7zr() -> Path:
    import sys

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "7zr.exe")
        candidates.append(Path(sys.executable).resolve().parent / "7zr")
    candidates.append(Path(__file__).resolve().parent / "7zr.exe")
    candidates.append(Path(__file__).resolve().parent / "7zr")
    candidates.append(Path(__file__).resolve().parent.parent / "7ztools" / "7zr.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("7zr.exe not found; reinstall VoiceSmith")


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "VoiceSmith/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            done += len(chunk)
            if total:
                _update(progress=min(0.75, done / total * 0.75), stage="downloading",
                        message=f"{done / 1024 ** 3:.2f} / {total / 1024 ** 3:.2f} GB")


def _download_pack(url: str, target: Path) -> str:
    if not url.lower().endswith(".json"):
        _download(url, target)
        return ""
    request = urllib.request.Request(url, headers={"User-Agent": "VoiceSmith/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        manifest = json.loads(response.read().decode("utf-8-sig"))
    parts = manifest.get("parts") or []
    if not parts:
        raise ValueError("asset manifest has no parts")
    with target.open("wb") as output:
        for index, part in enumerate(parts):
            part_url = str(part.get("url") or "")
            if not part_url:
                raise ValueError("asset manifest part has no url")
            temp = target.with_suffix(f".part{index:02}")
            _download(part_url, temp)
            with temp.open("rb") as source:
                shutil.copyfileobj(source, output)
            temp.unlink(missing_ok=True)
    return str(manifest.get("sha256") or "")


def _copy_tree(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)


def _import_legacy_engine(source_engine: Path) -> int:
    """Import weights from a pre-vendor pack; ignore its bundled source."""
    weights = engine_paths.weights_root()
    copied = 0
    for rel in engine_paths.WEIGHT_MOUNTS:
        candidate = source_engine / rel
        if candidate.is_dir():
            _copy_tree(candidate, weights / rel)
            copied += 1
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        candidate = source_engine / "runtime" / name
        if candidate.is_file():
            target = engine_paths.bin_root() / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, target)
    return copied


def _install_from_dir(extracted: Path) -> None:
    assert _DATA is not None
    _update(stage="installing", progress=0.9, message="安装引擎权重与工具")
    weights = engine_paths.weights_root()
    bin_root = engine_paths.bin_root()
    weights.mkdir(parents=True, exist_ok=True)
    bin_root.mkdir(parents=True, exist_ok=True)

    pack_weights = extracted / "gpt-sovits"
    legacy_engine = extracted / "engine" / "GPT-SoVITS"
    bare_weights = extracted / "GPT_SoVITS"

    if pack_weights.is_dir():
        _copy_tree(pack_weights, weights)
        _copy_tree(extracted / "bin", bin_root)
    elif legacy_engine.is_dir():
        if not _import_legacy_engine(legacy_engine):
            raise FileNotFoundError("legacy asset pack has no known weight directories")
    elif bare_weights.is_dir():
        _copy_tree(extracted, weights)
        _copy_tree(extracted / "bin", bin_root)
    else:
        raise FileNotFoundError(
            "asset pack has no gpt-sovits/ weight tree (expected gpt-sovits/... or legacy engine/GPT-SoVITS)"
        )

    source_models = extracted / "models" / "faster-whisper"
    if source_models.exists():
        target_models = _DATA / "models" / "faster-whisper"
        shutil.copytree(source_models, target_models, dirs_exist_ok=True)

    engine_paths.ensure_mounts(_ENGINE)
    missing = _missing_weights()
    if missing:
        raise FileNotFoundError("asset pack incomplete, missing: " + ", ".join(missing))


def _run(url: str, expected: str) -> None:
    assert _DATA is not None
    pack = _DATA / "asset-pack.7z"
    extracted = _DATA / "asset-pack-extract"
    try:
        if not url:
            raise ValueError("asset pack URL is not configured")
        _update(installing=True, progress=0.01, stage="downloading", error="", message="开始下载")
        manifest_hash = _download_pack(url, pack)
        expected = expected or manifest_hash
        if expected:
            _update(stage="verifying", progress=0.78, message="校验 sha256")
            actual = _sha256(pack)
            if actual.lower() != expected.lower():
                raise ValueError(f"asset pack sha256 mismatch: {actual}")
        _update(stage="extracting", progress=0.82, message="解压离线资产")
        seven = _find_7zr()
        if extracted.exists():
            shutil.rmtree(extracted)
        result = subprocess.run(
            [str(seven), "x", str(pack), f"-o{extracted}", "-y"],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if result.returncode != 0:
            raise RuntimeError(f"7zr failed: {result.stderr[-500:]}")
        _install_from_dir(extracted)
        _update(installing=False, progress=1.0, stage="done", message="离线资产安装完成")
    except Exception as exc:  # noqa: BLE001
        _update(installing=False, progress=0, stage="failed", error=str(exc), message="安装失败")
    finally:
        shutil.rmtree(extracted, ignore_errors=True)
        pack.unlink(missing_ok=True)


def start(url: str = "", expected_sha256: str = "") -> dict[str, Any]:
    with _LOCK:
        if _STATE["installing"]:
            return dict(_STATE)
    target_url = url or str(_STATE.get("url") or "")
    target_hash = expected_sha256 or str(_STATE.get("expected_sha256") or "")
    _update(url=target_url, expected_sha256=target_hash, error="", stage="queued", progress=0)
    thread = threading.Thread(target=_run, args=(target_url, target_hash), daemon=True)
    thread.start()
    return status()
