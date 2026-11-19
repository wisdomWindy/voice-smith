"""Download and install the optional offline asset pack."""

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


def configure(data_dir: Path, engine_root: Path) -> None:
    global _DATA, _ENGINE
    _DATA = data_dir
    _ENGINE = engine_root


def _update(**values: Any) -> None:
    with _LOCK:
        _STATE.update(values)


def status() -> dict[str, Any]:
    with _LOCK:
        data = dict(_STATE)
    engine = _ENGINE
    required = [
        engine / "GPT_SoVITS" / "pretrained_models" / "s1v3.ckpt" if engine else None,
        engine / "GPT_SoVITS" / "pretrained_models" / "gsv-v4-pretrained" / "s2Gv4.pth" if engine else None,
        engine / "GPT_SoVITS" / "pretrained_models" / "gsv-v4-pretrained" / "vocoder.pth" if engine else None,
    ]
    data["installed"] = all(path and path.exists() for path in required)
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
    candidates.append(Path(__file__).resolve().parent / "7zr.exe")
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


def _install_from_dir(extracted: Path) -> None:
    assert _DATA is not None and _ENGINE is not None
    _update(stage="installing", progress=0.9, message="安装引擎与权重")
    source_engine = extracted / "engine" / "GPT-SoVITS"
    if not source_engine.exists():
        raise FileNotFoundError("asset pack missing engine/GPT-SoVITS")
    shutil.copytree(source_engine, _ENGINE, dirs_exist_ok=True)
    source_models = extracted / "models" / "faster-whisper"
    if source_models.exists():
        target_models = _DATA / "models" / "faster-whisper"
        shutil.copytree(source_models, target_models, dirs_exist_ok=True)


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
