from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, AsyncIterator

import httpx


@dataclass
class RunnerConfig:
    server_binary: str
    server_host: str
    server_port: int
    model_path: str
    n_ctx: int = 4096
    n_gpu_layers: int = -1
    threads: int = 8
    batch_size: int = 512
    rope_freq_base: float | None = None
    rope_freq_scale: float | None = None


class LlamaServerSupervisor:
    def __init__(self, cfg: RunnerConfig, cwd: Optional[Path] = None) -> None:
        self.cfg = cfg
        self.cwd = str(cwd) if cwd else None
        self.proc: Optional[subprocess.Popen] = None

    def build_cmd(self) -> list[str]:
        c = self.cfg
        cmd = [
            c.server_binary,
            "-m", c.model_path,
            "--host", c.server_host,
            "--port", str(c.server_port),
            "-ngl", str(c.n_gpu_layers),
            "-c", str(c.n_ctx),
            "-t", str(c.threads),
            "-b", str(c.batch_size),
        ]
        if c.rope_freq_base is not None:
            cmd += ["--rope-freq-base", str(c.rope_freq_base)]
        if c.rope_freq_scale is not None:
            cmd += ["--rope-freq-scale", str(c.rope_freq_scale)]
        return cmd

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return
        cmd = self.build_cmd()
        self.proc = subprocess.Popen(
            cmd,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def stop(self, timeout: float = 5.0) -> None:
        if not self.proc:
            return
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=timeout)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None

    async def probe(self) -> bool:
        url = f"http://{self.cfg.server_host}:{self.cfg.server_port}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(url)
                return r.status_code == 200
        except Exception:
            return False

    async def iter_logs(self) -> AsyncIterator[str]:
        if not self.proc or not self.proc.stdout:
            return
        loop = asyncio.get_event_loop()
        while self.proc and self.proc.poll() is None:
            line = await loop.run_in_executor(None, self.proc.stdout.readline)
            if not line:
                break
            yield line.rstrip()
