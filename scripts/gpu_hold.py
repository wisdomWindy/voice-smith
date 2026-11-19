import sys
import time

import torch

count = int(sys.argv[1]) if len(sys.argv) > 1 else 3_000_000_000
seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 300
x = torch.empty(count, dtype=torch.float32, device="cuda")
torch.cuda.synchronize()
print("ALLOC", torch.cuda.memory_allocated() // (1024 ** 2), "MiB", flush=True)
time.sleep(seconds)
