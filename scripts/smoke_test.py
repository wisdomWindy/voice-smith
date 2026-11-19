"""End-to-end sidecar smoke test with proper UTF-8 JSON."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def request(base: str, path: str, token: str, method: str = "GET", body: dict | None = None):
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read(), response.headers.get("content-type", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="dev-token")
    parser.add_argument("--voice", default="demo_hui")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    raw, _ = request(base, "/health", args.token)
    print("health:", raw.decode("utf-8"))
    raw, _ = request(base, "/api/v1/assets", args.token)
    assets = json.loads(raw)
    print("assets_ready:", assets["ready"], "missing:", assets["missing"])
    raw, _ = request(base, "/api/v1/doctor/run", args.token, "POST")
    doctor = json.loads(raw)
    print("doctor:", doctor["summary"])

    text = "持久化测试：这是一段真实语音。"
    started = time.time()
    raw, _ = request(
        base,
        "/api/v1/syntheses",
        args.token,
        "POST",
        {"text": text, "voice_id": args.voice, "params": {"speed": 1.0}, "request_id": f"smoke_{int(started)}"},
    )
    job = json.loads(raw)
    print("job:", job)
    while True:
        raw, _ = request(base, f"/api/v1/syntheses/{job['job_id']}", args.token)
        current = json.loads(raw)
        print("state:", current["status"], current["progress"])
        if current["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(1)
    if current["status"] != "succeeded":
        print("error:", current.get("error"))
        return 1
    audio, content_type = request(base, f"/api/v1/syntheses/{job['job_id']}/audio", args.token)
    out = Path("outputs") / f"{job['job_id']}.wav"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(audio)
    print("audio:", out, len(audio), content_type, f"elapsed={time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
