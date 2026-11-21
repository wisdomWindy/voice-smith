"""Generate a lightweight local SBOM and third-party notice list."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "release"
OUT.mkdir(parents=True, exist_ok=True)


def python_components() -> list[dict]:
    items = []
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or ""
        if not name:
            continue
        items.append(
            {
                "type": "library",
                "ecosystem": "pypi",
                "name": name,
                "version": dist.version,
                "license": dist.metadata.get("License-Expression") or dist.metadata.get("License") or "UNKNOWN",
            }
        )
    return sorted(items, key=lambda item: item["name"].lower())


def node_components() -> list[dict]:
    try:
        raw = subprocess.check_output(["pnpm", "list", "--json", "--depth", "0"], cwd=ROOT, text=True)
        data = json.loads(raw)
        deps = data[0].get("dependencies", {}) if isinstance(data, list) and data else {}
        return [
            {"type": "library", "ecosystem": "npm", "name": name, "version": value.get("version", "")}
            for name, value in sorted(deps.items())
        ]
    except Exception:
        return []


def rust_components() -> list[dict]:
    lock = ROOT / "src-tauri" / "Cargo.lock"
    if not lock.exists():
        return []
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    return [
        {
            "type": "library",
            "ecosystem": "cargo",
            "name": package["name"],
            "version": package["version"],
        }
        for package in data.get("package", [])
        if package.get("name") != "voice-smith"
    ]


def main() -> int:
    components = python_components() + node_components() + rust_components()
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "VoiceSmith",
                "version": "0.1.0",
            }
        },
        "components": components,
    }
    (OUT / "SBOM.json").write_text(json.dumps(sbom, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Third-party notices",
        "",
        "VoiceSmith bundles the GPT-SoVITS engine source (MIT) and the Python runtime "
        "dependencies. Model weights are not bundled and remain subject to their own licenses.",
        "",
        "## Application",
        "- Tauri 2 (MIT/Apache-2.0)",
        "- Vue 3 (MIT)",
        "- FastAPI / Uvicorn (MIT/BSD)",
        "- GPT-SoVITS engine source, vendored under vendor/GPT-SoVITS (MIT)",
        "- PyTorch (BSD-3-Clause)",
        "",
        "## Full inventory",
        "See `SBOM.json` for the generated package inventory "
        f"({len(components)} components).",
    ]
    (OUT / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("components:", len(components))
    print("python:", len(python_components()), "node:", len(node_components()), "rust:", len(rust_components()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
