from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml
from PySide6 import QtCore

from vex_native.config import CONFIG_DIR, load_settings


AGENTS_DIR = CONFIG_DIR / "agents"


@dataclass
class AgentRecord:
    id: str
    name: str
    type: str
    enabled: bool
    path: Path
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = "idle"
    last_error: Optional[str] = None


class AgentManager(QtCore.QObject):
    def __init__(self) -> None:
        super().__init__()
        self._agents: Dict[str, AgentRecord] = {}
        self._logs: Dict[str, List[str]] = {}
        self.scan()

    # --- Discovery / config ---
    def scan(self) -> None:
        self._agents.clear()
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        for d in AGENTS_DIR.iterdir():
            if not d.is_dir():
                continue
            cfg = d / "agent.yaml"
            if not cfg.exists():
                continue
            try:
                data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
                aid = d.name
                rec = AgentRecord(
                    id=aid,
                    name=str(data.get("name") or aid),
                    type=str(data.get("type") or "memory_triage"),
                    enabled=bool(data.get("enabled", False)),
                    path=d,
                    config=data,
                )
                self._agents[aid] = rec
            except Exception:
                continue

    def list(self) -> List[Dict[str, Any]]:
        out = []
        for a in self._agents.values():
            out.append({
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "enabled": a.enabled,
                "status": a.status,
                "last_error": a.last_error,
                "config_path": str(a.path / 'agent.yaml'),
            })
        return out

    def get_config_text(self, aid: str) -> str:
        a = self._agents.get(aid)
        if not a:
            return ""
        p = a.path / "agent.yaml"
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return ""

    def save_config_text(self, aid: str, text: str) -> None:
        a = self._agents.get(aid)
        if not a:
            return
        p = a.path / "agent.yaml"
        p.write_text(text, encoding="utf-8")
        # reload
        self.scan()

    # --- Control ---
    def enable(self, aid: str, on: bool) -> None:
        a = self._agents.get(aid)
        if not a:
            return
        try:
            a.enabled = bool(on)
            cfgp = a.path / "agent.yaml"
            data = yaml.safe_load(cfgp.read_text(encoding="utf-8")) or {}
            data["enabled"] = a.enabled
            cfgp.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            a.config = data
        except Exception:
            pass

    def run_once(self, aid: str, payload: Dict[str, Any]) -> None:
        a = self._agents.get(aid)
        if not a:
            return
        QtCore.QThreadPool.globalInstance().start(_AgentTask(a, payload, self._log, self._set_status))

    def emit_event(self, event: str, payload: Dict[str, Any]) -> None:
        # Dispatch to all enabled agents whose triggers include event
        for a in list(self._agents.values()):
            if not a.enabled:
                continue
            triggers = (a.config or {}).get("triggers") or []
            if event in triggers:
                QtCore.QThreadPool.globalInstance().start(_AgentTask(a, {"event": event, **payload}, self._log, self._set_status))

    # --- Logs & status ---
    def _log(self, aid: str, line: str) -> None:
        buf = self._logs.setdefault(aid, [])
        buf.append(line)
        if len(buf) > 500:
            del buf[:-500]

    def get_logs(self, aid: str) -> str:
        return "\n".join(self._logs.get(aid, []))

    def _set_status(self, aid: str, status: str, err: Optional[str] = None) -> None:
        a = self._agents.get(aid)
        if a:
            a.status = status
            a.last_error = err


class _AgentTask(QtCore.QRunnable):
    def __init__(self, agent: AgentRecord, payload: Dict[str, Any], log, set_status):
        super().__init__()
        self.agent = agent
        self.payload = payload
        self.log = log
        self.set_status = set_status

    def run(self):
        import asyncio, math, time
        async def _run():
            try:
                self.set_status(self.agent.id, "running")
                if self.agent.type == "memory_triage":
                    await self._memory_triage(self.agent, self.payload)
                else:
                    self.log(self.agent.id, f"unknown agent type: {self.agent.type}")
                self.set_status(self.agent.id, "idle")
            except Exception as e:
                self.set_status(self.agent.id, "error", str(e))
                self.log(self.agent.id, f"error: {e}")
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop(); loop.run_until_complete(_run())

    async def _memory_triage(self, agent: AgentRecord, payload: Dict[str, Any]):
        cfg = agent.config or {}
        params = cfg.get("params") or {}
        min_chars = int(params.get("min_chars", 80))
        min_novelty = float(params.get("min_novelty", 0.85))
        target_cols = params.get("target_collections") or ["general"]
        col = target_cols[0]
        save_assistant = bool(params.get("save_assistant", False))
        tag_keywords = params.get("tag_keywords") or []

        event = payload.get("event")
        if event != "on_chat_turn_saved":
            return
        msg = (payload.get("message") or {}).get("content") or ""
        role = (payload.get("message") or {}).get("role") or "user"
        if role != "user" and not save_assistant:
            return
        text = str(msg).strip()
        if len(text) < min_chars:
            self.log(agent.id, f"skip (too short): {len(text)} chars")
            return
        # Compute novelty vs existing memory in this collection
        from vex_native.memory.embedder import get_embedder
        from vex_native.memory.store import ChromaStore
        emb = get_embedder()
        qvec = await emb.embed_one(text)
        store = ChromaStore()
        hits = await store.query(collection=col, query_embedding=qvec, n_results=5)
        sims: List[float] = []
        # For a quick proxy, compute cosine by embedding the top hits again (small k)
        for h in hits:
            try:
                vec2 = await emb.embed_one(h.get("text") or "")
                # both normalized embeddings
                sim = sum(a*b for a,b in zip(qvec, vec2))
                sims.append(sim)
            except Exception:
                continue
        max_sim = max(sims) if sims else 0.0
        novelty = 1.0 - max_sim
        if novelty < min_novelty:
            self.log(agent.id, f"skip (novelty {novelty:.2f} < {min_novelty})")
            return
        # Write file to memory root and upsert
        from vex_native.config import load_settings
        settings = load_settings()
        memroot = Path(getattr(settings, 'memory_root_dir', str(CONFIG_DIR / 'memory')))
        memroot.mkdir(parents=True, exist_ok=True)
        import time, re
        col_dir = memroot / col
        col_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        head = " ".join(text.split()[:6])
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", head)[:40] or "mem"
        p = col_dir / f"{ts}_{slug}.md"
        p.write_text(text, encoding='utf-8')
        meta = {"path": str(p)}
        if tag_keywords:
            tags = [kw for kw in tag_keywords if kw.lower() in text.lower()]
            if tags:
                meta["tags"] = tags
        await store.upsert(collection=col, embeddings=[qvec], documents=[text], metadatas=[meta])
        self.log(agent.id, f"saved to {col}: {p.name} (novelty {novelty:.2f})")


agent_manager = AgentManager()

