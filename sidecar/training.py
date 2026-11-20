"""Training orchestration for GPT-SoVITS.

This module runs the upstream preparation scripts and S1/S2 training in a
background thread. It intentionally uses the engine's own scripts instead of
reimplementing model code.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import soundfile as sf
import yaml

import dataset as dataset_qc

CREATE_NO_WINDOW = 0x0800_0000 if os.name == "nt" else 0
CREATE_NEW_PROCESS_GROUP = 0x0000_0200 if os.name == "nt" else 0

ROOT: Optional[Path] = None
ENGINE: Optional[Path] = None
_LOCK = threading.Lock()
_CURRENT: dict[str, subprocess.Popen[str]] = {}
_CANCEL: set[str] = set()


class TrainingCancelled(Exception):
    pass


def configure(data_dir: Path, engine_root: Path) -> None:
    global ROOT, ENGINE
    ROOT = data_dir / "training"
    ENGINE = engine_root
    ROOT.mkdir(parents=True, exist_ok=True)


def request_cancel(job_id: str) -> None:
    with _LOCK:
        _CANCEL.add(job_id)
        proc = _CURRENT.get(job_id)
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
            )
        else:
            proc.terminate()


def cancel_all() -> None:
    with _LOCK:
        ids = list(_CURRENT)
    for job_id in ids:
        request_cancel(job_id)


def log_tail(job_id: str, limit: int = 12000) -> str:
    if ROOT is None:
        return ""
    path = ROOT / "logs" / f"{job_id}.log"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-limit:]


def _append(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")


def _check_cancel(job_id: str) -> None:
    if job_id in _CANCEL:
        raise TrainingCancelled


def _log_has_oom(log_path: Path) -> bool:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")[-8000:].lower()
    except Exception:
        return False
    return "out of memory" in text or "outofmemoryerror" in text or "cuda error: out of memory" in text()


def _python_command(script: Path, engine: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-script", str(script), "--engine", str(engine)]
    if script.name.startswith("s2_train_v3"):
        wrapper = Path(__file__).resolve().parent / "v5_train.py"
        return [sys.executable, str(wrapper), str(script)]
    return [sys.executable, str(script)]


def _run(
    job_id: str,
    label: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
) -> None:
    _check_cancel(job_id)
    _append(log_path, f"\n=== {label} ===\n$ {' '.join(command)}")
    log_file = log_path.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        )
        with _LOCK:
            _CURRENT[job_id] = proc
        while proc.poll() is None:
            if job_id in _CANCEL:
                request_cancel(job_id)
                raise TrainingCancelled()
            time.sleep(0.25)
        if job_id in _CANCEL:
            raise TrainingCancelled()
        if proc.returncode != 0:
            raise RuntimeError(f"{label} failed (exit {proc.returncode}); see training log")
        _append(log_path, f"=== {label} OK ===")
    finally:
        log_file.close()
        with _LOCK:
            _CURRENT.pop(job_id, None)


def _validate_dataset(list_path: Path) -> tuple[list[dict[str, Any]], Path, float]:
    entries: list[dict[str, Any]] = []
    total = 0.0
    for line_no, raw in enumerate(list_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 3)
        if len(parts) != 4:
            raise ValueError(f"line {line_no}: expected path|speaker|lang|text")
        path, speaker, lang, text = (part.strip() for part in parts)
        wav = Path(path)
        if not wav.exists():
            raise ValueError(f"line {line_no}: audio not found: {wav}")
        if not text:
            raise ValueError(f"line {line_no}: empty transcript")
        info = sf.info(str(wav))
        total += float(info.duration)
        entries.append({"path": str(wav), "speaker": speaker or "speaker", "lang": lang or "zh", "text": text})
    if not entries:
        raise ValueError("dataset list is empty")
    return entries, Path(entries[0]["path"]).parent, total


def _base_env() -> dict[str, str]:
    assert ENGINE is not None
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ENGINE / 'GPT_SoVITS'}{os.pathsep}{ENGINE}"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["HF_ENDPOINT"] = env.get("HF_ENDPOINT", "https://hf-mirror.com")
    env["OMP_NUM_THREADS"] = "4"
    env["PATH"] = f"{ENGINE / 'runtime'}{os.pathsep}{ENGINE}{os.pathsep}{env.get('PATH', '')}"
    return env


def _write_s1(exp_dir: Path, epochs: int, batch_size: int, num_workers: int = 1) -> Path:
    assert ENGINE is not None
    config = {
        "train": {
            "seed": 1234,
            "epochs": int(epochs),
            "batch_size": int(batch_size),
            "save_every_n_epoch": 1,
            "precision": "16-mixed",
            "gradient_clip": 1.0,
            "if_save_latest": True,
            "if_save_every_weights": True,
            "half_weights_save_dir": str(exp_dir / "logs_s1"),
            "exp_name": exp_dir.name,
        },
        "optimizer": {"lr": 0.01, "lr_init": 0.00001, "lr_end": 0.0001, "warmup_steps": 2000, "decay_steps": 40000},
        "data": {"max_eval_sample": 8, "max_sec": 20, "num_workers": int(num_workers), "pad_val": 1024},
        "model": {
            "vocab_size": 1025,
            "phoneme_vocab_size": 732,
            "embedding_dim": 512,
            "hidden_dim": 512,
            "head": 16,
            "linear_units": 2048,
            "n_layer": 24,
            "dropout": 0,
            "EOS": 1024,
            "random_bert": 0,
        },
        "inference": {"top_k": 15},
        "train_semantic_path": str(exp_dir / "6-name2semantic-0.tsv"),
        "train_phoneme_path": str(exp_dir / "2-name2text-0.txt"),
        "output_dir": str(exp_dir / "logs_s1"),
        "pretrained_s1": str(ENGINE / "GPT_SoVITS" / "pretrained_models" / "s1v3.ckpt"),
    }
    path = exp_dir / "s1.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _write_s2(exp_dir: Path, epochs: int, segment_size: int = 20480, num_workers: int = 1) -> Path:
    assert ENGINE is not None
    base = json.loads((ENGINE / "GPT_SoVITS" / "configs" / "s2.json").read_text(encoding="utf-8"))
    base["train"].update(
        {
            "epochs": int(epochs),
            "batch_size": 1,
            "segment_size": int(segment_size),
            "log_interval": 1,
            "eval_interval": 1000,
            "grad_ckpt": True,
            "gpu_numbers": "0",
            "save_every_epoch": 1,
            "if_save_latest": 0,
            "if_save_every_weights": True,
            "pretrained_s2G": str(ENGINE / "GPT_SoVITS" / "pretrained_models" / "gsv-v5-pretrained" / "s2Gv5turbo.pth"),
            "pretrained_s2D": "",
        }
    )
    base["data"]["exp_dir"] = str(exp_dir)
    base["data"]["num_workers"] = int(num_workers)
    base["model"]["version"] = "v5turbo"
    base["model"]["gin_channels"] = 512
    base["s2_ckpt_dir"] = str(exp_dir / "logs_s2_v5turbo")
    base["name"] = exp_dir.name
    base["save_weight_dir"] = str(exp_dir / "logs_s2_v5turbo")
    path = exp_dir / "s2.json"
    path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _newest(path: Path, pattern: str) -> Optional[Path]:
    files = sorted(path.glob(pattern), key=lambda item: item.stat().st_mtime)
    return files[-1] if files else None


def run_training(job_id: str, spec: dict[str, Any], on_update: Callable[..., None]) -> None:
    assert ROOT is not None and ENGINE is not None
    log_path = ROOT / "logs" / f"{job_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    exp_name = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", str(spec.get("exp_name") or "voice"))[:40] or "voice"
    exp_dir = ROOT / "experiments" / f"{exp_name}_{job_id[-6:]}"
    exp_dir.mkdir(parents=True, exist_ok=True)

    try:
        on_update(job_id, stage="validate", progress=3, detail="校验数据集")
        list_path = Path(str(spec["dataset_list"])).expanduser().resolve()
        if not list_path.exists():
            raise ValueError(f"dataset list not found: {list_path}")
        entries, wav_dir, total = _validate_dataset(list_path)
        if total < 60 and not spec.get("force"):
            raise ValueError(f"dataset is {total:.1f}s; need at least 60s (or set force)")
        qc = dataset_qc.analyze_dataset(list_path)
        if qc["blocking"] and not spec.get("force"):
            raise ValueError("dataset QC: " + "; ".join(qc["blocking"][:3]))
        _append(
            log_path,
            f"dataset: {len(entries)} files, {total:.1f}s, wav_dir={wav_dir}; "
            f"qc_errors={len(qc['errors'])}, qc_blocking={len(qc['blocking'])}",
        )

        env = _base_env()
        gpt = ENGINE / "GPT_SoVITS"
        common = {
            "inp_text": str(list_path),
            "inp_wav_dir": str(wav_dir),
            "exp_name": exp_dir.name,
            "i_part": "0",
            "all_parts": "1",
            "opt_dir": str(exp_dir),
            "is_half": "True",
            "version": "v5turbo",
        }

        on_update(job_id, stage="text", progress=12, detail="文本与 BERT 特征")
        env1 = {**env, **common, "bert_pretrained_dir": str(gpt / "pretrained_models" / "chinese-roberta-wwm-ext-large")}
        _run(job_id, "1-get-text", _python_command(gpt / "prepare_datasets" / "1-get-text.py", ENGINE), ENGINE, env1, log_path)
        text_out = exp_dir / "2-name2text-0.txt"
        if not text_out.exists() or text_out.stat().st_size < 10:
            raise RuntimeError("1-get-text produced no usable text; see training log")

        on_update(job_id, stage="hubert", progress=28, detail="HuBERT 与 32k 音频")
        env2 = {**env, **common, "cnhubert_base_dir": str(gpt / "pretrained_models" / "chinese-hubert-base")}
        _run(job_id, "2-get-hubert", _python_command(gpt / "prepare_datasets" / "2-get-hubert-wav32k.py", ENGINE), ENGINE, env2, log_path)

        on_update(job_id, stage="sv", progress=40, detail="说话人向量")
        env_sv = {**env, **common, "sv_path": str(gpt / "pretrained_models" / "sv" / "pretrained_eres2netv2w24s4ep4.ckpt")}
        _run(job_id, "2-get-sv", _python_command(gpt / "prepare_datasets" / "2-get-sv.py", ENGINE), ENGINE, env_sv, log_path)

        on_update(job_id, stage="semantic", progress=50, detail="语义 token")
        semantic_cfg = json.loads((gpt / "configs" / "s2.json").read_text(encoding="utf-8"))
        semantic_cfg["model"].pop("version", None)
        semantic_cfg["model"]["gin_channels"] = 512
        semantic_cfg_path = exp_dir / "s2_semantic.json"
        semantic_cfg_path.write_text(json.dumps(semantic_cfg, ensure_ascii=False), encoding="utf-8")
        env3 = {
            **env,
            **common,
            "pretrained_s2G": str(gpt / "pretrained_models" / "gsv-v5-pretrained" / "s2Gv5turbo.pth"),
            "s2config_path": str(semantic_cfg_path),
        }
        _run(job_id, "3-get-semantic", _python_command(gpt / "prepare_datasets" / "3-get-semantic.py", ENGINE), ENGINE, env3, log_path)
        semantic_out = exp_dir / "6-name2semantic-0.tsv"
        if not semantic_out.exists() or semantic_out.stat().st_size < 10:
            raise RuntimeError("3-get-semantic produced no usable tokens; see training log")

        shutil.copy2(exp_dir / "2-name2text-0.txt", exp_dir / "2-name2text.txt")

        s1_epochs = max(1, min(int(spec.get("s1_epochs", 5)), 50))
        s2_epochs = max(1, min(int(spec.get("s2_epochs", 2)), 50))
        batch = max(1, min(int(spec.get("batch_size", 2)), 8))
        num_workers = max(1, min(int(spec.get("num_workers", 2)), 8))

        on_update(job_id, stage="s1", progress=58, detail=f"S1 训练 · {s1_epochs} epochs")
        s1_config = _write_s1(exp_dir, s1_epochs, batch, num_workers)
        oom_retries = 0
        while True:
            try:
                _run(job_id, "S1 train", _python_command(gpt / "s1_train.py", ENGINE) + ["-c", str(s1_config)], gpt, env, log_path)
                break
            except RuntimeError:
                if batch <= 1 or oom_retries >= 3 or not _log_has_oom(log_path):
                    raise
                batch = max(1, batch // 2)
                oom_retries += 1
                _append(log_path, f"=== S1 OOM detected; retry {oom_retries} with batch={batch} ===")
                on_update(job_id, stage="s1", progress=58, detail=f"S1 OOM 自愈 · batch={batch}")
                s1_config = _write_s1(exp_dir, s1_epochs, batch, num_workers)

        on_update(job_id, stage="s2", progress=76, detail=f"S2 训练 · {s2_epochs} epochs")
        s2_config = _write_s2(exp_dir, s2_epochs, num_workers=num_workers)
        try:
            _run(job_id, "S2 train", _python_command(gpt / "s2_train_v3.py", ENGINE) + ["-c", str(s2_config)], gpt, env, log_path)
        except RuntimeError:
            if not _log_has_oom(log_path):
                raise
            _append(log_path, "=== S2 OOM detected; retry with segment_size=10240 ===")
            on_update(job_id, stage="s2", progress=76, detail="S2 OOM 自愈 · segment=10240")
            s2_config = _write_s2(exp_dir, s2_epochs, segment_size=10240, num_workers=num_workers)
            _run(job_id, "S2 train (OOM retry)", _python_command(gpt / "s2_train_v3.py", ENGINE) + ["-c", str(s2_config)], gpt, env, log_path)

        s1_model = _newest(exp_dir / "logs_s1", f"{exp_dir.name}-e{s1_epochs}.ckpt") or _newest(exp_dir / "logs_s1", "*.ckpt")
        s2_model = (
            _newest(exp_dir / "logs_s2_v5turbo", f"{exp_dir.name}_e{s2_epochs}_s*.pth")
            or _newest(exp_dir / "logs_s2_v5turbo", "*_s*.pth")
            or _newest(exp_dir / "logs_s2_v5turbo", "G_*.pth")
        )
        on_update(
            job_id,
            stage="done",
            progress=100,
            detail="训练完成",
            output_dir=str(exp_dir),
            s1_model=str(s1_model) if s1_model else None,
            s2_model=str(s2_model) if s2_model else None,
        )
    except TrainingCancelled:
        _append(log_path, "training cancelled by user")
        on_update(job_id, stage="cancelled", progress=0, detail="已取消")
    except Exception as exc:  # noqa: BLE001
        _append(log_path, f"training failed: {exc}")
        on_update(job_id, stage="failed", progress=0, detail=str(exc)[:1000])
    finally:
        with _LOCK:
            _CANCEL.discard(job_id)
            _CURRENT.pop(job_id, None)
