"""Single-process launcher for GPT-SoVITS v5 s2_train_v3.

The upstream v5 trainer assumes a distributed process group even for one GPU;
initialize a local gloo group before running the script.
"""

from __future__ import annotations

import os
import runpy
import sys

import torch.distributed as dist


def main() -> int:
    script = sys.argv[1]
    extra = sys.argv[2:]
    if not dist.is_initialized():
        os.environ["MASTER_ADDR"] = "127.0.0.1"
        os.environ["MASTER_PORT"] = "29591"
        dist.init_process_group(backend="gloo", rank=0, world_size=1)
    sys.argv = [script, *extra]
    runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
