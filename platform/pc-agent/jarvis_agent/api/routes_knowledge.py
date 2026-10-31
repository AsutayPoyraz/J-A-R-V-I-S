"""Bilgi tabanı uçları (Özellik 8) — yükleme, listeleme, silme, arama.

Kullanıcı bazlı izolasyon; misafirde kapalı (upload 403 / liste boş).
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from .. import security
from ..knowledge import store as kstore

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/api/knowledge/upload")
async def upload_document(request: Request, file: UploadFile = File(...)) -> dict:
    owner = security.request_owner(request)
    if security.is_guest(request):
        raise HTTPException(status_code=403, detail="Misafir bilgi tabanı kullanamaz.")
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks 10 MB).")
    if not data:
        raise HTTPException(status_code=422, detail="Boş dosya.")
    # Ağ/embedding işi olay döngüsünü bloklamasın:
    result = await asyncio.to_thread(
        kstore.ingest_document, owner, file.filename or "belge", data
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("detail") or "İşlenemedi.")
    return result


@router.get("/api/knowledge/documents")
def list_documents(request: Request) -> dict:
    owner = security.request_owner(request)
    if security.is_guest(request):
        return {"documents": [], "detail": "misafir"}
    return {"documents": kstore.list_documents(owner)}


@router.delete("/api/knowledge/{document_id}")
def remove_document(document_id: int, request: Request) -> dict:
    owner = security.request_owner(request)
    if not kstore.delete_document(owner, document_id):
        raise HTTPException(status_code=404, detail="Belge bulunamadı.")
    return {"ok": True}


@router.get("/api/knowledge/search")
def search(request: Request, q: str = "", top_k: int = 5) -> dict:
    owner = security.request_owner(request)
    if security.is_guest(request):
        return {"results": [], "detail": "misafir"}
    return {"results": kstore.search_chunks(owner, q, top_k=top_k)}
