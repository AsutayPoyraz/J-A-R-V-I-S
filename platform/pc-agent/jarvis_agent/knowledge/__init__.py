"""Kişisel bilgi tabanı (Second Brain / RAG) — Özellik 8.

Alt modüller:
- ingestion: dosyayı metne çevirir + chunk'lara böler (500 token / 50 overlap)
- store: SQLite kalıcılık (knowledge_documents / knowledge_chunks)
- retriever: sorguyu embed eder, cosine similarity ile en yakın 5 chunk

Varsayım: chromadb/sqlite-vec yerine saf SQLite + Python cosine tercih edildi
(ek bağımlılık/kurulum riski yok; kişisel veri hacmi için yeterli).
Embedding: OpenAI text-embedding-3-small (anahtar varsa) → yoksa yerel
deterministik hash embedding (256 boyut, offline çalışır).
"""
from .ingestion import chunk_text, extract_text
from .retriever import retrieve
from .store import (
    delete_document,
    get_document,
    ingest_document,
    list_documents,
    search_chunks,
)

__all__ = [
    "chunk_text",
    "delete_document",
    "extract_text",
    "get_document",
    "ingest_document",
    "list_documents",
    "retrieve",
    "search_chunks",
]
