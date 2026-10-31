"""Günlük özet uçları (Özellik 11) — anında üretim + geçmiş."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..core import daily_summary
from ..store import v11

router = APIRouter()


class GenerateBody(BaseModel):
    channels: str = Field(default="chat", max_length=120)


@router.post("/api/summary/generate")
async def generate_summary(request: Request, payload: GenerateBody = None) -> dict:
    """Test/anında özet üretimi (varsayılan kanal: chat)."""
    owner = security.request_owner(request)
    channels = payload.channels if payload else "chat"
    result = await daily_summary.generate_for_owner(request.app, owner, channels)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("detail") or "Özet üretilemedi.")
    return result


@router.get("/api/summary/history")
def summary_history(request: Request, limit: int = 30) -> dict:
    owner = security.request_owner(request)
    return {"summaries": v11.list_summaries(owner, limit=max(1, min(90, limit)))}
