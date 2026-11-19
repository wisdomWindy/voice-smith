"""Smoke-test the training API end to end."""

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
    parser.add_argument("--exp", default="api_smoke")
    parser.add_argument("--s1", type=int, default=1)
    parser.add_argument("--s2", type=int, default=1)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    job = call(
        base,
        "/api/v1/trainings",
        args.token,
        "POST",
        {
            "dataset_list": args.dataset,
            "exp_name": args.exp,
            "s1_epochs": args.s1,
            "s2_epochs": args.s2,
            "batch_size": args.batch,
            "force": args.force,
        },
    )
    print("training:", job["id"], job["status"])
    started = time.time()
    last = ""
    while True:
        current = call(base, f"/api/v1/trainings/{job['id']}", args.token)
        marker = f"{current['stage']} {current['progress']} {current['detail']}"
        if marker != last:
            print(f"[{time.time() - started:6.1f}s] {marker}")
            last = marker
        if current["status"] in {"succeeded", "failed", "cancelled"}:
            print(json.dumps(current, ensure_ascii=False, indent=2))
            log = call(base, f"/api/v1/trainings/{job['id']}/log?limit=4000", args.token)["log"]
            print("---- log tail ----")
            print(log)
            return 0 if current["status"] == "succeeded" else 1
        if time.time() - started > 900:
            print("timeout")
            return 1
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
