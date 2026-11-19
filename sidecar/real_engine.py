"""Persistent GPT-SoVITS worker supervisor used by the sidecar."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

CREATE_NO_WINDOW = 0x0800_0000 if os.name == "nt" else 0


class RealEngine:
    def __init__(self, engine_root: Path, log_path: Path):
        self.engine_root = engine_root
        self.log_path = log_path
        self.proc: Optional[subprocess.Popen[str]] = None
        self.log_file = None
        self.lock = threading.Lock()

    def _start(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_path, "a", encoding="utf-8")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--worker", "--engine", str(self.engine_root)]
        else:
            command = [
                sys.executable,
                str(Path(__file__).resolve().parent / "gpt_worker.py"),
                "--engine",
                str(self.engine_root),
            ]
        self.proc = subprocess.Popen(
            command,
            cwd=str(self.engine_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log_file,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            code = self.proc.poll()
            self.log_file.flush()
            tail = ""
            try:
                tail = self.log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
            except Exception:
                pass
            raise RuntimeError(f"GPT-SoVITS worker exited before ready (code={code}): {tail}")
        message = json.loads(line)
        if message.get("event") != "ready":
            raise RuntimeError(f"unexpected worker handshake: {message}")

    def _ensure(self) -> None:
        if self.proc is None or self.proc.poll() is not None:
            self._start()

    def synthesize(self, request: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self._ensure()
            assert self.proc and self.proc.stdin and self.proc.stdout
            self.proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("GPT-SoVITS worker stopped; see logs/engine.log")
            response = json.loads(line)
            if not response.get("ok"):
                raise RuntimeError(response.get("error") or "GPT-SoVITS failed")
            return response

    def stop(self) -> None:
        with self.lock:
            if not self.proc:
                return
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                self.proc = None
                if self.log_file is not None:
                    try:
                        self.log_file.close()
                    except Exception:
                        pass
                    self.log_file = None
