"""Serial background task queue for long-running sidecar work.

The queue is deliberately simple: one worker thread, FIFO order, SQLite rows as
the source of truth. A task survives UI navigation; if the sidecar restarts,
running tasks are marked failed and queued tasks are enqueued again.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

DB_PATH: Optional[Path] = None
HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {}
QUEUE: "queue.Queue[str]" = queue.Queue()
CANCELLED: dict[str, threading.Event] = {}
WRITE_LOCK = threading.Lock()
WORKER: Optional[threading.Thread] = None
STOP = threading.Event()

class TaskCancelled(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    assert DB_PATH is not None
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key in ("payload_json", "result_json"):
        raw = item.pop(key, "") or ""
        target = key.replace("_json", "")
        try:
            item[target] = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            item[target] = {}
    return item


def get(task_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _serialize(row) if row else None


def list_tasks(limit: int = 50, kind: str = "") -> list[dict[str, Any]]:
    sql = "SELECT * FROM tasks"
    params: list[Any] = []
    if kind:
        sql += " WHERE kind = ?"
        params.append(kind)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, min(int(limit), 200)))
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_serialize(row) for row in rows]


def update(task_id: str, **fields: Any) -> None:
    if not fields:
        return
    allowed = {
        "status",
        "stage",
        "progress",
        "detail",
        "started_at",
        "finished_at",
        "result_json",
    }
    payload = {key: value for key, value in fields.items() if key in allowed}
    if not payload:
        return
    columns = ", ".join(f"{key} = ?" for key in payload)
    with WRITE_LOCK, _connect() as conn:
        conn.execute(f"UPDATE tasks SET {columns} WHERE id = ?", [*payload.values(), task_id])


def create(kind: str, title: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind not in HANDLERS:
        raise ValueError(f"unknown task kind: {kind}")
    task_id = f"{kind}_{uuid.uuid4().hex[:12]}"
    with WRITE_LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO tasks(id, kind, title, status, stage, progress, detail, payload_json, result_json, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                task_id,
                kind,
                title or kind,
                "queued",
                "queued",
                0.0,
                "",
                json.dumps(payload, ensure_ascii=False),
                "{}",
                _now(),
            ),
        )
    QUEUE.put(task_id)
    return get(task_id)  # type: ignore[return-value]


def cancel(task_id: str) -> dict[str, Any]:
    row = get(task_id)
    if not row:
        raise KeyError(task_id)
    event = CANCELLED.get(task_id)
    if row["status"] == "queued":
        update(task_id, status="cancelled", stage="cancelled", detail="已取消", finished_at=_now())
    elif row["status"] == "running":
        update(task_id, status="cancelling", detail="正在停止…")
        if event is not None:
            event.set()
    return get(task_id)  # type: ignore[return-value]


def _report(task_id: str, event: threading.Event, fields: dict[str, Any]) -> None:
    if event.is_set():
        raise TaskCancelled()
    update(task_id, **fields)


def _execute(task_id: str) -> None:
    row = get(task_id)
    if not row or row["status"] != "queued":
        return
    event = threading.Event()
    CANCELLED[task_id] = event
    update(task_id, status="running", stage="starting", progress=0.0, started_at=_now())
    handler = HANDLERS.get(row["kind"])
    try:
        if handler is None:
            raise RuntimeError(f"unknown task kind: {row['kind']}")
        result = handler(
            task_id,
            row.get("payload") or {},
            lambda **fields: _report(task_id, event, fields),
        )
        if event.is_set():
            raise TaskCancelled()
        update(
            task_id,
            status="succeeded",
            stage="done",
            progress=1.0,
            detail="",
            finished_at=_now(),
            result_json=json.dumps(result or {}, ensure_ascii=False),
        )
    except TaskCancelled:
        update(task_id, status="cancelled", stage="cancelled", detail="已取消", finished_at=_now())
    except Exception as exc:  # noqa: BLE001
        update(task_id, status="failed", stage="failed", detail=str(exc)[:2000], finished_at=_now())
    finally:
        CANCELLED.pop(task_id, None)


def _loop() -> None:
    while not STOP.is_set():
        try:
            task_id = QUEUE.get(timeout=0.5)
        except queue.Empty:
            continue
        if task_id is None:
            return
        _execute(task_id)


def _recover() -> None:
    with WRITE_LOCK, _connect() as conn:
        conn.execute(
            "UPDATE tasks SET status='failed', stage='failed', detail='engine restarted', finished_at=? "
            "WHERE status IN ('running','cancelling')",
            (_now(),),
        )
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status='queued' ORDER BY created_at"
        ).fetchall()
    for row in rows:
        QUEUE.put(row["id"])


def configure(db_path: Path, handlers: dict[str, Callable[..., dict[str, Any]]]) -> None:
    global DB_PATH, HANDLERS, WORKER
    DB_PATH = Path(db_path)
    HANDLERS = handlers
    _recover()
    if WORKER is None or not WORKER.is_alive():
        STOP.clear()
        WORKER = threading.Thread(target=_loop, name="voicesmith-tasks", daemon=True)
        WORKER.start()


def shutdown() -> None:
    STOP.set()
    QUEUE.put(None)  # type: ignore[arg-type]
