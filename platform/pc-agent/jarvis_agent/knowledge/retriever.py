"""Sorgu → en ilgili chunk'lar (Özellik 8.3) — sohbet entegrasyonu için."""
from __future__ import annotations

from typing import Any

from .store import search_chunks

# Sohbete bağlam eklemek için asgari alaka eşiği (hash embedding düşük skor
# üretebildiği için muhafazakâr bir eşik kullanılır).
MIN_SCORE = 0.10
TOP_K = 5


def retrieve(owner_id: str, query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
    """Sohbet bağlamına uygun chunk'lar: eşiği geçen en iyi top_k."""
    results = search_chunks(owner_id, query, top_k=top_k)
    return [r for r in results if r.get("score", 0.0) >= MIN_SCORE]


def context_block(owner_id: str, query: str) -> str:
    """Soru için RAG bağlam metni üretir; ilgili belge yoksa boş döner."""
    hits = retrieve(owner_id, query)
    if not hits:
        return ""
    lines = []
    for hit in hits[:TOP_K]:
        name = hit.get("document_name") or "belge"
        lines.append(f"- [{name}] {hit['content'][:500]}")
    joined = "\n".join(lines)
    return (
        "\n\n[Kullanıcının kişisel bilgi tabanından ilgili bölümler — "
        "yanıtı bunlara dayandır, kaynağını belirt]\n" + joined
    )
