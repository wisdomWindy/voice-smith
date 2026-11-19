"""Real GPT-SoVITS inference worker.

Run in its own process with cwd = engine root so GPT-SoVITS relative paths work.
The sidecar spawns this only when the engine assets + torch are ready.
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

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
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
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    os.chdir(engine)
    sys.path.insert(0, str(engine))
    sys.path.insert(0, str(engine / "GPT_SoVITS"))

    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    is_half = device == "cuda"

    base = yaml.safe_load((engine / "GPT_SoVITS" / "configs" / "tts_infer.yaml").read_text(encoding="utf-8"))
    custom = dict(base.get("custom") or {})
    custom.update(
        {
            "device": device,
            "is_half": is_half,
            "version": "v4",
            "t2s_weights_path": "GPT_SoVITS/pretrained_models/s1v3.ckpt",
            "vits_weights_path": "GPT_SoVITS/pretrained_models/gsv-v4-pretrained/s2Gv4.pth",
            "cnhuhbert_base_path": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
            "bert_base_path": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
        }
    )
    config_path = out.with_suffix(".yaml")
    config_path.write_text(yaml.safe_dump({"custom": custom}, allow_unicode=True), encoding="utf-8")

    from process_ckpt import head2version

head2version[b"04"] = ["v2", "v4", False]
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
        "sample_steps": 32,
        "super_sampling": False,
        "media_type": "wav",
    }
    chunks: list[np.ndarray] = []
    sample_rate = 32000
    for sr, audio in tts.run(req):
        sample_rate = int(sr)
        chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
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
