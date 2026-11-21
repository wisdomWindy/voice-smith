"""Install offline wheel packs into the embedded runtime."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.executable).resolve().parent
    wheels: list[str] = []
    for folder in (root / "deps" / "core", root / "deps" / "torch"):
        if folder.is_dir():
            wheels.extend(str(p) for p in folder.rglob("*.whl"))
    if not wheels:
        print("no wheel packs found", file=sys.stderr)
        return 2
    command = [sys.executable, "-m", "pip", "install", "--no-index", "--no-cache-dir", *wheels]
    print("installing", len(wheels), "wheels", flush=True)
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
