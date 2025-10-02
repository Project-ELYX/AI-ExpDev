from __future__ import annotations

import asyncio
from typing import List

_MODEL = None


def _load_model(name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    global _MODEL
    if _MODEL is None:
        # Lazy import to avoid hard dependency if not used yet
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:
            raise RuntimeError("Memory embedding backend unavailable: sentence-transformers not installed") from e
        # Prefer CUDA when available
        try:
            import torch  # type: ignore
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
        _MODEL = SentenceTransformer(name, device=device)
    return _MODEL


class Embedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = _load_model(model_name)

    async def embed_one(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        vec = await loop.run_in_executor(None, lambda: self.model.encode(text, normalize_embeddings=True).tolist())
        return vec

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_event_loop()
        vecs = await loop.run_in_executor(None, lambda: self.model.encode(texts, normalize_embeddings=True).tolist())
        return vecs


def get_embedder(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Embedder:
    return Embedder(model_name)
