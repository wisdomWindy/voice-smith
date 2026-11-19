"""Emotion reference smoke test."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

REF = str(Path.home() / ".voicesmith" / "sample" / "ref_hui.wav")
TEXT = "先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。"


def call(base: str, path: str, token: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="dev-token")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    emotion = call(
        base,
        "/api/v1/voices/demo_hui/emotions",
        args.token,
        "POST",
        {"name": "平静", "ref_audio_path": REF, "ref_text": TEXT},
    )
    print("emotion:", emotion["id"], emotion["name"])
    items = call(base, "/api/v1/voices/demo_hui/emotions", args.token)["items"]
    print("count:", len(items))
    job = call(
        base,
        "/api/v1/syntheses",
        args.token,
        "POST",
        {"text": "这是情绪参考测试。", "voice_id": "demo_hui", "params": {"emotion_id": emotion["id"]}},
    )
    started = time.time()
    while True:
        current = call(base, f"/api/v1/syntheses/{job['job_id']}", args.token)
        if current["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(1)
    print("job:", current["status"], f"{time.time() - started:.1f}s", current.get("error"))
    call(base, f"/api/v1/emotions/{emotion['id']}", args.token, "DELETE")
    print("deleted")
    return 0 if current["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
