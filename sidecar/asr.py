"""Local ASR using the GPT-SoVITS V5 FunASR pipeline.

The FunASR models are assets (``<data>/assets/gpt-sovits/tools/asr/models``),
never part of the vendored engine source.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import soundfile as sf

import engine_paths

_MODEL = None
_LOCK = threading.Lock()
_MODEL_ROOT: Path | None = None
_ENGINE: Path | None = None
_WEIGHTS: Path | None = None


def configure(data_dir: Path, engine_root: Path | None = None) -> None:
    global _MODEL_ROOT, _ENGINE, _WEIGHTS
    os.environ[engine_paths.DATA_ENV] = str(data_dir)
    _ENGINE = engine_root or engine_paths.engine_root()
    engine_paths.ensure_mounts(_ENGINE)
    _WEIGHTS = engine_paths.weights_root()
    _MODEL_ROOT = data_dir / "models" / "funasr"
    _MODEL_ROOT.mkdir(parents=True, exist_ok=True)


def _models() -> tuple[Path, Path, Path]:
    root = (_WEIGHTS or engine_paths.weights_root()) / "tools" / "asr" / "models"
    asr = root / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    vad = root / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
    punc = root / "punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
    missing = [p.name for p in (asr, vad, punc) if not p.is_dir()]
    if missing:
        raise RuntimeError("FunASR models missing: " + ", ".join(missing))
    return asr, vad, punc


def _model():
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            from funasr import AutoModel

            asr, vad, punc = _models()
            # FunASR's Paraformer + punc stack can hit CUDA OOM while the main
            # TTS worker is loaded. ASR is short-lived; CPU is stable and keeps
            # VRAM for GPT-SoVITS.
            _MODEL = AutoModel(
                model=str(asr),
                vad_model=str(vad),
                punc_model=str(punc),
                device=os.environ.get("VOICE_SMITH_ASR_DEVICE", "cpu"),
                disable_update=True,
            )
        return _MODEL


def transcribe(path: Path, language: str = "zh") -> str:
    result = _model().generate(input=str(path), batch_size_s=300)
    return str(result[0].get("text", "")).strip()


def transcribe_folder(folder: Path, language: str = "zh", speaker: str = "speaker") -> dict[str, Any]:
    assert _MODEL_ROOT is not None
    files = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".wav", ".flac", ".mp3"})
    if not files:
        raise ValueError("no audio files found")
    out_dir = _MODEL_ROOT.parent.parent / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    list_path = out_dir / f"asr_{folder.name}.list"
    lines: list[str] = []
    total = 0.0
    for path in files:
        text = transcribe(path, language)
        if not text:
            continue
        total += float(sf.info(str(path)).duration)
        lines.append(f"{path}|{speaker}|{language}|{text}")
    if not lines:
        raise ValueError("FunASR produced no text")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"list_path": str(list_path), "count": len(lines), "total_duration": round(total, 3)}
