from __future__ import annotations

import asyncio
import os
import uuid
from typing import Dict, List

from ..config import CONFIG_DIR


class ChromaStore:
    def __init__(self, persist_subdir: str = ".chroma"):
        try:
            import chromadb  # type: ignore
            from chromadb.config import Settings  # type: ignore
        except Exception as e:
            raise RuntimeError("Memory vector store unavailable: chromadb not installed") from e

        persist_path = CONFIG_DIR / persist_subdir
        os.makedirs(persist_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_path), settings=Settings(anonymized_telemetry=False))

    def _get_collection(self, name: str):
        try:
            return self.client.get_collection(name)
        except Exception:
            return self.client.create_collection(name)

    async def upsert(self, collection: str, embeddings: List[List[float]], documents: List[str], metadatas: List[Dict]):
        col = self._get_collection(collection)
        ids = [str(uuid.uuid4()) for _ in documents]
        # ensure timestamps in metadata for clarity when auditing
        import time
        safe_metas: List[Dict] = []
        ts = time.time()
        for m in metadatas:
            mm = dict(m or {})
            if "ts" not in mm:
                mm["ts"] = ts
            safe_metas.append(mm)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: col.add(embeddings=embeddings, documents=documents, metadatas=safe_metas, ids=ids))

    async def query(self, collection: str, query_embedding: List[float], n_results: int = 3):
        col = self._get_collection(collection)
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: col.query(query_embeddings=[query_embedding], n_results=n_results))
        out = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        for d, m in zip(docs, metas):
            out.append({"text": d, "meta": m or {}})
        return out

    def list_collections(self):
        cols = []
        for c in self.client.list_collections():
            try:
                count = c.count()
            except Exception:
                count = None
            cols.append({"name": c.name, "count": count})
        return cols
