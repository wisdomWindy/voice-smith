"""Install offline wheel packs into the embedded runtime."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _distutils_shim(root: Path) -> None:
    """Python 3.12 dropped distutils; FunASR still imports it."""
    site = root / "Lib" / "site-packages"
    src = site / "setuptools" / "_distutils"
    dst = site / "distutils"
    if src.is_dir() and not dst.exists():
        import shutil

        shutil.copytree(src, dst)


def main() -> int:
    root = Path(sys.executable).resolve().parent
    folders = [root / "deps" / "core", root / "deps" / "torch"]
    installed = 0
    for folder in folders:
        if not folder.is_dir():
            continue
        wheels = [str(p) for p in folder.rglob("*.whl")]
        if not wheels:
            continue
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-cache-dir",
            "--no-warn-script-location",
            *wheels,
        ]
        print(f"installing {len(wheels)} wheels from {folder.name}", flush=True)
        code = subprocess.call(command)
        if code != 0:
            # Offline pack may miss a source-only dependency (e.g. jieba).
            # Retry with the public index so bootstrap can still complete.
            print("offline install failed; retrying with PyPI", flush=True)
            command = [c for c in command if c != "--no-index"]
            command += ["--index-url", "https://pypi.org/simple"]
            code = subprocess.call(command)
            if code != 0:
                return code
        installed += len(wheels)
    if installed == 0:
        print("no wheel packs found", file=sys.stderr)
        return 2
    _distutils_shim(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
