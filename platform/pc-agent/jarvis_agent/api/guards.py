"""Misafir modu kapıları (Prompt 2).

Kural: misafir (kimliksiz uzak istemci) yalnızca sohbet, sağlık, auth ve
eşleştirme gibi allow-list uçlarını kullanır. Dosya transferi, kamera,
cihaz kontrolü (WoL), akıllı ev, entegrasyonlar, hatırlatıcılar ve ses
uçları misafire KAPALIDIR (403 + Türkçe mesaj).

WebSocket tarafında misafire yalnızca sohbet olayları verilir; istatistik
akışı (sistem bilgisi) gizlenir (bkz. api/ws.py).
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .. import security
from ..store import database

# Misafire açık önekler (allow-list).
GUEST_ALLOWED_PREFIXES = (
    "/api/health",
    "/api/chat",
    "/api/auth/",
    "/api/pair/",
    "/api/session",
    "/api/weather",
)

GUEST_DENIED_MESSAGE = "Misafir modunda bu özellik kullanılamaz."


def is_guest(request: Any) -> bool:
    return security.is_guest(request)


def require_not_guest(request: Any) -> None:
    """Misafir isteği 403 ile reddeder (uç başında çağrılır)."""
    if is_guest(request):
        raise HTTPException(status_code=403, detail=GUEST_DENIED_MESSAGE)


def mode_of(request: Any) -> str:
    """Oturum modu: guest | user | local."""
    if security.is_loopback(security._client_host(request)):
        return "local"
    if getattr(getattr(request, "state", None), "user", None):
        return "user"
    if getattr(getattr(request, "state", None), "device", None):
        return "user"
    return "guest"


def capabilities_of(request: Any) -> dict[str, bool]:
    """İstemcinin hangi özellikleri kullanabileceğini söyler."""
    owner = security.request_owner(request)
    guest = is_guest(request)
    can_write = not guest and not database.is_guest(owner)
    return {
        "chat": True,
        "files": not guest,
        "device_control": not guest,
        "history": not guest,
        "settings_write": can_write,
    }


def session_payload(request: Any) -> dict[str, Any]:
    return {"mode": mode_of(request), "capabilities": capabilities_of(request)}
