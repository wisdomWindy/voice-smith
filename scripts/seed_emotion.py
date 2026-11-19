import json
import sys
import urllib.request
from pathlib import Path

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
base = f"http://127.0.0.1:{port}"
ref = str(Path.home() / ".voicesmith" / "sample" / "ref_hui.wav")
body = {
    "name": "平静 Calm",
    "ref_audio_path": ref,
    "ref_text": "先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。",
}
request = urllib.request.Request(
    base + "/api/v1/voices/demo_hui/emotions",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={"Authorization": "Bearer dev-token", "Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    print(response.read().decode("utf-8"))
