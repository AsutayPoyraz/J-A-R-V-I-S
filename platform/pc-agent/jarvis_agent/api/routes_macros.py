"""Sesli/metin komut makroları uçları (Özellik 9).

Yol notu: mevcut section_f /api/macros (kısayollar) ile çakışmaması için
v11 trigger'lı makrolar /api/command-macros altındadır (tablo: command_macros).
Tetikleme: STT/metin pipeline'ı (routes_chat + voice service) textmatch
üzerinden ``store.v11.find_macro_by_trigger`` çağırır.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..store import v11

logger = logging.getLogger("jarvis.api.macros")

router = APIRouter()


class MacroStep(BaseModel):
    type: str = Field(min_length=1, max_length=16)  # chat | api_call | delay
    params: dict = Field(default_factory=dict)


class MacroBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    trigger_phrase: str = Field(min_length=2, max_length=120)
    steps: list[MacroStep] = Field(default_factory=list, max_length=20)


@router.get("/api/command-macros")
def get_macros(request: Request) -> dict:
    return {"macros": v11.list_macros(security.request_owner(request))}


@router.post("/api/command-macros")
def post_macro(payload: MacroBody, request: Request) -> dict:
    macro = v11.create_macro(
        security.request_owner(request),
        payload.name,
        payload.trigger_phrase,
        [step.model_dump() for step in payload.steps],
    )
    if macro is None:
        raise HTTPException(
            status_code=422,
            detail="Makro oluşturulamadı (misafir, geçersiz adım veya tetikleyici zaten var).",
        )
    return {"macro": macro}


@router.delete("/api/command-macros/{macro_id}")
def delete_macro(macro_id: int, request: Request) -> dict:
    if not v11.delete_macro(security.request_owner(request), macro_id):
        raise HTTPException(status_code=404, detail="Makro bulunamadı.")
    return {"ok": True}


@router.post("/api/command-macros/{macro_id}/run")
async def run_macro(macro_id: int, request: Request) -> dict:
    """Makroyu çalıştırır: chat adımları → sohbet çekirdeği, delay → bekleme,
    api_call → yerel GET isteği (yalnızca /api/ önekli güvenli uçlar)."""
    owner = security.request_owner(request)
    macro = v11.get_macro(owner, macro_id)
    if macro is None:
        raise HTTPException(status_code=404, detail="Makro bulunamadı.")

    from ..chat.service import run_chat

    outputs = []
    for step in macro.get("steps") or []:
        stype = step.get("type")
        params = step.get("params") or {}
        if stype == "delay":
            seconds = min(10.0, max(0.1, float(params.get("seconds") or 1)))
            await asyncio.sleep(seconds)
            outputs.append({"type": "delay", "seconds": seconds})
        elif stype == "chat":
            message = str(params.get("message") or "").strip()
            if not message:
                continue
            result = await run_chat(
                message,
                request.app.state.llm,
                request.app.state.stats,
                source="macro",
                owner_id=owner,
                persist=False,
            )
            outputs.append({"type": "chat", "message": message, "reply": result.get("reply")})
        elif stype == "api_call":
            endpoint = str(params.get("endpoint") or "")
            method = str(params.get("method") or "GET").upper()
            # Güvenlik: yalnızca yerel /api uçları, yalnızca GET/POST.
            if not endpoint.startswith("/api/") or method not in ("GET", "POST"):
                outputs.append({"type": "api_call", "endpoint": endpoint, "error": "izin yok"})
                continue
            outputs.append(
                {"type": "api_call", "endpoint": endpoint, "method": method,
                 "note": "istemci tarafında yürütülür"}
            )
    database_audit(owner, f"macro.run:{macro['name']}")
    return {"macro": macro["name"], "outputs": outputs}


def database_audit(owner: str, detail: str) -> None:
    from ..store import database

    database.audit("macros", actor=owner, detail=detail[:120])
