"""Persistent GPT-SoVITS worker.

Loads the TTS pipeline once, then serves JSON-line synthesis requests. The
sidecar keeps one worker alive to avoid a 10-30 s model load per request.

Engine source comes from ``vendor/GPT-SoVITS`` (or the bundled copy); weights
come from ``<data>/assets`` and are mounted into the engine tree by
``engine_paths.ensure_mounts``. The generated ``tts_infer`` config lives in the
data directory and uses absolute weight paths, so nothing is written into the
engine source tree.
"""

from __future__ import annotations

import argparse
import contextlib
import json
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


def _weights() -> Path:
    return engine_paths.weights_root()


def build_config(engine: Path, data_dir: Path) -> Path:
    """Write a data-dir config with absolute asset paths; engine stays read-only."""
    weights = _weights()
    base_path = engine / "GPT_SoVITS" / "configs" / "tts_infer.yaml"
    base: dict = {}
    if base_path.is_file():
        base = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    custom = dict(base.get("custom") or {})
    device = "cuda" if torch.cuda.is_available() else "cpu"
    custom.update(
        {
            "device": device,
            "is_half": device == "cuda",
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
    config_dir = data_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "tts_infer_voicesmith.yaml"
    config_path.write_text(yaml.safe_dump({"custom": custom}, allow_unicode=True), encoding="utf-8")
    return config_path


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--data-dir", default="")
    args = parser.parse_args()
    engine = Path(args.engine).resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else engine_paths.data_root()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ[engine_paths.DATA_ENV] = str(data_dir)
    mount_report = engine_paths.ensure_mounts(engine)
    if mount_report.get("error"):
        print(json.dumps({"event": "warning", "mounts": mount_report}), file=sys.stderr, flush=True)
    engine = Path(mount_report.get("engine_root") or engine).resolve()
    os.chdir(engine)
    os.environ["PATH"] = f"{engine}{os.pathsep}{os.environ.get('PATH', '')}"
    sys.path.insert(0, str(engine))
    sys.path.insert(0, str(engine / "GPT_SoVITS"))
    # chinese2.py reads `bert_path` for its G2PW model_source fallback.
    os.environ.setdefault("bert_path", str(_weights() / "GPT_SoVITS" / "pretrained_models" / "chinese-roberta-wwm-ext-large"))

    config_path = build_config(engine, data_dir)
    with contextlib.redirect_stdout(sys.stderr):
        from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

        tts = TTS(TTS_Config(str(config_path)))

    base_s1 = str(Path(tts.configs.t2s_weights_path).resolve())
    base_s2 = str(Path(tts.configs.vits_weights_path).resolve())
    current_s1 = base_s1
    current_s2 = base_s2

    print(json.dumps({"event": "ready", "device": str(tts.configs.device), "version": str(tts.configs.version),
                      "engine": str(engine), "weights": str(_weights())}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request_id = None
        try:
            req = json.loads(line)
            request_id = req.get("id")
            out = Path(req["out"]).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            requested_s1 = str(Path(req["s1_model"]).resolve()) if req.get("s1_model") else base_s1
            requested_s2 = str(Path(req["s2_model"]).resolve()) if req.get("s2_model") else base_s2
            with contextlib.redirect_stdout(sys.stderr):
                if requested_s1 != current_s1:
                    tts.init_t2s_weights(requested_s1)
                    current_s1 = requested_s1
                if requested_s2 != current_s2:
                    tts.init_vits_weights(requested_s2)
                    current_s2 = requested_s2
            run_req = {
                "text": req["text"],
                "text_lang": req.get("text_lang", "zh"),
                "ref_audio_path": str(Path(req["ref"]).resolve()),
                "prompt_text": req.get("ref_text", ""),
                "prompt_lang": req.get("prompt_lang", "zh"),
                "top_k": 15,
                "top_p": 1.0,
                "temperature": 1.0,
                "text_split_method": "cut5",
                "batch_size": 1,
                "speed_factor": float(req.get("speed", 1.0)),
                "seed": int(req.get("seed", -1)),
                "parallel_infer": True,
                "repetition_penalty": 1.35,
                "sample_steps": 4,
                "super_sampling": False,
                "media_type": "wav",
            }
            chunks: list[np.ndarray] = []
            sr = 32000
            with contextlib.redirect_stdout(sys.stderr):
                for sample_rate, audio in tts.run(run_req):
                    sr = int(sample_rate)
                    arr = np.asarray(audio)
                    if np.issubdtype(arr.dtype, np.integer):
                        arr = arr.astype(np.float32) / 32768.0
                    else:
                        arr = arr.astype(np.float32)
                    chunks.append(arr.reshape(-1))
                if not chunks:
                    raise RuntimeError("GPT-SoVITS produced no audio")
                sf.write(str(out), np.concatenate(chunks), sr)
            seconds = sum(len(c) for c in chunks) / sr
            print(json.dumps({"id": request_id, "ok": True, "out": str(out), "sr": sr, "seconds": seconds}), flush=True)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"id": request_id, "ok": False, "error": str(exc)}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
