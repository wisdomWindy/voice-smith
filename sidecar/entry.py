"""Frozen/source entrypoint for the VoiceSmith engine.

Modes:
  (default)           run the FastAPI sidecar
  --worker ...        run the persistent GPT-SoVITS worker
  --run-script S ...  run an upstream GPT-SoVITS script with a Python interpreter
"""

from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path


def _patch_versions() -> None:
    try:
        import pathlib
        import torch

        torch.serialization.add_safe_globals([pathlib.WindowsPath, pathlib.PosixPath])
    except Exception:
        pass

    try:
        import pytorch_lightning as pl

        if not hasattr(pl, "__version__"):
            pl.__version__ = "2.6.6"
    except Exception:
        pass

    try:
        import lightning_fabric as fabric

        if not hasattr(fabric, "__version__"):
            fabric.__version__ = "2.6.6"
    except Exception:
        pass


def _install_gradio_stub() -> None:
    """Training scripts only use gr.Warning/Info; avoid importing the full UI."""
    if "gradio" in sys.modules:
        return

    class _Progress:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return self

    stub = types.SimpleNamespace(
        Warning=lambda *args, **kwargs: None,
        Info=lambda *args, **kwargs: None,
        Progress=_Progress,
    )
    sys.modules["gradio"] = stub  # type: ignore[assignment]


def _bootstrap_paths(engine: str | None) -> None:
    if not engine:
        return
    root = Path(engine).resolve()
    for path in (root / "GPT_SoVITS", root):
        text = str(path)
        if path.is_dir() and text not in sys.path:
            sys.path.insert(0, text)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    engine = None
    for index, value in enumerate(argv):
        if value == "--engine" and index + 1 < len(argv):
            engine = argv[index + 1]
            break

    if argv[:1] == ["--worker"]:
        _bootstrap_paths(engine)
        sys.argv = [sys.argv[0], *argv[1:]]
        import gpt_worker

        raise SystemExit(gpt_worker.main())

    if argv[:1] == ["--run-script"]:
        if len(argv) < 2:
            raise SystemExit("--run-script requires a script path")
        script = Path(argv[1]).resolve()
        _bootstrap_paths(engine)
        tail = argv[2:]
        cleaned: list[str] = []
        index = 0
        while index < len(tail):
            if tail[index] == "--engine" and index + 1 < len(tail):
                index += 2
                continue
            cleaned.append(tail[index])
            index += 1
        sys.argv = [str(script), *cleaned]
        _install_gradio_stub()
        _patch_versions()
        if script.name.startswith("s2_train_v3"):
            import os

            import torch.distributed as dist

            if not dist.is_initialized():
                os.environ["MASTER_ADDR"] = "127.0.0.1"
                os.environ["MASTER_PORT"] = "29591"
                dist.init_process_group(backend="gloo", rank=0, world_size=1)
        runpy.run_path(str(script), run_name="__main__")
        return

    _bootstrap_paths(engine)
    import app

    app.main()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("--multiprocessing-fork"):
        from multiprocessing.spawn import spawn_main

        _install_gradio_stub()
        _patch_versions()
        values = {}
        for item in sys.argv[2:]:
            if "=" in item:
                key, value = item.split("=", 1)
                values[key] = value
        spawn_main(pipe_handle=int(values["pipe_handle"]), parent_pid=int(values["parent_pid"]))
    else:
        main()
