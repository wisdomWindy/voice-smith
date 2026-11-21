"""Model / tool asset checks for the vendored GPT-SoVITS engine.

Asset bytes live in the data directory (``<data>/assets``), never in the engine
source tree:

  assets/gpt-sovits/GPT_SoVITS/pretrained_models/...   BERT, HuBERT, GPT/SoVITS, SV
  assets/gpt-sovits/GPT_SoVITS/text/G2PWModel/...      G2PW ONNX frontend
  assets/gpt-sovits/tools/uvr5/uvr5_weights/...        UVR5 separation weights
  assets/gpt-sovits/tools/asr/models/...               FunASR models
  assets/gpt-sovits/tools/AP_BWE_main/24kto48k/...     super-sampling weights
  assets/bin/ffmpeg.exe                                ffmpeg / ffprobe

``engine_paths.ensure_mounts`` links those directories into the engine tree so
upstream relative lookups keep working. ``refresh`` recomputes the module-level
paths after the sidecar knows its real ``--data-dir``.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import engine_paths

PROJECT_ROOT = engine_paths.PROJECT_ROOT

ENGINE_ROOT = engine_paths.engine_root()
ASSETS_ROOT = engine_paths.assets_root()
WEIGHTS_ROOT = engine_paths.weights_root()
MODEL_ROOT = WEIGHTS_ROOT / "GPT_SoVITS" / "pretrained_models"

MOUNT_REPORT: dict[str, Any] = {}


def refresh(engine: Path | None = None) -> dict[str, Any]:
    """Recompute roots and (re)create the asset mounts in the engine tree."""
    global ENGINE_ROOT, ASSETS_ROOT, WEIGHTS_ROOT, MODEL_ROOT, MOUNT_REPORT
    ENGINE_ROOT = Path(engine) if engine is not None else engine_paths.engine_root()
    ASSETS_ROOT = engine_paths.assets_root()
    WEIGHTS_ROOT = engine_paths.weights_root()
    MODEL_ROOT = WEIGHTS_ROOT / "GPT_SoVITS" / "pretrained_models"
    MOUNT_REPORT = engine_paths.ensure_mounts(ENGINE_ROOT)
    if MOUNT_REPORT.get("engine_root"):
        ENGINE_ROOT = Path(MOUNT_REPORT["engine_root"])
    return MOUNT_REPORT


def _definitions() -> list[dict[str, Any]]:
    return [
        {
            "id": "engine",
            "name": "GPT-SoVITS 引擎源码",
            "path": ENGINE_ROOT,
            "required": True,
            "kind": "dir",
            "probe": "GPT_SoVITS/TTS_infer_pack/TTS.py",
            "note": "vendor/GPT-SoVITS（锁定 commit，随安装包分发）",
        },
        {
            "id": "bert",
            "name": "中文 BERT",
            "path": MODEL_ROOT / "chinese-roberta-wwm-ext-large",
            "required": True,
            "kind": "dir",
            "note": "文本前端依赖",
        },
        {
            "id": "hubert",
            "name": "HuBERT",
            "path": MODEL_ROOT / "chinese-hubert-base",
            "required": True,
            "kind": "dir",
            "note": "语音编码器",
        },
        {
            "id": "gpt",
            "name": "GPT 底模 s1v3",
            "path": MODEL_ROOT / "s1v3.ckpt",
            "required": True,
            "kind": "file",
            "note": "V5 共用 GPT",
        },
        {
            "id": "sovits",
            "name": "SoVITS V5 Turbo",
            "path": MODEL_ROOT / "gsv-v5-pretrained" / "s2Gv5turbo.pth",
            "required": True,
            "kind": "file",
            "note": "V5 默认声学模型（48k，4 步）",
        },
        {
            "id": "vocoder",
            "name": "V5 Vocoder",
            "path": MODEL_ROOT / "gsv-v5-pretrained" / "vocoder.pth",
            "required": True,
            "kind": "file",
            "note": "V5 原生 48k 声码器",
        },
        {
            "id": "sv",
            "name": "说话人验证 SV",
            "path": MODEL_ROOT / "sv" / "pretrained_eres2netv2w24s4ep4.ckpt",
            "required": True,
            "kind": "file",
            "note": "参考音频音色校验",
        },
        {
            "id": "g2pw",
            "name": "G2PW 中文前端",
            "path": WEIGHTS_ROOT / "GPT_SoVITS" / "text" / "G2PWModel",
            "required": True,
            "kind": "dir",
            "probe": "g2pW.onnx",
            "note": "中文多音字",
        },
        {
            "id": "langdetect",
            "name": "自动语种识别",
            "path": MODEL_ROOT / "fast_langdetect" / "lid.176.bin",
            "required": False,
            "kind": "file",
            "note": "文本前端自动语种检测（可选）",
        },
        {
            "id": "uvr5",
            "name": "UVR5 人声分离",
            "path": WEIGHTS_ROOT / "tools" / "uvr5" / "uvr5_weights",
            "required": False,
            "kind": "dir",
            "probe": "HP2_all_vocals.pth",
            "note": "训练可选",
        },
        {
            "id": "asr",
            "name": "ASR 模型",
            "path": WEIGHTS_ROOT / "tools" / "asr" / "models",
            "required": False,
            "kind": "dir",
            "note": "训练可选；可在线下载",
        },
        {
            "id": "supersampling",
            "name": "超分（AP-BWE）",
            "path": WEIGHTS_ROOT / "tools" / "AP_BWE_main" / "24kto48k",
            "required": False,
            "kind": "dir",
            "note": "V5 超采样可选",
        },
        {
            "id": "ffmpeg",
            "name": "ffmpeg / ffprobe",
            "path": ASSETS_ROOT / "bin",
            "required": False,
            "kind": "dir",
            "probes": ["ffmpeg.exe", "ffmpeg"],
            "note": "音频转码与切片",
        },
    ]


def _hashes() -> dict[str, tuple[Path, str]]:
    return {
        "bert": (
            MODEL_ROOT / "chinese-roberta-wwm-ext-large" / "pytorch_model.bin",
            "e53a693acc59ace251d143d068096ae0d7b79e4b1b503fa84c9dcf576448c1d8",
        ),
        "hubert": (
            MODEL_ROOT / "chinese-hubert-base" / "pytorch_model.bin",
            "24164f129c66499d1346e2aa55f183250c223161ec2770c0da3d3b08cf432d3c",
        ),
        "gpt": (MODEL_ROOT / "s1v3.ckpt", "87133414860ea14ff6620c483a3db5ed07b44be42e2c3fcdad65523a729a745a"),
        "sovits": (
            MODEL_ROOT / "gsv-v5-pretrained" / "s2Gv5turbo.pth",
            "287b32a06b7d486f5303ec520468b0728fb01aac8b0f5d86fd5455c9a1d3e022",
        ),
        "vocoder": (
            MODEL_ROOT / "gsv-v5-pretrained" / "vocoder.pth",
            "b7543c83222aa2105bb4efb56845086bc5f2eeba61243d723ffa062052b3221f",
        ),
        "sv": (
            MODEL_ROOT / "sv" / "pretrained_eres2netv2w24s4ep4.ckpt",
            "4f5a0bf73c61eb41b174e1bb54e7ee3c83233892be8e0af1f187024e8e581a35",
        ),
        "g2pw": (
            WEIGHTS_ROOT / "GPT_SoVITS" / "text" / "G2PWModel" / "g2pW.onnx",
            "2eb3c71fd95117b2e1abef8d2d0cd78aae894bbe7f0fac105ddc9c32ce63cbd0",
        ),
        "uvr5": (
            WEIGHTS_ROOT / "tools" / "uvr5" / "uvr5_weights" / "HP2_all_vocals.pth",
            "39796caa5db18d7f9382d8ac997ac967bfd85f7761014bb807d2543cc844ef05",
        ),
    }


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _present(asset: dict[str, Any]) -> bool:
    path: Path = asset["path"]
    if asset["kind"] == "dir":
        if not path.is_dir():
            return False
        probes = asset.get("probes") or ([asset["probe"]] if asset.get("probe") else [])
        if probes:
            return any((path / probe).exists() for probe in probes)
        return True
    return path.is_file() and path.stat().st_size > 0


def asset_status(asset: dict[str, Any]) -> dict[str, Any]:
    path: Path = asset["path"]
    present = _present(asset)
    size = _size(path) if present else 0
    expected = _hashes().get(asset["id"])
    return {
        "id": asset["id"],
        "name": asset["name"],
        "path": str(path),
        "required": asset["required"],
        "kind": asset["kind"],
        "note": asset["note"],
        "present": present,
        "size": size,
        "sha256": expected[1] if expected else "",
        "hash_path": str(expected[0]) if expected else "",
    }


def list_assets() -> dict[str, Any]:
    items = [asset_status(a) for a in _definitions()]
    missing = [a["id"] for a in items if a["required"] and not a["present"]]
    return {
        "engine_root": str(ENGINE_ROOT),
        "engine_source": str(engine_paths.engine_source()),
        "assets_root": str(ASSETS_ROOT),
        "weights_root": str(WEIGHTS_ROOT),
        "model_root": str(MODEL_ROOT),
        "items": items,
        "missing": missing,
        "ready": not missing,
        "mounts": MOUNT_REPORT.get("mounts", []),
        "mount_error": MOUNT_REPORT.get("error", ""),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets() -> dict[str, Any]:
    hashes = _hashes()
    items = []
    for asset in _definitions():
        status = asset_status(asset)
        expected = hashes.get(asset["id"])
        status["hash_ok"] = None
        if expected:
            hash_path = expected[0]
            if hash_path.exists():
                status["actual_sha256"] = _sha256(hash_path)
                status["hash_ok"] = status["actual_sha256"] == expected[1]
            else:
                status["hash_ok"] = False
        items.append(status)
    missing = [a["id"] for a in items if a["required"] and not a["present"]]
    bad_hash = [a["id"] for a in items if a["hash_ok"] is False]
    payload = list_assets()
    payload.update(
        {
            "items": items,
            "missing": missing,
            "bad_hash": bad_hash,
            "ready": not missing and not bad_hash,
        }
    )
    return payload


def import_asset(asset_id: str, source_path: str) -> dict[str, Any]:
    asset = next((a for a in _definitions() if a["id"] == asset_id), None)
    if not asset:
        raise KeyError(f"unknown asset: {asset_id}")
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))
    target: Path = asset["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if asset["kind"] == "dir":
        if source.is_file():
            raise ValueError("expected a directory")
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        if source.is_dir():
            raise ValueError("expected a file")
        shutil.copy2(source, target)
    refresh()
    status = asset_status(next(a for a in _definitions() if a["id"] == asset_id))
    expected = _hashes().get(asset_id)
    if expected and expected[0].exists():
        actual = _sha256(expected[0])
        if actual != expected[1]:
            raise ValueError(f"sha256 mismatch for {asset_id}: {actual} != {expected[1]}")
    return status
