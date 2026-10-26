"""Cihaz eşleştirme uçları (Faz 2).

Akış:
1. PC kullanıcı UI'da "Eşleştir" → POST /api/pair/start (yalnızca loopback).
2. UI QR gösterir: http://<lan-ip>:<port>/?pair=<kod>
3. Telefon QR'ı okur, sayfa ?pair= parametresini alıp
   POST /api/pair/claim çağırır → device_token localStorage'a yazılır.
4. Sonraki isteklerde telefon X-Device-Token başlığı gönderir.
"""
from __future__ import annotations

import io

import segno
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import config, security
from ..store import database  # madde 25: eşleşme olayları denetim günlüğüne yazılır

router = APIRouter()


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def _require_loopback(request: Request) -> None:
    if not _is_loopback(request):
        raise HTTPException(
            status_code=403, detail="Eşleştirme yalnızca PC üzerinden başlatılır."
        )


def pair_url(request: Request, code: str) -> str:
    ip = security.lan_ip() or "127.0.0.1"
    port = config.env("JARVIS_PORT", "8000")
    scheme = "https" if request.url.scheme == "https" else "http"
    return f"{scheme}://{ip}:{port}/?pair={code}"


class ClaimBody(BaseModel):
    code: str = Field(min_length=4, max_length=8)
    device_name: str = Field(default="telefon", max_length=40)


@router.post("/api/pair/start")
def start(request: Request) -> dict:
    _require_loopback(request)
    info = security.start_pairing()
    return {**info, "url": pair_url(request, info["code"])}


@router.get("/api/pair/qr.svg")
def qr_svg(request: Request) -> Response:
    """Aktif eşleştirme kodunun QR'ı (SVG). Kod yoksa önce /start çağrılır."""
    _require_loopback(request)
    info = security.pending_code_info()
    if not info.get("active"):
        info = security.start_pairing()
    url = pair_url(request, str(info["code"]))
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=6, border=2, dark="#e8ecf7")
    return Response(content=buf.getvalue(), media_type="image/svg+xml")


@router.get("/api/pair/status")
def status(request: Request) -> dict:
    _require_loopback(request)
    info = security.pending_code_info()
    return {
        "pending": bool(info.get("active")),
        "expires_in": info.get("expires_in"),
        "devices": security.list_devices(),
        "lan_ip": security.lan_ip(),
    }


@router.post("/api/pair/claim")
def claim(payload: ClaimBody) -> dict:
    """Kamuya açık uç: kod bilgisi olmayan sadece kodu deneyebilir."""
    result = security.claim(payload.code, payload.device_name)
    if result is None:
        raise HTTPException(status_code=400, detail="Kod geçersiz veya süresi doldu.")
    # Madde 25: cihaz eşleşmeleri güvenlik denetim kaydına yazılır.
    database.audit(
        "pair.claim",
        actor=str(result.get("owner_id") or payload.device_name)[:60],
        detail=str(payload.device_name)[:60],
    )
    return result


@router.delete("/api/pair/devices/{device_id}")
def remove_device(device_id: str, request: Request) -> dict:
    # Kritik işlem: cihaz token'ı iptali 2FA elevation ister (madde 15).
    # Loopback (PC) serbest; uzak istemciden X-Elevation-Token beklenir.
    from .routes_critical import require_elevation

    require_elevation(request)
    if not security.revoke(device_id):
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
    database.audit("pair.revoke", actor="elevated", detail=str(device_id)[:60])
    return {"revoked": device_id}
