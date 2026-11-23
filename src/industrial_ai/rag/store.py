from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import chromadb

from .chunking import Chunk
from .embeddings import Embedder


@dataclass
class Hit:
    source: str
    heading: str
    text: str
    score: float  # cosine similarity, 1.0 = identical

    def as_dict(self) -> dict:
        return {"source": self.source, "section": self.heading, "text": self.text, "score": round(self.score, 3)}


class VectorStore:
    def __init__(self, embedder: Embedder, collection: str = "industrial_docs", path: Path | None = None) -> None:
        self.embedder = embedder
        self._client = chromadb.PersistentClient(path=str(path)) if path else chromadb.EphemeralClient()
        self._col = self._client.get_or_create_collection(collection, metadata={"hnsw:space": "cosine"})

    def count(self) -> int:
        return self._col.count()

    def reset(self) -> None:
        name = self._col.name
        self._client.delete_collection(name)
        self._col = self._client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})

    def add(self, chunks: list[Chunk], batch: int = 32) -> int:
        for i in range(0, len(chunks), batch):
            part = chunks[i : i + batch]
            self._col.upsert(
                ids=[c.id for c in part],
                documents=[c.text for c in part],
                embeddings=self.embedder.embed([c.text for c in part]),
                metadatas=[{"source": c.source, "heading": c.heading} for c in part],
            )
        return len(chunks)

    def search(self, query: str, k: int = 4) -> list[Hit]:
        if self.count() == 0:
            return []
        res = self._col.query(
            query_embeddings=self.embedder.embed([query]),
            n_results=min(k, self.count()),
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hits.append(Hit(meta["source"], meta["heading"], doc, 1.0 - float(dist)))
        return hits


def unique_collection(prefix: str = "t") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
