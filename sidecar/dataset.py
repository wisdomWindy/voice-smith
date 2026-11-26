"""Dataset list QC without external models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def analyze_dataset(list_path: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    blocking: list[str] = []
    total = 0.0

    text = list_path.read_text(encoding="utf-8-sig")
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 3)
        if len(parts) != 4:
            errors.append(f"line {line_no}: expected path|speaker|lang|text")
            continue
        path_text, speaker, lang, transcript = (part.strip() for part in parts)
        wav = Path(path_text)
        item: dict[str, Any] = {
            "line": line_no,
            "path": str(wav),
            "speaker": speaker,
            "lang": lang,
            "text": transcript,
            "issues": [],
        }
        if not wav.exists():
            item["issues"].append("missing")
            errors.append(f"line {line_no}: missing {wav}")
            items.append(item)
            continue
        if not transcript:
            item["issues"].append("empty transcript")
            blocking.append(f"line {line_no}: empty transcript")
        try:
            info = sf.info(str(wav))
            duration = float(info.duration)
            item.update(
                duration=round(duration, 3),
                samplerate=info.samplerate,
                channels=info.channels,
                format=info.format,
            )
            total += duration
            if duration < 1.0:
                item["issues"].append("too short (<1s)")
                blocking.append(f"line {line_no}: too short")
            elif duration > 30.0:
                item["issues"].append("too long (>30s)")
                blocking.append(f"line {line_no}: too long")
            if info.channels != 1:
                item["issues"].append("not mono")
                blocking.append(f"line {line_no}: {info.channels} channels")
            data, _ = sf.read(str(wav), always_2d=True, dtype="float32")
            mono = data.mean(axis=1)
            if mono.size:
                peak = float(np.max(np.abs(mono)))
                clipping = float(np.mean(np.abs(mono) >= 0.999))
                active = np.flatnonzero(np.abs(mono) >= 0.001)
                if active.size:
                    trimmed = mono[active[0] : active[-1] + 1]
                    silence = float(np.mean(np.abs(trimmed) < 0.001))
                else:
                    silence = 1.0
                item.update(
                    peak=round(peak, 4),
                    clipping_ratio=round(clipping, 6),
                    silence_ratio=round(silence, 4),
                )
                if clipping >= 0.001:
                    item["issues"].append("clipping >=0.1%")
                    blocking.append(f"line {line_no}: clipping")
                # Natural speech pauses routinely dip below -60 dBFS; only treat
                # an effectively silent file as blocking, otherwise just warn.
                if peak < 0.01:
                    item["issues"].append("silent audio")
                    blocking.append(f"line {line_no}: silence")
                elif silence > 0.5:
                    item["issues"].append("mostly silence (>50%)")
        except Exception as exc:  # noqa: BLE001
            item["issues"].append(f"unreadable: {exc}")
            errors.append(f"line {line_no}: {exc}")
        items.append(item)

    if not items:
        errors.append("dataset list is empty")
    if total < 60:
        blocking.append(f"total duration {total:.1f}s < 60s")

    return {
        "count": len(items),
        "total_duration": round(total, 3),
        "items": items,
        "errors": errors,
        "blocking": blocking,
        "warnings": [issue for item in items for issue in item.get("issues", [])],
        "ok": not errors and not blocking,
    }
