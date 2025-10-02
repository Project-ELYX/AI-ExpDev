from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Dict, List, Optional, Callable

import httpx


async def stream_chat(server_url: str, messages: List[Dict], gen: Optional[Dict] = None, stop_flag: Optional[Callable[[], bool]] = None) -> AsyncIterator[str]:
    """Stream tokens from an OpenAI-compatible /v1/chat/completions endpoint."""
    body = {
        "model": "local",
        "messages": messages,
        "stream": True,
    }
    if gen:
        body.update({k: v for k, v in gen.items() if v is not None})
    url = server_url.rstrip("/") + "/v1/chat/completions"
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=body) as r:
            ait = r.aiter_lines()
            while True:
                if stop_flag and stop_flag():
                    break
                try:
                    # allow responsiveness to stop_flag
                    line = await asyncio.wait_for(ait.__anext__(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                except StopAsyncIteration:
                    break
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    choices = obj.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content


async def once_chat(server_url: str, messages: List[Dict], gen: Optional[Dict] = None) -> str:
    body = {
        "model": "local",
        "messages": messages,
        "stream": False,
    }
    if gen:
        body.update({k: v for k, v in gen.items() if v is not None})
    url = server_url.rstrip("/") + "/v1/chat/completions"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        obj = r.json()
        return obj.get("choices", [{}])[0].get("message", {}).get("content", "")
