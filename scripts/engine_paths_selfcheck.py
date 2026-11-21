"""Self-check for the engine-source / asset-store path contract.

Stdlib only, no torch/weights required. Builds a synthetic engine tree and a
synthetic asset store in a temp dir, then verifies that:

1. weight directories are mounted into the engine tree (junction/symlink),
2. the mount is idempotent and transparent to upstream relative paths,
3. an existing in-place weight directory is never deleted ("unmanaged"),
4. ffmpeg resolves from ``assets/bin``,
5. ``sidecar/assets.py`` reports the engine + weights as ready.

Run: ``python scripts/engine_paths_selfcheck.py``
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "sidecar"
sys.path.insert(0, str(SIDECAR))


def make_engine(path: Path) -> None:
    (path / "GPT_SoVITS" / "TTS_infer_pack").mkdir(parents=True)
    (path / "GPT_SoVITS" / "TTS_infer_pack" / "TTS.py").write_text("# engine\n", encoding="utf-8")
    (path / "GPT_SoVITS" / "configs").mkdir(parents=True)
    (path / "tools").mkdir(parents=True)


def make_assets(assets: Path) -> None:
    weights = assets / "gpt-sovits"
    files = {
        "GPT_SoVITS/pretrained_models/s1v3.ckpt": b"gpt",
        "GPT_SoVITS/pretrained_models/gsv-v5-pretrained/s2Gv5turbo.pth": b"sovits",
        "GPT_SoVITS/pretrained_models/gsv-v5-pretrained/vocoder.pth": b"vocoder",
        "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt": b"sv",
        "GPT_SoVITS/pretrained_models/fast_langdetect/lid.176.bin": b"lang",
        "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large/pytorch_model.bin": b"bert",
        "GPT_SoVITS/pretrained_models/chinese-hubert-base/pytorch_model.bin": b"hubert",
        "GPT_SoVITS/text/G2PWModel/g2pW.onnx": b"g2pw",
        "tools/uvr5/uvr5_weights/HP2_all_vocals.pth": b"uvr5",
        "tools/asr/models/speech_fsmn_vad_zh-cn-16k-common-pytorch/model.pt": b"vad",
        "tools/AP_BWE_main/24kto48k/g_24kto48k.zip": b"bwe",
    }
    for rel, payload in files.items():
        target = weights / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (assets / "bin").mkdir(parents=True)
    (assets / "bin" / "ffmpeg.exe").write_bytes(b"ffmpeg")
    (assets / "bin" / "ffprobe.exe").write_bytes(b"ffprobe")


def main() -> int:
    from engine_paths import ASSETS_ENV, DATA_ENV, ENGINE_ENV  # noqa: F401  (import for env names)

    tmp = Path(tempfile.mkdtemp(prefix="voicesmith-paths-"))
    old = {name: os.environ.get(name) for name in (ENGINE_ENV, ASSETS_ENV, DATA_ENV)}
    try:
        engine = tmp / "engine-root"
        asset_store_dir = tmp / "assets"
        data = tmp / "data"
        make_engine(engine)
        make_assets(asset_store_dir)
        os.environ[ENGINE_ENV] = str(engine)
        os.environ[ASSETS_ENV] = str(asset_store_dir)
        os.environ[DATA_ENV] = str(data)

        import engine_paths

        assert engine_paths.engine_root() == engine, engine_paths.engine_root()
        assert engine_paths.weights_root() == asset_store_dir / "gpt-sovits"

        report = engine_paths.ensure_mounts(engine)
        assert report["error"] == "", report
        statuses = {item["path"]: item["status"] for item in report["mounts"]}
        for rel in engine_paths.WEIGHT_MOUNTS:
            assert statuses[rel] == "mounted", (rel, statuses[rel])
        assert statuses[engine_paths.BIN_MOUNT] == "mounted", statuses

        # upstream relative lookups now hit the asset bytes
        assert (engine / "GPT_SoVITS" / "pretrained_models" / "s1v3.ckpt").read_bytes() == b"gpt"
        assert (engine / "GPT_SoVITS" / "text" / "G2PWModel" / "g2pW.onnx").exists()
        assert (engine / "runtime" / "ffmpeg.exe").exists()
        assert str(engine_paths.ffmpeg_path()).endswith("ffmpeg.exe")

        # idempotent
        again = engine_paths.ensure_mounts(engine)
        assert all(item["status"] == "mounted" for item in again["mounts"]), again["mounts"]

        # an in-place weight directory (legacy install) is never deleted
        legacy_engine = tmp / "legacy-engine"
        make_engine(legacy_engine)
        legacy_weights = legacy_engine / "GPT_SoVITS" / "pretrained_models"
        legacy_weights.mkdir(parents=True)
        (legacy_weights / "keep.pth").write_bytes(b"keep")
        legacy_report = engine_paths.ensure_mounts(legacy_engine)
        legacy_status = {i["path"]: i["status"] for i in legacy_report["mounts"]}
        assert legacy_status["GPT_SoVITS/pretrained_models"] == "unmanaged", legacy_status
        assert (legacy_weights / "keep.pth").read_bytes() == b"keep"

        # sidecar asset report sees engine + weights as ready
        import assets

        assets.refresh(engine)
        state = assets.list_assets()
        assert state["ready"] is True, state["missing"]
        assert state["engine_root"] == str(engine)
        assert state["weights_root"] == str(asset_store_dir / "gpt-sovits")
        assert state["mounts"], "mount report should be exposed to the UI"

        print("engine path self-check: OK")
        print(f"  engine      {engine}")
        print(f"  assets      {asset_store_dir}")
        print(f"  mounts      {len(state['mounts'])}")
        print(f"  assets ready {state['ready']}")
        return 0
    finally:
        for name, value in old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
