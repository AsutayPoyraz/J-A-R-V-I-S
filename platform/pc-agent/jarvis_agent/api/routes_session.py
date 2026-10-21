"""Oturum bilgisi ucu (Prompt 2): mod + yetenekler.

Arayüz açılışta çağırır: misafirde devre dışı butonlar bu yanıtla çizilir.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from . import guards

router = APIRouter()


@router.get("/api/session")
def session(request: Request) -> dict:
    return guards.session_payload(request)
