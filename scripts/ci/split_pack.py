import hashlib
import json
import sys
from pathlib import Path

import os

VERSION = os.environ.get("VERSION", "0.0.0")
pack = Path(sys.argv[1])
prefix = sys.argv[2]
limit = 1800 * 1024 * 1024
parts = []
data = pack.read_bytes()
for index, start in enumerate(range(0, len(data), limit), 1):
    name = f"{prefix}.part{index:02d}"
    Path(name).write_bytes(data[start:start + limit])
    parts.append({"url": f"https://github.com/wisdomWindy/voice-smith/releases/download/v{VERSION}/{name}", "file": name, "size": min(limit, len(data) - start)})
manifest = {
    "version": VERSION,
    "sha256": hashlib.sha256(data).hexdigest(),
    "size": len(data),
    "parts": parts,
}
Path(f"{prefix}-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))

