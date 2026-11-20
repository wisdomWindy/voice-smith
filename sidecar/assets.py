"""Model asset checks for the GPT-SoVITS engine.

The engine expects its weights under its own directory:
  GPT_SoVITS/pretrained_models/...
  GPT_SoVITS/text/G2PWModel/...
  tools/uvr5/uvr5_weights/...
  tools/asr/models/...
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(
    os.environ.get("VOICE_SMITH_ENGINE", str(PROJECT_ROOT / "engine" / "GPT-SoVITS"))
).resolve()
MODEL_ROOT = ENGINE_ROOT / "GPT_SoVITS" / "pretrained_models"

ASSETS: list[dict[str, Any]] = [
    {
        "id": "engine",
        "name": "GPT-SoVITS 引擎",
        "path": ENGINE_ROOT,
        "required": True,
        "kind": "dir",
        "note": "engine/GPT-SoVITS（锁定 commit）",
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
        "path": ENGINE_ROOT / "GPT_SoVITS" / "text" / "G2PWModel",
        "required": True,
        "kind": "dir",
        "note": "中文多音字",
    },
    {
        "id": "uvr5",
        "name": "UVR5 人声分离",
        "path": ENGINE_ROOT / "tools" / "uvr5" / "uvr5_weights",
        "required": False,
        "kind": "dir",
        "note": "训练可选",
    },
    {
        "id": "asr",
        "name": "ASR 模型",
        "path": ENGINE_ROOT / "tools" / "asr" / "models",
        "required": False,
        "kind": "dir",
        "note": "训练可选；可在线下载",
    },
]


HASHES: dict[str, tuple[Path, str]] = {
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
        ENGINE_ROOT / "GPT_SoVITS" / "text" / "G2PWModel" / "g2pW.onnx",
        "2eb3c71fd95117b2e1abef8d2d0cd78aae894bbe7f0fac105ddc9c32ce63cbd0",
    ),
    "uvr5": (
        ENGINE_ROOT / "tools" / "uvr5" / "uvr5_weights" / "HP2_all_vocals.pth",
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


def asset_status(asset: dict[str, Any]) -> dict[str, Any]:
    path: Path = asset["path"]
    present = path.exists() and (path.is_dir() or path.stat().st_size > 0)
    size = _size(path) if present else 0
    expected = HASHES.get(asset["id"])
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
    items = [asset_status(a) for a in ASSETS]
    missing = [a["id"] for a in items if a["required"] and not a["present"]]
    return {
        "engine_root": str(ENGINE_ROOT),
        "model_root": str(MODEL_ROOT),
        "items": items,
        "missing": missing,
        "ready": not missing,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets() -> dict[str, Any]:
    items = []
    for asset in ASSETS:
        status = asset_status(asset)
        expected = HASHES.get(asset["id"])
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
    return {
        "engine_root": str(ENGINE_ROOT),
        "model_root": str(MODEL_ROOT),
        "items": items,
        "missing": missing,
        "bad_hash": bad_hash,
        "ready": not missing and not bad_hash,
    }


def import_asset(asset_id: str, source_path: str) -> dict[str, Any]:
    asset = next((a for a in ASSETS if a["id"] == asset_id), None)
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
    status = asset_status(asset)
    expected = HASHES.get(asset_id)
    if expected and expected[0].exists():
        actual = _sha256(expected[0])
        if actual != expected[1]:
            raise ValueError(f"sha256 mismatch for {asset_id}: {actual} != {expected[1]}")
    return status
