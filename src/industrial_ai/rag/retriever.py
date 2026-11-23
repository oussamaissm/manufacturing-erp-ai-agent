from __future__ import annotations

from ..config import Settings
from .chunking import load_directory
from .embeddings import Embedder, OllamaEmbedder
from .store import Hit, VectorStore


class Retriever:
    def __init__(self, store: VectorStore, k: int = 4, min_score: float = 0.25) -> None:
        self.store, self.k, self.min_score = store, k, min_score

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        return [h for h in self.store.search(query, k or self.k) if h.score >= self.min_score]


def ingest_directory(store: VectorStore, directory, reset: bool = False) -> int:
    if reset:
        store.reset()
    return store.add(load_directory(directory))


def build_default_retriever(s: Settings, embedder: Embedder | None = None) -> Retriever:
    embedder = embedder or OllamaEmbedder(s.embed_model, s.ollama_host)
    store = VectorStore(embedder, s.rag_collection, s.chroma_dir)
    if store.count() == 0:
        ingest_directory(store, s.docs_dir)
    return Retriever(store)
