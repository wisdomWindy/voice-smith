"""One-shot GPT-SoVITS inference (debug / smoke tests).

Engine source comes from ``vendor/GPT-SoVITS``; weights come from
``<data>/assets`` and are mounted into the engine tree by
``engine_paths.ensure_mounts``. The sidecar normally uses ``gpt_worker.py``
(persistent process); this entry point is for scripts and manual checks.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_paths

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--text", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--ref-text", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--text-lang", default="zh")
    parser.add_argument("--prompt-lang", default="zh")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    engine = Path(args.engine).resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else engine_paths.data_root()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ[engine_paths.DATA_ENV] = str(data_dir)
    mount_report = engine_paths.ensure_mounts(engine)
    engine = Path(mount_report.get("engine_root") or engine).resolve()

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    os.chdir(engine)
    sys.path.insert(0, str(engine))
    sys.path.insert(0, str(engine / "GPT_SoVITS"))
    os.environ.setdefault(
        "bert_path",
        str(engine_paths.weights_root() / "GPT_SoVITS" / "pretrained_models" / "chinese-roberta-wwm-ext-large"),
    )

    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    is_half = device == "cuda"

    weights = engine_paths.weights_root()
    base_path = engine / "GPT_SoVITS" / "configs" / "tts_infer.yaml"
    base: dict = {}
    if base_path.is_file():
        base = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    custom = dict(base.get("custom") or {})
    custom.update(
        {
            "device": device,
            "is_half": is_half,
            "version": "v5turbo",
            "t2s_weights_path": str(weights / "GPT_SoVITS" / "pretrained_models" / "s1v3.ckpt"),
            "vits_weights_path": str(
                weights / "GPT_SoVITS" / "pretrained_models" / "gsv-v5-pretrained" / "s2Gv5turbo.pth"
            ),
            "cnhuhbert_base_path": str(weights / "GPT_SoVITS" / "pretrained_models" / "chinese-hubert-base"),
            "bert_base_path": str(
                weights / "GPT_SoVITS" / "pretrained_models" / "chinese-roberta-wwm-ext-large"
            ),
        }
    )
    config_path = data_dir / "config" / "tts_infer_voicesmith.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump({"custom": custom}, allow_unicode=True), encoding="utf-8")

    from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

    tts = TTS(TTS_Config(str(config_path)))
    req = {
        "text": args.text,
        "text_lang": args.text_lang,
        "ref_audio_path": str(Path(args.ref).resolve()),
        "prompt_text": args.ref_text,
        "prompt_lang": args.prompt_lang,
        "top_k": 15,
        "top_p": 1.0,
        "temperature": 1.0,
        "text_split_method": "cut5",
        "batch_size": 1,
        "speed_factor": args.speed,
        "seed": args.seed,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
        "sample_steps": 4,
        "super_sampling": False,
        "media_type": "wav",
    }
    chunks: list[np.ndarray] = []
    sample_rate = 32000
    for sr, audio in tts.run(req):
        sample_rate = int(sr)
        arr = np.asarray(audio)
        if np.issubdtype(arr.dtype, np.integer):
            arr = arr.astype(np.float32) / 32768.0
        else:
            arr = arr.astype(np.float32)
        chunks.append(arr.reshape(-1))
    if not chunks:
        raise RuntimeError("GPT-SoVITS produced no audio")
    sf.write(str(out), np.concatenate(chunks), sample_rate)
    print(f"OK {out} sr={sample_rate} seconds={sum(len(c) for c in chunks) / sample_rate:.2f}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
