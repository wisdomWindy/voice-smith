"""Deterministic 5–15s slicing for training audio."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def slice_audio(
    source: Path,
    output_root: Path,
    min_sec: float = 5.0,
    max_sec: float = 15.0,
) -> dict[str, Any]:
    data, sr = sf.read(str(source), always_2d=True, dtype="float32")
    mono = data.mean(axis=1)
    active = np.flatnonzero(np.abs(mono) >= 0.005)
    if active.size:
        mono = mono[active[0] : active[-1] + 1]
    if not mono.size:
        raise ValueError("audio is silent")

    # 10s windows keep natural phrases while staying inside the 5–15s gate.
    window = int(sr * min(max_sec, max(min_sec, 10.0)))
    work = output_root / f"slice_{uuid.uuid4().hex[:10]}"
    work.mkdir(parents=True, exist_ok=True)
    items = []
    for index, start in enumerate(range(0, len(mono), window)):
        chunk = mono[start : start + window]
        if len(chunk) < int(sr * min_sec):
            continue
        target_sr = 48000
        if sr != target_sr:
            duration = len(chunk) / sr
            chunk = np.interp(
                np.linspace(0, len(chunk) - 1, int(duration * target_sr)),
                np.arange(len(chunk)),
                chunk,
            ).astype(np.float32)
        path = work / f"part_{index:03d}.wav"
        sf.write(str(path), chunk, target_sr, subtype="PCM_16")
        items.append(
            {
                "path": str(path),
                "duration": round(len(chunk) / target_sr, 3),
                "samplerate": target_sr,
            }
        )
    if not items:
        raise ValueError(f"audio shorter than {min_sec}s")
    return {"output_dir": str(work), "count": len(items), "items": items}
