"""Submit a training job, cancel it mid-run, verify status."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


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
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    job = call(
        base,
        "/api/v1/trainings",
        args.token,
        "POST",
        {
            "dataset_list": args.dataset,
            "exp_name": "cancel_smoke",
            "s1_epochs": 5,
            "s2_epochs": 2,
            "batch_size": 2,
            "force": True,
        },
    )
    print("training:", job["id"])
    started = time.time()
    cancelled = False
    while True:
        current = call(base, f"/api/v1/trainings/{job['id']}", args.token)
        print(f"[{time.time() - started:6.1f}s]", current["stage"], current["progress"], current["status"])
        if not cancelled and current["stage"] in {"s1", "s2"}:
            call(base, f"/api/v1/trainings/{job['id']}/cancel", args.token, "POST")
            print("cancel requested")
            cancelled = True
        if current["status"] in {"succeeded", "failed", "cancelled"}:
            print("final:", current["status"], current["detail"])
            return 0 if current["status"] == "cancelled" else 1
        if time.time() - started > 240:
            print("timeout")
            return 1
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
