"""UVR5 vocal/instrumental separation using the engine's HP2 model.

The UVR5 weights are assets (``<data>/assets/gpt-sovits/tools/uvr5/uvr5_weights``);
the separation code stays in the vendored engine source.
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import engine_paths

_ROOT: Path | None = None
_ENGINE: Path | None = None
_WEIGHTS: Path | None = None
_MODEL = None
_LOCK = threading.Lock()


def configure(data_dir: Path, engine_root: Path) -> None:
    global _ROOT, _ENGINE, _WEIGHTS
    os.environ[engine_paths.DATA_ENV] = str(data_dir)
    _ROOT = data_dir / "uvr5"
    _ROOT.mkdir(parents=True, exist_ok=True)
    report = engine_paths.ensure_mounts(engine_root)
    _ENGINE = Path(report.get("engine_root") or engine_root)
    _WEIGHTS = engine_paths.weights_root()


def _load():
    global _MODEL
    assert _ENGINE is not None
    model_path = (_WEIGHTS or engine_paths.weights_root()) / "tools" / "uvr5" / "uvr5_weights" / "HP2_all_vocals.pth"
    if not model_path.exists():
        raise FileNotFoundError(f"UVR5 model not found: {model_path}")
    if _MODEL is None:
        tools = str(_ENGINE / "tools" / "uvr5")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        for path in (str(_ENGINE / "runtime"), str(_ENGINE)):
            if path not in os.environ.get("PATH", ""):
                os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
        from vr import AudioPre

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _MODEL = AudioPre(10, str(model_path), device, device == "cuda")
    return _MODEL


def separate(audio_path: Path) -> dict[str, Any]:
    assert _ROOT is not None
    audio_path = audio_path.resolve()
    if not audio_path.exists():
        raise FileNotFoundError(str(audio_path))
    work = _ROOT / uuid.uuid4().hex[:12]
    vocal_dir = work / "vocal"
    ins_dir = work / "instrumental"
    vocal_dir.mkdir(parents=True, exist_ok=True)
    ins_dir.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        _load()._path_audio_(str(audio_path), str(ins_dir), str(vocal_dir), "wav")
    vocals = sorted(vocal_dir.glob("*"))
    instrumentals = sorted(ins_dir.glob("*"))
    if not vocals:
        raise RuntimeError("UVR5 produced no vocal track")
    return {
        "vocal_path": str(vocals[0]),
        "instrumental_path": str(instrumentals[0]) if instrumentals else None,
        "work_dir": str(work),
    }
