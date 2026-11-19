import argparse
import json
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8765)
parser.add_argument("--token", default="dev-token")
parser.add_argument("--list", required=True)
args = parser.parse_args()
request = urllib.request.Request(
    f"http://127.0.0.1:{args.port}/api/v1/datasets/qc",
    data=json.dumps({"dataset_list": args.list}, ensure_ascii=False).encode("utf-8"),
    headers={"Authorization": f"Bearer {args.token}", "Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=120) as response:
    report = json.loads(response.read())
print("count:", report["count"], "total:", report["total_duration"], "ok:", report["ok"])
print("errors:", report["errors"][:3])
print("blocking:", report["blocking"][:3])
print("first:", {key: report["items"][0].get(key) for key in ("duration", "samplerate", "channels", "silence_ratio", "clipping_ratio")})
