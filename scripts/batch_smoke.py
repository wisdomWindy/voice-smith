"""Batch synthesis + ZIP/MP3 export smoke test."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def call(base: str, path: str, token: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), response.headers.get("content-type", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="dev-token")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    raw, _ = call(
        base,
        "/api/v1/syntheses/batch",
        args.token,
        "POST",
        {"texts": ["批量第一段。", "批量第二段。"], "voice_id": "demo_hui", "params": {"speed": 1.0}},
    )
    batch = json.loads(raw)
    print("batch:", batch["batch_id"], [job["id"] for job in batch["jobs"]])
    started = time.time()
    while True:
        raw, _ = call(base, f"/api/v1/syntheses/batch/{batch['batch_id']}", args.token)
        current = json.loads(raw)
        print("state:", current["status"], current["done"], "/", current["total"], current["progress"])
        if not any(job["status"] in {"queued", "running"} for job in current["jobs"]):
            break
        if time.time() - started > 300:
            print("timeout")
            return 1
        time.sleep(1)
    print("jobs:", [(job["id"], job["status"], job.get("error")) for job in current["jobs"]])
    if not any(job["status"] == "succeeded" for job in current["jobs"]):
        return 1
    raw, content_type = call(base, f"/api/v1/syntheses/batch/{batch['batch_id']}/zip", args.token)
    out = Path("outputs") / f"{batch['batch_id']}.zip"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(raw)
    print("zip:", out, len(raw), content_type)
    first = next(job for job in current["jobs"] if job["status"] == "succeeded")
    raw, content_type = call(base, f"/api/v1/syntheses/{first['id']}/export?format=mp3", args.token)
    mp3 = Path("outputs") / f"{first['id']}.mp3"
    mp3.write_bytes(raw)
    print("mp3:", mp3, len(raw), content_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
