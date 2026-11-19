"""Local ASR (faster-whisper) for dataset transcription."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import soundfile as sf

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_MODEL = None
_LOCK = threading.Lock()
_ROOT: Path | None = None


def configure(data_dir: Path) -> None:
    global _ROOT
    _ROOT = data_dir / "models" / "faster-whisper"
    _ROOT.mkdir(parents=True, exist_ok=True)


def _model():
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            from faster_whisper import WhisperModel

            _MODEL = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
                download_root=str(_ROOT) if _ROOT else None,
            )
        return _MODEL


def transcribe(path: Path, language: str = "zh") -> str:
    segments, _info = _model().transcribe(str(path), language=language, vad_filter=True)
    return "".join(segment.text for segment in segments).strip()


def transcribe_folder(folder: Path, language: str = "zh", speaker: str = "speaker") -> dict[str, Any]:
    assert _ROOT is not None
    files = sorted([path for path in folder.iterdir() if path.suffix.lower() in {".wav", ".flac", ".mp3"}])
    if not files:
        raise ValueError("no audio files found")
    out_dir = _ROOT.parent.parent / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    list_path = out_dir / f"asr_{folder.name}.list"
    lines: list[str] = []
    total = 0.0
    for path in files:
        text = transcribe(path, language)
        if not text:
            continue
        duration = float(sf.info(str(path)).duration)
        total += duration
        lines.append(f"{path}|{speaker}|{language}|{text}")
    if not lines:
        raise ValueError("ASR produced no text")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"list_path": str(list_path), "count": len(lines), "total_duration": round(total, 3)}
