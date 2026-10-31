"""Bilgi tabanı SQLite deposu + embedding üretimi (Özellik 8.2).

Embedding stratejisi:
1. JARVIS_EMBEDDING_PROVIDER=openai ve OPENAI anahtarı varsa
   text-embedding-3-small.
2. Aksi halde yerel deterministik hash embedding (256 boyut, normalize)
   — offline/kurulum'suz çalışır; alaka duyarlılığı anahtarlıya göre düşer.
"""
from __future__ import annotations

import datetime
import hashlib
import math
import struct
from typing import Any, Optional

from .. import config
from ..store import database

EMBED_DIM = 256


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ── Embedding ────────────────────────────────────────────────────────────────

def _local_embed(text: str) -> list[float]:
    """Deterministik hash tabanlı vektör (offline fallback).

    Token'lardan n-gram öznitelikleri hash ile EMBED_DIM kovasına dağıtır,
    sonra L2 normalize eder. Aynı metin → aynı vektör.
    """
    vec = [0.0] * EMBED_DIM
    tokens = (text or "").lower().split()
    if not tokens:
        return vec
    grams = list(tokens)
    for i in range(len(tokens) - 1):
        grams.append(tokens[i] + "_" + tokens[i + 1])
    for gram in grams:
        digest = hashlib.md5(gram.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % EMBED_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _openai_embed(texts: list[str]) -> Optional[list[list[float]]]:
    """OpenAI embeddings API; anahtar/hata yoksa None."""
    api_key = config.OPENAI_API_KEY
    if not api_key or config.env("JARVIS_EMBEDDING_PROVIDER") != "openai":
        return None
    try:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "text-embedding-3-small", "input": texts[:64]},
            timeout=30.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return [item["embedding"] for item in data.get("data", [])]
    except Exception:  # noqa: BLE001 — ağ hatasında yerel embedding'e düş
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """OpenAI varsa onu, yoksa yerel hash embedding kullanır."""
    if not texts:
        return []
    remote = _openai_embed(texts)
    if remote and len(remote) == len(texts):
        return remote
    return [_local_embed(t) for t in texts]


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: Optional[bytes]) -> list[float]:
    if not blob:
        return []
    count = len(blob) // 4
    if count == 0:
        return []
    return list(struct.unpack(f"<{count}f", blob[: count * 4]))


# ── Belge CRUD ───────────────────────────────────────────────────────────────

def list_documents(owner_id: str) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, name, mime, chunks_count, status, error, created_at "
            "FROM knowledge_documents WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_document(owner_id: str, document_id: int) -> Optional[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT id, name, mime, chunks_count, status, error, created_at "
            "FROM knowledge_documents WHERE owner_id = ? AND id = ?",
            (owner_id, document_id),
        ).fetchone()
    return dict(row) if row else None


def delete_document(owner_id: str, document_id: int) -> bool:
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id IN "
            "(SELECT id FROM knowledge_documents WHERE owner_id = ? AND id = ?)",
            (owner_id, document_id),
        )
        cur = conn.execute(
            "DELETE FROM knowledge_documents WHERE owner_id = ? AND id = ?",
            (owner_id, document_id),
        )
    return cur.rowcount > 0


def _guess_mime(name: str) -> str:
    lowered = (name or "").lower()
    if lowered.endswith(".pdf"):
        return "application/pdf"
    if lowered.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lowered.endswith(".md"):
        return "text/markdown"
    return "text/plain"


def ingest_document(owner_id: str, filename: str, data: bytes) -> dict[str, Any]:
    """Dosyayı metne çevirir, chunk'lar, embed eder ve kaydeder.

    Hata durumunda status='error' bir kayıt bırakılır (frontend gösterebilsin).
    """
    from .ingestion import ExtractionError, chunk_text, extract_text

    if database.is_guest(owner_id):
        return {"ok": False, "detail": "misafir oturumda bilgi tabanı kapalı"}
    name = (filename or "belge").strip()[:120]
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO knowledge_documents (owner_id, name, mime, chunks_count, "
            "status, created_at) VALUES (?, ?, ?, 0, 'processing', ?)",
            (owner_id, name, _guess_mime(name), _now()),
        )
        doc_id = cur.lastrowid
    try:
        text = extract_text(name, data)
        chunks = chunk_text(text)
        if not chunks:
            raise ExtractionError("Belgede işlenebilir metin bulunamadı.")
        vectors = embed_texts(chunks)
        stamp = _now()
        with database._write_lock, database.closing(database.connect()) as conn, conn:
            for index, (chunk, vec) in enumerate(zip(chunks, vectors)):
                conn.execute(
                    "INSERT INTO knowledge_chunks (document_id, owner_id, "
                    "chunk_index, content, embedding, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (doc_id, owner_id, index, chunk[:4000], _pack(vec), stamp),
                )
            conn.execute(
                "UPDATE knowledge_documents SET chunks_count = ?, status = 'ready', "
                "error = '' WHERE id = ?",
                (len(chunks), doc_id),
            )
    except Exception as exc:  # noqa: BLE001 — hata kayıtta saklanır
        with database._write_lock, database.closing(database.connect()) as conn, conn:
            conn.execute(
                "UPDATE knowledge_documents SET status = 'error', error = ? "
                "WHERE id = ?",
                (str(exc)[:400], doc_id),
            )
        return {"ok": False, "document_id": doc_id, "detail": str(exc)[:300]}
    return {
        "ok": True,
        "document_id": doc_id,
        "chunks": len(chunks),
        "document": get_document(owner_id, doc_id),
    }


def search_chunks(
    owner_id: str, query: str, top_k: int = 5
) -> list[dict[str, Any]]:
    """Sorguya en yakın top_k chunk (cosine similarity, saf Python)."""
    query = (query or "").strip()
    if not query:
        return []
    qvec = embed_texts([query])[0]
    if not any(qvec):
        return []
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, "
            "d.name AS document_name FROM knowledge_chunks c "
            "JOIN knowledge_documents d ON d.id = c.document_id "
            "WHERE c.owner_id = ? AND c.embedding IS NOT NULL LIMIT 2000",
            (owner_id,),
        ).fetchall()
    scored = []
    qnorm = math.sqrt(sum(v * v for v in qvec)) or 1.0
    for row in rows:
        vec = _unpack(row["embedding"])
        if not vec:
            continue
        dot = sum(a * b for a, b in zip(qvec, vec))
        vnorm = math.sqrt(sum(v * v for v in vec)) or 1.0
        score = dot / (qnorm * vnorm)
        scored.append(
            {
                "chunk_id": row["id"],
                "document_id": row["document_id"],
                "document_name": row["document_name"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "score": round(score, 4),
            }
        )
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[: max(1, min(20, top_k))]

