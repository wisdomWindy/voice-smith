"""Synthesize with the newest trained voice."""

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
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("content-type", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="dev-token")
    parser.add_argument("--text", default="这是微调音色测试。")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    raw, _ = call(base, "/api/v1/voices", args.token)
    voices = json.loads(raw)["items"]
    trained = [voice for voice in voices if voice.get("type") == "trained"]
    if not trained:
        print("no trained voice")
        return 1
    voice = trained[-1]
    print("voice:", voice["id"], voice["name"], voice.get("s1_model"), voice.get("s2_model"))
    raw, _ = call(
        base,
        "/api/v1/syntheses",
        args.token,
        "POST",
        {"text": args.text, "voice_id": voice["id"], "params": {"speed": 1.0}, "request_id": f"trained_{int(time.time())}"},
    )
    job = json.loads(raw)
    started = time.time()
    while True:
        raw, _ = call(base, f"/api/v1/syntheses/{job['job_id']}", args.token)
        current = json.loads(raw)
        if current["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(1)
    print("job:", current["status"], f"{time.time() - started:.1f}s", current.get("error"))
    if current["status"] != "succeeded":
        return 1
    audio, content_type = call(base, f"/api/v1/syntheses/{job['job_id']}/audio", args.token)
    out = Path("outputs") / f"trained_{job['job_id']}.wav"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(audio)
    print("audio:", out, len(audio), content_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
