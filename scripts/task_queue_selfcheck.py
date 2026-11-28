"""Self-check for the sidecar background task queue.

Covers: restart recovery (queued resumes, running fails), FIFO ordering,
cancelling a queued task, cancelling a running task and result persistence.

Run with the sidecar venv: python scripts/task_queue_selfcheck.py
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sidecar"))

import tasks  # noqa: E402

SCHEMA = """
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL DEFAULT '',
  progress REAL NOT NULL DEFAULT 0,
  detail TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
)
"""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    db = Path(tempfile.mkdtemp(prefix="vs-tasks-")) / "tasks.db"
    conn = sqlite3.connect(db)
    conn.execute(SCHEMA)
    conn.execute(
        "INSERT INTO tasks(id,kind,title,status,stage,created_at) VALUES(?,?,?,?,?,?)",
        ("recovered", "work", "queued before restart", "queued", "queued", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO tasks(id,kind,title,status,stage,created_at) VALUES(?,?,?,?,?,?)",
        ("interrupted", "work", "running before restart", "running", "working", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    def work(task_id: str, payload: dict, report) -> dict:
        for step in range(6):
            time.sleep(0.05)
            report(stage=f"step {step}", progress=(step + 1) / 6)
        return {"ok": True}

    tasks.configure(db, {"work": work})
    time.sleep(0.5)
    check(tasks.get("recovered")["status"] == "succeeded", "queued task was not resumed")
    interrupted = tasks.get("interrupted")
    check(interrupted["status"] == "failed", "running task was not failed on restart")
    check("restarted" in interrupted["detail"], "restart reason missing")

    first = tasks.create("work", "first", {})
    second = tasks.create("work", "second", {})
    time.sleep(0.2)
    check(tasks.get(first["id"])["status"] == "running", "first task did not start")
    check(tasks.get(second["id"])["status"] == "queued", "second task ran concurrently")

    tasks.cancel(second["id"])
    check(tasks.get(second["id"])["status"] == "cancelled", "queued cancel failed")
    time.sleep(0.8)
    check(tasks.get(first["id"])["status"] == "succeeded", "first task did not finish")
    check((tasks.get(first["id"])["result"] or {}).get("ok") is True, "result was not persisted")

    third = tasks.create("work", "third", {})
    time.sleep(0.2)
    tasks.cancel(third["id"])
    time.sleep(0.5)
    check(tasks.get(third["id"])["status"] == "cancelled", "running cancel failed")

    tasks.shutdown()
    print("task queue selfcheck OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
