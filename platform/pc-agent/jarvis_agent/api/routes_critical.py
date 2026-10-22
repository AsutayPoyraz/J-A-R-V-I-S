"""Kritik komut uçları (Bölüm C — madde 15: 2FA/biyometrik onay).

Kritik uçlar:
- DELETE /api/pair/devices/{id}   → cihaz token'ını iptal (routes_pair.py)
- DELETE /api/files/{name}        → paylaşılan dosya silme (routes_files.py)
- POST /api/system/shutdown       → PC'yi kapat (JARVIS_ALLOW_SHUTDOWN=1 gerekir)

2FA akışı (twofa.py): prepare → OTP PC ekranına WS ile düşer → confirm ile
2 dakikalık elevation token'ı → kritik uçta X-Elevation-Token başlığı.
Loopback (PC) istekleri güvenilir kabul edilir; yalnızca shutdown daima
elevation ister.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import config, security, twofa
from ..store import database
from . import ws as ws_module

router = APIRouter()

ELEVATION_REQUIRED = "2fa_elevation_required"


class ConfirmBody(BaseModel):
    challenge_id: str = Field(min_length=8, max_length=64)
    otp: str = Field(min_length=4, max_length=8)


def elevation_of(request: Request) -> str:
    return str(request.headers.get("x-elevation-token") or "").strip()


def require_elevation(request: Request) -> None:
    """Kritik uçlar için ortak kapı: loopback geçer, diğerleri elevation ister.

    403 yanıtındaki ``code`` alanı frontend'e OTP akışını başlatmasını söyler.
    """
    identity = twofa.request_identity(request)
    if identity == "local" and security.is_loopback(
        security._client_host(request)
    ):
        return  # PC (loopback) güvenilir uçtur.
    user = getattr(getattr(request, "state", None), "user", None) or {}
    user_id = str(user.get("id") or "")
    device = getattr(getattr(request, "state", None), "device", None) or {}
    if not user_id and device.get("device_id"):
        # Eşleşmiş cihaz kullanıcısız kritik işlem yapamaz; önce giriş isteriz.
        raise HTTPException(
            status_code=403,
            detail={"code": ELEVATION_REQUIRED, "reason": "giriş gerekli"},
        )
    if not user_id:
        raise HTTPException(
            status_code=403,
            detail={"code": ELEVATION_REQUIRED, "reason": "giriş gerekli"},
        )
    if not twofa.verify_elevation(elevation_of(request), user_id):
        raise HTTPException(
            status_code=403,
            detail={"code": ELEVATION_REQUIRED, "reason": "2FA onayı gerekli"},
        )


@router.post("/api/2fa/prepare")
async def prepare(request: Request) -> JSONResponse:
    """Yeni OTP üretir; PC ekranına WS ile yayınlar, uzak istemciye dönmez."""
    identity = twofa.request_identity(request)
    if identity == "local":
        user = security.require_user(request)
        user_id = str(user["id"])
    else:
        user = getattr(getattr(request, "state", None), "user", None) or {}
        user_id = str(user.get("id") or "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Giriş gerekli.")
    info = twofa.create_challenge(user_id)
    owner = getattr(getattr(request, "state", None), "owner", "") or ""
    event = {
        "type": "2fa.challenge",
        "challenge_id": info["challenge_id"],
        "otp": info["otp"],
        "expires_in": info["expires_in"],
    }
    if owner:
        await ws_module.manager.publish_to_owner(owner, event)
    user_id_claim = str(user.get("id") or "")
    if user_id_claim:
        await ws_module.manager.publish_to_user(user_id_claim, event)
    body = {
        "challenge_id": info["challenge_id"],
        "expires_in": info["expires_in"],
        # OTP yalnızca PC'ye (loopback) yanıt olarak da verilir.
        "otp": info["otp"] if identity == "local" else None,
    }
    return JSONResponse(body)


@router.post("/api/2fa/confirm")
def confirm_endpoint(payload: ConfirmBody, request: Request) -> JSONResponse:
    identity = twofa.request_identity(request)
    if identity == "local":
        user = security.require_user(request)
        user_id = str(user["id"])
    else:
        user = getattr(getattr(request, "state", None), "user", None) or {}
        user_id = str(user.get("id") or "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Giriş gerekli.")
    try:
        token = twofa.confirm(payload.challenge_id, payload.otp, user_id)
    except twofa.TwoFactorError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)
    database.audit("2fa.elevation_issued", actor=f"user:{user_id}")
    return JSONResponse(
        {"elevated_token": token, "expires_in": int(config.ELEVATION_TTL_SECONDS)}
    )
