"""VoiceSmith local engine sidecar.

M0/M1: FastAPI shell with health, doctor, voices, mock preview and mock
async synthesis. The real GPT-SoVITS inference/training adapter lands in M2.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import threading
import time
import uuid
import wave
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

import assets as asset_store
import asset_install
import asr as asr_engine
import dataset as dataset_qc
import engine_paths
import slice as slice_engine
import training as training_runner
import uvr5 as uvr5_engine
from real_engine import RealEngine

APP_VERSION = "0.2.8"
TOKEN = ""
DATA_DIR = Path.cwd() / ".data"
DB_PATH = DATA_DIR / "voice_smith.db"
OUTPUT_DIR = DATA_DIR / "outputs"
MODEL_DIR = DATA_DIR / "models"
LOCK = threading.Lock()
STOP_EVENT = threading.Event()
REAL_ENGINE: Optional[RealEngine] = None
REAL_ENGINE_LOCK = threading.Lock()

app = FastAPI(title="VoiceSmith Engine", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not TOKEN:
        return
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="invalid engine token")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def builtin_voices_dir() -> Optional[Path]:
    candidates = [Path(__file__).resolve().parent / "builtin_voices"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(Path(bundle) / "builtin_voices")
    for candidate in candidates:
        if (candidate / "manifest.json").is_file():
            return candidate
    return None


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK, closing(connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS voices (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              type TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              request_id TEXT UNIQUE,
              text TEXT NOT NULL,
              voice_id TEXT NOT NULL,
              params_json TEXT NOT NULL,
              status TEXT NOT NULL,
              progress INTEGER NOT NULL DEFAULT 0,
              audio_path TEXT,
              error TEXT,
              batch_id TEXT,
              created_at TEXT NOT NULL,
              finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trainings (
              id TEXT PRIMARY KEY,
              request_id TEXT UNIQUE,
              exp_name TEXT NOT NULL,
              dataset_list TEXT NOT NULL,
              status TEXT NOT NULL,
              stage TEXT NOT NULL DEFAULT 'queued',
              progress INTEGER NOT NULL DEFAULT 0,
              detail TEXT NOT NULL DEFAULT '',
              log_path TEXT,
              output_dir TEXT,
              s1_model TEXT,
              s2_model TEXT,
              created_at TEXT NOT NULL,
              finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS emotions (
              id TEXT PRIMARY KEY,
              voice_id TEXT NOT NULL,
              name TEXT NOT NULL,
              ref_audio_path TEXT NOT NULL,
              ref_text TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        existing = {row[1] for row in conn.execute("PRAGMA table_info(voices)").fetchall()}
        for column, ddl in {
            "ref_audio_path": "TEXT",
            "ref_text": "TEXT",
            "prompt_lang": "TEXT DEFAULT 'zh'",
            "text_lang": "TEXT DEFAULT 'zh'",
            "model_version": "TEXT DEFAULT 'v5turbo'",
            "engine": "TEXT DEFAULT 'mock'",
            "s1_model": "TEXT",
            "s2_model": "TEXT",
        }.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE voices ADD COLUMN {column} {ddl}")
        existing_jobs = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "batch_id" not in existing_jobs:
            conn.execute("ALTER TABLE jobs ADD COLUMN batch_id TEXT")
        conn.execute(
            "INSERT OR IGNORE INTO voices(id,name,type,status,created_at) VALUES(?,?,?,?,?)",
            ("demo_edge", "示例音色（Mock）", "free", "ready", now_iso()),
        )
        conn.execute(
            "UPDATE trainings SET status='failed', detail='engine restarted', finished_at=? "
            "WHERE status IN ('queued','running','cancelling')",
            (now_iso(),),
        )
        sample = DATA_DIR / "sample" / "ref_hui.wav"
        if sample.exists():
            ref_dir = DATA_DIR / "voices" / "demo_hui"
            ref_dir.mkdir(parents=True, exist_ok=True)
            ref_file = ref_dir / "ref.wav"
            if not ref_file.exists():
                shutil.copy2(sample, ref_file)
            conn.execute(
                """
                INSERT OR IGNORE INTO voices(
                  id,name,type,status,created_at,ref_audio_path,ref_text,prompt_lang,text_lang,model_version,engine
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "demo_hui",
                    "示例音色（Huihui 参考）",
                    "quick",
                    "ready",
                    now_iso(),
                    str(ref_file),
                    "先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。",
                    "zh",
                    "zh",
                    "v5turbo",
                    "gpt-sovits",
                ),
            )
            conn.execute("UPDATE voices SET model_version='v5turbo' WHERE id='demo_hui'")
        builtin = builtin_voices_dir()
        if builtin:
            manifest = json.loads((builtin / "manifest.json").read_text(encoding="utf-8"))
            for item in manifest.get("voices", []):
                source = builtin / str(item["file"])
                if not source.is_file():
                    continue
                ref_dir = DATA_DIR / "voices" / str(item["id"])
                ref_dir.mkdir(parents=True, exist_ok=True)
                ref_file = ref_dir / "ref.wav"
                shutil.copy2(source, ref_file)
                conn.execute(
                    """
                    INSERT INTO voices(
                      id,name,type,status,created_at,ref_audio_path,ref_text,prompt_lang,text_lang,model_version,engine
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                      name=excluded.name,
                      ref_audio_path=excluded.ref_audio_path,
                      ref_text=excluded.ref_text,
                      status='ready'
                    """,
                    (
                        str(item["id"]),
                        str(item["name"]),
                        "quick",
                        "ready",
                        now_iso(),
                        str(ref_file),
                        str(item["ref_text"]),
                        str(item.get("prompt_lang") or "zh"),
                        str(item.get("text_lang") or "zh"),
                        "v5turbo",
                        "gpt-sovits",
                    ),
                )
        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    with LOCK, closing(connect()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    with LOCK, closing(connect()) as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def get_voice(voice_id: str) -> Optional[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        row = conn.execute("SELECT * FROM voices WHERE id = ?", (voice_id,)).fetchone()
        return dict(row) if row else None


def list_voices() -> list[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM voices ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]


def delete_voice(voice_id: str) -> bool:
    voice = get_voice(voice_id)
    if not voice:
        return False
    with LOCK, closing(connect()) as conn:
        conn.execute("DELETE FROM voices WHERE id = ?", (voice_id,))
        conn.commit()
    target = DATA_DIR / "voices" / voice_id
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    return True


def list_emotions(voice_id: str) -> list[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM emotions WHERE voice_id = ? ORDER BY created_at ASC", (voice_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_emotion(emotion_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not emotion_id:
        return None
    with LOCK, closing(connect()) as conn:
        row = conn.execute("SELECT * FROM emotions WHERE id = ?", (emotion_id,)).fetchone()
        return dict(row) if row else None


def create_emotion(voice_id: str, name: str, ref_audio_path: str, ref_text: str) -> dict[str, Any]:
    if not get_voice(voice_id):
        raise FileNotFoundError("voice not found")
    source = Path(ref_audio_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))
    emotion_id = f"emo_{uuid.uuid4().hex[:12]}"
    target_dir = DATA_DIR / "voices" / voice_id / "emotions"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{emotion_id}{source.suffix or '.wav'}"
    shutil.copy2(source, target)
    with LOCK, closing(connect()) as conn:
        conn.execute(
            "INSERT INTO emotions(id,voice_id,name,ref_audio_path,ref_text,created_at) VALUES(?,?,?,?,?,?)",
            (emotion_id, voice_id, name, str(target), ref_text, now_iso()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM emotions WHERE id = ?", (emotion_id,)).fetchone()
        return dict(row)


def delete_emotion(emotion_id: str) -> bool:
    emotion = get_emotion(emotion_id)
    if not emotion:
        return False
    with LOCK, closing(connect()) as conn:
        conn.execute("DELETE FROM emotions WHERE id = ?", (emotion_id,))
        conn.commit()
    path = Path(emotion["ref_audio_path"])
    if path.exists():
        path.unlink(missing_ok=True)
    return True


def register_trained_voice(
    training_id: str,
    record: dict[str, Any],
    s1_model: Optional[str],
    s2_model: Optional[str],
) -> Optional[str]:
    if not s1_model or not s2_model:
        return None
    list_path = Path(str(record.get("dataset_list") or ""))
    if not list_path.exists():
        return None
    sample_audio = ""
    sample_text = ""
    for raw in list_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            sample_audio, sample_text = parts[0].strip(), parts[3].strip()
            break
    if not sample_audio or not Path(sample_audio).exists() or not sample_text:
        return None
    voice_id = f"trained_{training_id[-6:]}"
    ref_dir = DATA_DIR / "voices" / voice_id
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_file = ref_dir / "ref.wav"
    if not ref_file.exists():
        shutil.copy2(sample_audio, ref_file)
    with LOCK, closing(connect()) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO voices(
              id,name,type,status,created_at,ref_audio_path,ref_text,prompt_lang,text_lang,model_version,engine,s1_model,s2_model
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                voice_id,
                f"{record.get('exp_name') or '微调'}（微调）",
                "trained",
                "ready",
                now_iso(),
                str(ref_file),
                sample_text,
                "zh",
                "zh",
                "v5turbo",
                "gpt-sovits",
                s1_model,
                s2_model,
            ),
        )
        conn.execute(
            "UPDATE voices SET s1_model=?, s2_model=?, status='ready' WHERE id=?",
            (s1_model, s2_model, voice_id),
        )
        conn.commit()
    return voice_id


def real_ready() -> bool:
    if not asset_store.list_assets().get("ready"):
        return False
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def get_real_engine() -> RealEngine:
    global REAL_ENGINE
    with REAL_ENGINE_LOCK:
        if REAL_ENGINE is None:
            REAL_ENGINE = RealEngine(
                asset_store.ENGINE_ROOT, DATA_DIR / "logs" / "engine.log", DATA_DIR
            )
        return REAL_ENGINE


def run_real_job(job_id: str, text: str, voice: dict[str, Any], params: dict[str, Any]) -> None:
    emotion = get_emotion(str(params.get("emotion_id") or ""))
    ref = emotion["ref_audio_path"] if emotion else voice.get("ref_audio_path")
    ref_text = emotion["ref_text"] if emotion else voice.get("ref_text")
    if not ref or not Path(ref).exists() or not ref_text:
        update_job(job_id, status="failed", error="voice has no reference audio", finished_at=now_iso())
        return
    out = OUTPUT_DIR / f"{job_id}.wav"
    log_path = DATA_DIR / "logs" / "engine.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    update_job(job_id, status="running", progress=10)
    request = {
        "id": job_id,
        "text": text,
        "ref": str(ref),
        "ref_text": ref_text,
        "out": str(out),
        "text_lang": str(voice.get("text_lang") or "zh"),
        "prompt_lang": str(voice.get("prompt_lang") or "zh"),
        "speed": params.get("speed", 1.0),
        "seed": params.get("seed", -1),
        "s1_model": voice.get("s1_model"),
        "s2_model": voice.get("s2_model"),
    }
    try:
        response = get_real_engine().synthesize(request)
        current = get_job(job_id)
        if not current or current["status"] == "cancelled":
            return
        if not out.exists():
            update_job(job_id, status="failed", error="engine returned no audio", finished_at=now_iso())
            return
        update_job(job_id, status="succeeded", progress=100, audio_path=str(out), finished_at=now_iso())
    except Exception as exc:  # noqa: BLE001
        update_job(job_id, status="failed", error=str(exc)[-2000:], finished_at=now_iso())


def job_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    if item.get("audio_path"):
        item["audio_url"] = f"/api/v1/syntheses/{item['id']}/audio"
    else:
        item["audio_url"] = None
    return item


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return job_row(row) if row else None


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [job_row(r) for r in rows]


def create_job(
    text: str,
    voice_id: str,
    params: dict[str, Any],
    request_id: Optional[str],
    batch_id: Optional[str] = None,
) -> dict[str, Any]:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    with LOCK, closing(connect()) as conn:
        if request_id:
            row = conn.execute("SELECT * FROM jobs WHERE request_id = ?", (request_id,)).fetchone()
            if row:
                return job_row(row)
        conn.execute(
            """
            INSERT INTO jobs(id, request_id, text, voice_id, params_json, status, progress, batch_id, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                job_id,
                request_id,
                text,
                voice_id,
                json.dumps(params, ensure_ascii=False),
                "queued",
                0,
                batch_id,
                now_iso(),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return job_row(row)


def update_job(job_id: str, **fields: Any) -> None:
    allowed = {"status", "progress", "audio_path", "error", "finished_at"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    with LOCK, closing(connect()) as conn:
        conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*updates.values(), job_id))
        conn.commit()


def make_wav(duration: float = 1.0, sample_rate: int = 32000, freq: float = 440.0) -> bytes:
    frames = max(1, int(duration * sample_rate))
    fade = max(1, int(sample_rate * 0.03))
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(frames):
            env = min(1.0, i / fade, (frames - i) / fade)
            value = int(0.16 * 32767 * env * math.sin(2 * math.pi * freq * i / sample_rate))
            wf.writeframes(struct.pack("<h", max(-32768, min(32767, value))))
    return buf.getvalue()


def run_mock_job(job_id: str, text: str) -> None:
    steps = max(4, min(10, len(text) // 80 + 4))
    for step in range(1, steps + 1):
        if STOP_EVENT.is_set():
            return
        current = get_job(job_id)
        if not current or current["status"] == "cancelled":
            return
        time.sleep(0.25)
        update_job(job_id, status="running", progress=int(step / steps * 92))
    current = get_job(job_id)
    if not current or current["status"] == "cancelled":
        return
    duration = max(0.8, min(8.0, len(text) * 0.04))
    path = OUTPUT_DIR / f"{job_id}.wav"
    path.write_bytes(make_wav(duration=duration, freq=392.0))
    update_job(
        job_id,
        status="succeeded",
        progress=100,
        audio_path=str(path),
        finished_at=now_iso(),
    )


class PreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    voice_id: str = "demo_edge"
    params: dict[str, Any] = Field(default_factory=dict)


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    voice_id: str = "demo_edge"
    params: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


class BatchSynthesisRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=50)
    voice_id: str = "demo_edge"
    params: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


class EmotionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    ref_audio_path: str
    ref_text: str = Field(min_length=1, max_length=500)


class DatasetQCRequest(BaseModel):
    dataset_list: str


class ASRRequest(BaseModel):
    audio_path: str
    language: str = "zh"


class ASRFolderRequest(BaseModel):
    audio_dir: str
    language: str = "zh"
    speaker: str = "speaker"


class UVR5Request(BaseModel):
    audio_path: str


class SliceRequest(BaseModel):
    audio_path: str
    min_sec: float = 5.0
    max_sec: float = 15.0


class AssetInstallRequest(BaseModel):
    url: str = ""
    sha256: str = ""


class TrainingRequest(BaseModel):
    dataset_list: str
    exp_name: str = Field(default="my_voice", min_length=1, max_length=40)
    s1_epochs: int = Field(default=5, ge=1, le=50)
    s2_epochs: int = Field(default=2, ge=1, le=50)
    batch_size: int = Field(default=2, ge=1, le=8)
    num_workers: int = Field(default=2, ge=1, le=8)
    force: bool = False
    request_id: Optional[str] = None


class DoctorCheck(BaseModel):
    id: str
    name: str
    status: str
    detail: str
    fix: str = ""


@app.get("/health")
def health() -> dict[str, Any]:
    assets_ready = bool(asset_store.list_assets().get("ready"))
    engine_ready = real_ready()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "engine": "gpt-sovits" if engine_ready else "mock",
        "model": "v5turbo" if engine_ready else "none",
        "mock": not engine_ready,
        "assets_ready": assets_ready,
        "python": sys.version.split()[0],
        "data_dir": str(DATA_DIR),
        "engine_source": str(asset_store.ENGINE_ROOT),
        "assets_root": str(asset_store.ASSETS_ROOT),
    }


@app.get("/api/v1/terms")
def terms() -> dict[str, Any]:
    return {"accepted": get_setting("terms_accepted") == "1"}


@app.post("/api/v1/terms/accept")
def terms_accept() -> dict[str, Any]:
    set_setting("terms_accepted", "1")
    return {"ok": True, "accepted": True}


@app.get("/api/v1/diagnostics", dependencies=[Depends(require_token)])
def diagnostics() -> Response:
    payload = {
        "version": APP_VERSION,
        "health": health(),
        "doctor": doctor(),
        "assets": asset_store.list_assets(),
        "python": sys.version,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(payload, ensure_ascii=False, indent=2))
        for name in ("sidecar.log", "engine.log"):
            path = DATA_DIR / "logs" / name
            if path.exists():
                archive.writestr(name, path.read_text(encoding="utf-8", errors="replace")[-20000:])
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="voicesmith-diagnostics.zip"'},
    )


@app.post("/api/v1/doctor/run", dependencies=[Depends(require_token)])
def doctor() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    py = sys.version_info
    py_ok = (3, 10) <= (py.major, py.minor) <= (3, 12)
    checks.append({
        "id": "python", "name": "Python 版本",
        "status": "pass" if py_ok else "warn",
        "detail": f"{py.major}.{py.minor}.{py.micro}",
        "fix": "" if py_ok else "GPT-SoVITS 推荐 Python 3.10–3.12；请切换 sidecar 运行时",
    })

    torch_ok = False
    try:
        import torch  # type: ignore
        torch_ok = True
        checks.append({
            "id": "torch", "name": "PyTorch",
            "status": "pass", "detail": torch.__version__,
            "fix": "",
        })
        cuda_ok = bool(torch.cuda.is_available())
        checks.append({
            "id": "cuda", "name": "CUDA",
            "status": "pass" if cuda_ok else "fail",
            "detail": torch.version.cuda or "not available",
            "fix": "" if cuda_ok else "妫€鏌?NVIDIA 驱动/CUDA wheel",
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({
            "id": "torch", "name": "PyTorch",
            "status": "fail", "detail": str(exc),
            "fix": "安装与 CUDA 匹配的 torch/torchaudio",
        })
        checks.append({
            "id": "cuda", "name": "CUDA",
            "status": "fail", "detail": "torch 未安装，无法检测",
            "fix": "先安装 torch",
        })

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        detail = out.stdout.strip().splitlines()[0] if out.stdout.strip() else "no GPU"
        checks.append({
            "id": "gpu", "name": "GPU",
            "status": "pass" if out.returncode == 0 else "fail",
            "detail": detail,
            "fix": "" if out.returncode == 0 else "安装/更新 NVIDIA 驱动",
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({
            "id": "gpu", "name": "GPU",
            "status": "fail", "detail": str(exc),
            "fix": "安装 NVIDIA 椹卞姩骞剁‘淇?nvidia-smi 可用",
        })

    ffmpeg = str(engine_paths.ffmpeg_path() or "")
    checks.append({
        "id": "ffmpeg", "name": "ffmpeg",
        "status": "pass" if ffmpeg else "fail",
        "detail": ffmpeg or "not found",
        "fix": "" if ffmpeg else "将 ffmpeg.exe/ffprobe.exe 放入资产目录 assets/bin 或 PATH",
    })

    try:
        free_gb = shutil.disk_usage(DATA_DIR).free / (1024 ** 3)
        checks.append({
            "id": "disk", "name": "磁盘空间",
            "status": "pass" if free_gb >= 20 else "warn",
            "detail": f"{free_gb:.1f} GB free",
            "fix": "" if free_gb >= 20 else "建议预留 20GB 以上",
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({
            "id": "disk", "name": "磁盘空间",
            "status": "fail", "detail": str(exc), "fix": "检查数据目录权限",
        })

    asset_state = asset_store.list_assets()
    by_id = {item["id"]: item for item in asset_state["items"]}
    frontend_ids = ["bert", "hubert", "g2pw"]
    missing_frontend = [i for i in frontend_ids if not by_id.get(i, {}).get("present")]
    checks.append({
        "id": "text_frontend", "name": "文本前端（BERT/HuBERT/G2PW）",
        "status": "pass" if not missing_frontend else "warn",
        "detail": "已就绪" if not missing_frontend else "缺少：" + ", ".join(missing_frontend),
        "fix": "" if not missing_frontend else "在模型资产页导入/下载 BERT、HuBERT、G2PWModel",
    })
    weight_ids = ["gpt", "sovits", "vocoder", "sv"]
    missing_weights = [i for i in weight_ids if not by_id.get(i, {}).get("present")]
    checks.append({
        "id": "weights", "name": "GPT/SoVITS/SV 权重",
        "status": "pass" if not missing_weights else "warn",
        "detail": "已就绪" if not missing_weights else "缺少：" + ", ".join(missing_weights),
        "fix": "" if not missing_weights else "在模型资产页导入 s1v3/s2Gv5turbo/vocoder.pth/SV 权重",
    })

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for item in checks:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"checks": checks, "summary": counts, "ok": counts["fail"] == 0}


@app.get("/api/v1/voices", dependencies=[Depends(require_token)])
def voices() -> dict[str, Any]:
    return {"items": list_voices()}


@app.delete("/api/v1/voices/{voice_id}", dependencies=[Depends(require_token)])
def voice_delete(voice_id: str) -> dict[str, Any]:
    if not delete_voice(voice_id):
        raise HTTPException(status_code=404, detail="voice not found")
    return {"ok": True, "voice_id": voice_id}


@app.get("/api/v1/voices/{voice_id}/emotions", dependencies=[Depends(require_token)])
def emotions(voice_id: str) -> dict[str, Any]:
    return {"items": list_emotions(voice_id)}


@app.post("/api/v1/voices/{voice_id}/emotions", status_code=201, dependencies=[Depends(require_token)])
def emotion_create(voice_id: str, req: EmotionRequest) -> dict[str, Any]:
    try:
        return create_emotion(voice_id, req.name, req.ref_audio_path, req.ref_text)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/v1/emotions/{emotion_id}", dependencies=[Depends(require_token)])
def emotion_delete(emotion_id: str) -> dict[str, Any]:
    if not delete_emotion(emotion_id):
        raise HTTPException(status_code=404, detail="emotion not found")
    return {"ok": True, "emotion_id": emotion_id}


def training_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["log_url"] = f"/api/v1/trainings/{item['id']}/log"
    return item


def get_training(training_id: str) -> Optional[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        row = conn.execute("SELECT * FROM trainings WHERE id = ?", (training_id,)).fetchone()
        return training_row(row) if row else None


def list_trainings(limit: int = 30) -> list[dict[str, Any]]:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM trainings ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [training_row(r) for r in rows]


TRAINING_FIELDS = {
    "status",
    "stage",
    "progress",
    "detail",
    "log_path",
    "output_dir",
    "s1_model",
    "s2_model",
    "finished_at",
}


def update_training(training_id: str, **fields: Any) -> None:
    updates = {key: value for key, value in fields.items() if key in TRAINING_FIELDS}
    if not updates:
        return
    with LOCK, closing(connect()) as conn:
        columns = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(f"UPDATE trainings SET {columns} WHERE id = ?", (*updates.values(), training_id))
        conn.commit()


def create_training_record(req: TrainingRequest) -> dict[str, Any]:
    training_id = f"train_{uuid.uuid4().hex[:12]}"
    log_path = DATA_DIR / "training" / "logs" / f"{training_id}.log"
    with LOCK, closing(connect()) as conn:
        if req.request_id:
            row = conn.execute("SELECT * FROM trainings WHERE request_id = ?", (req.request_id,)).fetchone()
            if row:
                return training_row(row)
        conn.execute(
            """
            INSERT INTO trainings(id,request_id,exp_name,dataset_list,status,stage,progress,detail,log_path,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (training_id, req.request_id, req.exp_name, req.dataset_list, "queued", "queued", 0, "排队", str(log_path), now_iso()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM trainings WHERE id = ?", (training_id,)).fetchone()
        return training_row(row)


def training_callback(training_id: str, **fields: Any) -> None:
    stage = str(fields.get("stage") or "")
    status = "running"
    if stage == "done":
        status = "succeeded"
    elif stage == "failed":
        status = "failed"
    elif stage == "cancelled":
        status = "cancelled"
    if status in {"succeeded", "failed", "cancelled"}:
        fields["finished_at"] = now_iso()
    fields["status"] = status
    update_training(training_id, **fields)
    if status == "succeeded":
        record = get_training(training_id)
        if record:
            register_trained_voice(training_id, record, record.get("s1_model"), record.get("s2_model"))


@app.post("/api/v1/datasets/qc", dependencies=[Depends(require_token)])
def dataset_qc_run(req: DatasetQCRequest) -> dict[str, Any]:
    path = Path(req.dataset_list).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="dataset list not found")
    return dataset_qc.analyze_dataset(path)


@app.post("/api/v1/asr", dependencies=[Depends(require_token)])
def asr_transcribe(req: ASRRequest) -> dict[str, Any]:
    path = Path(req.audio_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="audio not found")
    try:
        return {"text": asr_engine.transcribe(path, req.language)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ASR failed: {exc}") from exc


@app.post("/api/v1/datasets/transcribe", dependencies=[Depends(require_token)])
def dataset_transcribe(req: ASRFolderRequest) -> dict[str, Any]:
    folder = Path(req.audio_dir).expanduser().resolve()
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="audio directory not found")
    try:
        return asr_engine.transcribe_folder(folder, req.language, req.speaker)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ASR failed: {exc}") from exc


@app.post("/api/v1/uvr5", dependencies=[Depends(require_token)])
def uvr5_separate(req: UVR5Request) -> dict[str, Any]:
    path = Path(req.audio_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="audio not found")
    try:
        return uvr5_engine.separate(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"UVR5 failed: {exc}") from exc


@app.post("/api/v1/datasets/slice", dependencies=[Depends(require_token)])
def dataset_slice(req: SliceRequest) -> dict[str, Any]:
    path = Path(req.audio_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="audio not found")
    try:
        return slice_engine.slice_audio(path, DATA_DIR / "datasets" / "slices", req.min_sec, req.max_sec)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"slice failed: {exc}") from exc


@app.post("/api/v1/trainings", status_code=202, dependencies=[Depends(require_token)])
def training_create(req: TrainingRequest) -> dict[str, Any]:
    if not Path(req.dataset_list).expanduser().exists():
        raise HTTPException(status_code=404, detail="dataset list not found")
    record = create_training_record(req)
    if record["status"] == "queued":
        threading.Thread(
            target=training_runner.run_training,
            args=(
                record["id"],
                {
                    "dataset_list": req.dataset_list,
                    "exp_name": req.exp_name,
                    "s1_epochs": req.s1_epochs,
                    "s2_epochs": req.s2_epochs,
                    "batch_size": req.batch_size,
                    "num_workers": req.num_workers,
                    "force": req.force,
                },
                training_callback,
            ),
            daemon=True,
        ).start()
    return record


@app.get("/api/v1/trainings", dependencies=[Depends(require_token)])
def trainings() -> dict[str, Any]:
    return {"items": list_trainings()}


@app.get("/api/v1/models", dependencies=[Depends(require_token)])
def models() -> dict[str, Any]:
    root = DATA_DIR / "training" / "experiments"
    items: list[dict[str, Any]] = []
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".ckpt", ".pth"}:
                continue
            if "ckpt" in path.parts and path.suffix.lower() == ".ckpt":
                kind = "s1-checkpoint"
            elif path.suffix.lower() == ".ckpt":
                kind = "s1"
            elif path.name.startswith("G_"):
                kind = "s2-g"
            elif path.name.startswith("D_"):
                kind = "s2-d"
            else:
                kind = "s2"
            stat = path.stat()
            items.append(
                {
                    "id": path.relative_to(DATA_DIR).as_posix(),
                    "name": path.name,
                    "experiment": path.relative_to(root).parts[0] if path.relative_to(root).parts else "",
                    "kind": kind,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "path": str(path),
                }
            )
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"items": items}


@app.delete("/api/v1/models", dependencies=[Depends(require_token)])
def model_delete(path: str = Query(..., min_length=1)) -> dict[str, Any]:
    root = (DATA_DIR / "training" / "experiments").resolve()
    target = (DATA_DIR / path).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() not in {".ckpt", ".pth"}:
        raise HTTPException(status_code=400, detail="invalid model path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="model not found")
    target.unlink()
    return {"ok": True, "path": str(target)}


@app.get("/api/v1/trainings/{training_id}", dependencies=[Depends(require_token)])
def training_get(training_id: str) -> dict[str, Any]:
    record = get_training(training_id)
    if not record:
        raise HTTPException(status_code=404, detail="training not found")
    return record


@app.get("/api/v1/trainings/{training_id}/log", dependencies=[Depends(require_token)])
def training_log(training_id: str, limit: int = 12000) -> dict[str, Any]:
    record = get_training(training_id)
    if not record:
        raise HTTPException(status_code=404, detail="training not found")
    return {"training_id": training_id, "log": training_runner.log_tail(training_id, limit)}


@app.post("/api/v1/trainings/{training_id}/publish", dependencies=[Depends(require_token)])
def training_publish(training_id: str) -> dict[str, Any]:
    record = get_training(training_id)
    if not record:
        raise HTTPException(status_code=404, detail="training not found")
    if record["status"] != "succeeded":
        raise HTTPException(status_code=409, detail="training is not succeeded")
    voice_id = register_trained_voice(training_id, record, record.get("s1_model"), record.get("s2_model"))
    if not voice_id:
        raise HTTPException(status_code=409, detail="training has no usable model/ref audio")
    voice = get_voice(voice_id)
    return {"ok": True, "voice_id": voice_id, "voice": voice}


@app.post("/api/v1/trainings/{training_id}/cancel", dependencies=[Depends(require_token)])
def training_cancel(training_id: str) -> dict[str, Any]:
    record = get_training(training_id)
    if not record:
        raise HTTPException(status_code=404, detail="training not found")
    if record["status"] in {"succeeded", "failed", "cancelled"}:
        return record
    update_training(training_id, status="cancelling", detail="正在取消")
    training_runner.request_cancel(training_id)
    # Give the worker a moment to tear down the process tree so one click is
    # enough; force the terminal state if it is stuck between stages.
    for _ in range(50):
        time.sleep(0.1)
        current = get_training(training_id)
        if current and current["status"] in {"succeeded", "failed", "cancelled"}:
            return current
    update_training(training_id, status="cancelled", detail="已取消")
    return get_training(training_id) or record


class AssetImportRequest(BaseModel):
    asset_id: str
    source_path: str


@app.get("/api/v1/assets", dependencies=[Depends(require_token)])
def assets() -> dict[str, Any]:
    return asset_store.list_assets()


@app.post("/api/v1/assets/verify", dependencies=[Depends(require_token)])
def assets_verify() -> dict[str, Any]:
    return asset_store.verify_assets()


@app.post("/api/v1/assets/import", dependencies=[Depends(require_token)])
def assets_import(req: AssetImportRequest) -> dict[str, Any]:
    try:
        return asset_store.import_asset(req.asset_id, req.source_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"source not found: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/assets/asset-pack", dependencies=[Depends(require_token)])
def asset_pack_status() -> dict[str, Any]:
    return asset_install.status()


@app.post("/api/v1/assets/asset-pack/install", status_code=202, dependencies=[Depends(require_token)])
def asset_pack_install(req: AssetInstallRequest) -> dict[str, Any]:
    return asset_install.start(req.url, req.sha256)


@app.post("/api/v1/previews", dependencies=[Depends(require_token)])
def preview(req: PreviewRequest) -> Response:
    voice = get_voice(req.voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    emotion = get_emotion(str(req.params.get("emotion_id") or ""))
    ref = emotion["ref_audio_path"] if emotion else voice.get("ref_audio_path")
    ref_text = emotion["ref_text"] if emotion else voice.get("ref_text")
    if real_ready() and (not ref or not Path(ref).exists() or not ref_text):
        raise HTTPException(status_code=400, detail="voice has no reference audio")
    if real_ready():
        preview_id = f"preview_{uuid.uuid4().hex[:12]}"
        out = OUTPUT_DIR / f"{preview_id}.wav"
        request = {
            "id": preview_id,
            "text": req.text,
            "ref": str(ref),
            "ref_text": ref_text,
            "out": str(out),
            "text_lang": str(voice.get("text_lang") or "zh"),
            "prompt_lang": str(voice.get("prompt_lang") or "zh"),
            "speed": req.params.get("speed", 1.0),
            "seed": req.params.get("seed", -1),
            "s1_model": voice.get("s1_model"),
            "s2_model": voice.get("s2_model"),
        }
        try:
            get_real_engine().synthesize(request)
            return Response(content=out.read_bytes(), media_type="audio/wav")
        finally:
            out.unlink(missing_ok=True)
    duration = max(0.8, min(6.0, len(req.text) * 0.04))
    audio = make_wav(duration=duration, freq=440.0)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"X-VoiceSmith-Mock": "1", "X-Sample-Rate": "32000"},
    )


@app.post("/api/v1/syntheses", status_code=202, dependencies=[Depends(require_token)])
def create_synthesis(req: SynthesisRequest) -> dict[str, Any]:
    voice = get_voice(req.voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    if real_ready() and not voice.get("ref_audio_path"):
        raise HTTPException(status_code=400, detail="voice has no reference audio")
    job = create_job(req.text, req.voice_id, req.params, req.request_id)
    if job["status"] in {"queued", "running"}:
        if real_ready() and voice.get("ref_audio_path"):
            threading.Thread(target=run_real_job, args=(job["id"], req.text, voice, req.params), daemon=True).start()
        else:
            threading.Thread(target=run_mock_job, args=(job["id"], req.text), daemon=True).start()
    return {"job_id": job["id"], "status": job["status"]}


def run_batch_jobs(batch_id: str, jobs: list[dict[str, Any]], voice: dict[str, Any], params: dict[str, Any]) -> None:
    for job in jobs:
        current = get_job(job["id"])
        if not current or current["status"] == "cancelled":
            continue
        if real_ready() and voice.get("ref_audio_path"):
            run_real_job(job["id"], job["text"], voice, params)
        else:
            run_mock_job(job["id"], job["text"])


@app.post("/api/v1/syntheses/batch", status_code=202, dependencies=[Depends(require_token)])
def create_batch(req: BatchSynthesisRequest) -> dict[str, Any]:
    voice = get_voice(req.voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    if real_ready() and not voice.get("ref_audio_path"):
        raise HTTPException(status_code=400, detail="voice has no reference audio")
    texts = [text.strip() for text in req.texts if text.strip()]
    if not texts:
        raise HTTPException(status_code=400, detail="batch is empty")
    if any(len(text) > 10000 for text in texts):
        raise HTTPException(status_code=400, detail="one item exceeds 10,000 characters")
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    jobs = []
    for index, text in enumerate(texts):
        request_id = f"{req.request_id}:{index}" if req.request_id else None
        jobs.append(create_job(text, req.voice_id, req.params, request_id, batch_id))
    threading.Thread(target=run_batch_jobs, args=(batch_id, jobs, voice, req.params), daemon=True).start()
    return {"batch_id": batch_id, "jobs": jobs}


@app.get("/api/v1/syntheses/batch/{batch_id}", dependencies=[Depends(require_token)])
def batch_status(batch_id: str) -> dict[str, Any]:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE batch_id = ? ORDER BY created_at ASC", (batch_id,)).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="batch not found")
    jobs = [job_row(row) for row in rows]
    done = [job for job in jobs if job["status"] in {"succeeded", "failed", "cancelled"}]
    progress = round(sum(job["progress"] for job in jobs) / len(jobs)) if jobs else 0
    return {
        "batch_id": batch_id,
        "jobs": jobs,
        "total": len(jobs),
        "done": len(done),
        "progress": progress,
        "status": "succeeded" if len(done) == len(jobs) and all(job["status"] == "succeeded" for job in jobs) else "running",
    }


@app.get("/api/v1/syntheses/batch/{batch_id}/zip", dependencies=[Depends(require_token)])
def batch_zip(batch_id: str) -> Response:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE batch_id = ? ORDER BY created_at ASC", (batch_id,)).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="batch not found")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, row in enumerate(rows, 1):
            path = row["audio_path"]
            if path and Path(path).exists():
                archive.write(path, f"{index:03d}_{row['id']}.wav")
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{batch_id}.zip"'},
    )


@app.post("/api/v1/syntheses/batch/{batch_id}/cancel", dependencies=[Depends(require_token)])
def batch_cancel(batch_id: str) -> dict[str, Any]:
    with LOCK, closing(connect()) as conn:
        rows = conn.execute("SELECT id FROM jobs WHERE batch_id = ?", (batch_id,)).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE jobs SET status='cancelled', finished_at=? WHERE id=? AND status IN ('queued','running')",
                (now_iso(), row["id"]),
            )
        conn.commit()
    return {"ok": True, "batch_id": batch_id}


@app.get("/api/v1/syntheses/{job_id}", dependencies=[Depends(require_token)])
def synthesis(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/v1/syntheses/{job_id}/audio", dependencies=[Depends(require_token)])
def synthesis_audio(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if not job or not job.get("audio_path"):
        raise HTTPException(status_code=404, detail="audio not ready")
    return FileResponse(job["audio_path"], media_type="audio/wav", filename=f"{job_id}.wav")


@app.get("/api/v1/syntheses/{job_id}/export", dependencies=[Depends(require_token)])
def synthesis_export(job_id: str, format: str = Query(default="mp3", pattern="^(wav|mp3)$")) -> FileResponse:
    job = get_job(job_id)
    if not job or not job.get("audio_path"):
        raise HTTPException(status_code=404, detail="audio not ready")
    wav = Path(job["audio_path"])
    if format == "wav":
        return FileResponse(wav, media_type="audio/wav", filename=f"{job_id}.wav")
    mp3 = wav.with_suffix(".mp3")
    if not mp3.exists():
        ffmpeg = str(engine_paths.ffmpeg_path() or "ffmpeg")
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3)],
                capture_output=True,
                timeout=120,
                check=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"mp3 export failed: {exc}") from exc
    return FileResponse(mp3, media_type="audio/mpeg", filename=f"{job_id}.mp3")


@app.post("/api/v1/syntheses/{job_id}/cancel", dependencies=[Depends(require_token)])
def cancel_synthesis(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job["status"] in {"queued", "running"}:
        update_job(job_id, status="cancelled", finished_at=now_iso())
    return {"ok": True, "status": "cancelled"}


@app.get("/api/v1/jobs", dependencies=[Depends(require_token)])
def jobs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {"items": list_jobs(limit)}


@app.delete("/api/v1/jobs/{job_id}", dependencies=[Depends(require_token)])
def job_delete(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    audio_path = job.get("audio_path")
    if audio_path:
        target = Path(audio_path).resolve()
        root = OUTPUT_DIR.resolve()
        if target == root or root in target.parents:
            target.unlink(missing_ok=True)
    with LOCK, closing(connect()) as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
    return {"ok": True, "job_id": job_id}


@app.get("/api/v1/events")
async def events(
    job_id: str,
    token: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
) -> StreamingResponse:
    if TOKEN and token != TOKEN and authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="invalid engine token")

    async def stream():
        last: Optional[str] = None
        while not STOP_EVENT.is_set():
            job = get_job(job_id)
            if not job:
                yield "event: error\ndata: {\"message\":\"job not found\"}\n\n"
                return
            payload = {
                "id": job["id"],
                "status": job["status"],
                "progress": job["progress"],
                "error": job.get("error"),
                "audio_url": job.get("audio_url"),
            }
            raw = json.dumps(payload, ensure_ascii=False)
            if raw != last:
                yield f"event: state\ndata: {raw}\n\n"
                last = raw
            if job["status"] in {"succeeded", "failed", "cancelled"}:
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/shutdown")
def shutdown() -> dict[str, Any]:
    STOP_EVENT.set()
    training_runner.cancel_all()
    engine = REAL_ENGINE
    if engine is not None:
        engine.stop()
    threading.Timer(0.2, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    return {"ok": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", type=str, default="")
    parser.add_argument("--data-dir", type=str, default=str(Path.cwd() / ".data"))
    args = parser.parse_args()

    global TOKEN, DATA_DIR, DB_PATH, OUTPUT_DIR, MODEL_DIR
    TOKEN = args.token
    DATA_DIR = Path(args.data_dir).resolve()
    DB_PATH = DATA_DIR / "voice_smith.db"
    OUTPUT_DIR = DATA_DIR / "outputs"
    MODEL_DIR = DATA_DIR / "models"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ[engine_paths.DATA_ENV] = str(DATA_DIR)
    mount_report = asset_store.refresh()
    engine_root = asset_store.ENGINE_ROOT
    init_db()
    training_runner.configure(DATA_DIR, engine_root)
    asr_engine.configure(DATA_DIR, engine_root)
    uvr5_engine.configure(DATA_DIR, engine_root)
    asset_install.configure(DATA_DIR, engine_root)

    print(f"VoiceSmith engine ready on http://127.0.0.1:{args.port}", flush=True)
    print(f"engine source: {engine_root}", flush=True)
    print(f"asset store:   {asset_store.ASSETS_ROOT}", flush=True)
    if mount_report.get("error"):
        print(f"asset mounts:  {mount_report['error']}", flush=True)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()

