"""Build the Tauri updater manifest for one release."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path


def main() -> None:
    version = os.environ["VERSION"]
    repo = os.environ["GITHUB_REPOSITORY"]
    base = f"https://github.com/{repo}/releases/download/v{version}"
    platforms = {
        "windows-x86_64": {
            "signature": os.environ["SIG"].strip(),
            "url": f"{base}/VoiceSmith-{version}-windows-x64-setup.exe",
        }
    }
    for suffix, target in (
        ("macos-arm64", "darwin-aarch64"),
        ("macos-intel", "darwin-x86_64"),
    ):
        sig = Path(f"sigs/VoiceSmith-{version}-{suffix}.app.tar.gz.sig")
        if sig.is_file():
            platforms[target] = {
                "signature": sig.read_text(encoding="utf-8").strip(),
                "url": f"{base}/VoiceSmith-{version}-{suffix}.app.tar.gz",
            }
    data = {
        "version": version,
        "notes": Path(f"docs/releases/v{version}.md").read_text(encoding="utf-8"),
        "pub_date": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "platforms": platforms,
    }
    Path("latest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
