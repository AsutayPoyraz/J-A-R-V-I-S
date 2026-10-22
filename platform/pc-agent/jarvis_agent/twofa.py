"""Kritik komutlar için 2FA (Bölüm C — madde 15).

Model (kişisel kullanım MVP'si):
- Kritik uç (cihaz kaldırma, dosya silme, PC kapatma) çağrılmadan önce
  POST /api/2fa/prepare ile 6 haneli tek kullanımlık OTP üretilir.
- OTP, WS ile sahibin DİĞER cihazlarına (PC ekranı) yayınlanır; uzak
  istemciye (telefon) yanıt içinde asla dönülmez. Loopback (PC) çağrısında
  OTP yanıtla döner (PC zaten güvenilir uçtur).
- POST /api/2fa/confirm ile OTP doğrulanır → 2 dakikalık kısa ömürlü
  "elevation" JWT'si verilir; kritik uçlar X-Elevation-Token bekler.
- 3 hatalı OTP denemesi challenge'ı geçersiz kılar.

KISMEN: SMS OTP ve biyometrik (Face ID/parmak) doğrulama sağlayıcı
gerektirir; bu MVP'de yoktur. Eşdeğer onay = PC ekranında gösterilen kod.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any, Optional

from . import config
from .store import database

_CHALLENGE_TTL_SECONDS = 300          # OTP 5 dk geçerli
_MAX_OTP_ATTEMPTS = 3

_lock = threading.Lock()
_challenges: dict[str, dict[str, Any]] = {}


class TwoFactorError(Exception):
    """Kullanıcıya dönülebilir 2FA hatası (HTTP status ile)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def create_challenge(user_id: str) -> dict[str, Any]:
    """Yeni OTP challenge'ı üretir (kullanıcının eski challenge'ları geçersizleşir)."""
    otp = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = secrets.token_urlsafe(16)
    now = time.time()
    with _lock:
        for cid in [c for c, v in _challenges.items() if v.get("user_id") == user_id]:
            _challenges.pop(cid, None)
        _challenges[challenge_id] = {
            "otp": otp,                      # yalnızca bellekte, hash'siz (kısa ömür)
            "user_id": user_id,
            "expires_at": now + _CHALLENGE_TTL_SECONDS,
            "attempts": 0,
        }
        # Süresi geçmişleri temizle (bellek hijyeni).
        for cid in [c for c, v in _challenges.items() if v["expires_at"] < now]:
            _challenges.pop(cid, None)
    database.audit("2fa.prepare", actor=f"user:{user_id}")
    return {"challenge_id": challenge_id, "otp": otp, "expires_in": _CHALLENGE_TTL_SECONDS}


def confirm(challenge_id: str, otp: str, user_id: str) -> str:
    """OTP'yi doğrular ve elevation token'ı döndürür."""
    with _lock:
        challenge = _challenges.get(challenge_id)
        if not challenge or challenge["expires_at"] < time.time():
            _challenges.pop(challenge_id, None)
            raise TwoFactorError("Doğrulama oturumu bulunamadı veya süresi doldu.", 400)
        if challenge["user_id"] != user_id:
            raise TwoFactorError("Bu doğrulama oturumu bu hesaba ait değil.", 403)
        if challenge["attempts"] >= _MAX_OTP_ATTEMPTS:
            _challenges.pop(challenge_id, None)
            raise TwoFactorError("Çok fazla hatalı deneme. Yeni kod isteyin.", 429)
        challenge["attempts"] += 1
        if not secrets.compare_digest(str(otp).strip(), challenge["otp"]):
            # Challenge'ı burada silme: bir sonraki deneme 429 (kilitli) dönsün.
            # Bellek hijyenini TTL temizliği üstlenir.
            raise TwoFactorError("Kod hatalı.", 400)
        _challenges.pop(challenge_id, None)
    database.audit("2fa.confirmed", actor=f"user:{user_id}")
    from . import auth  # döngüsel import'ları yerinde çöz

    return auth.make_token(
        user_id, "elevation", int(config.ELEVATION_TTL_SECONDS)
    )


def verify_elevation(token: str, user_id: str) -> bool:
    """Elevation token'ı bu kullanıcı için geçerli mi?"""
    if not token:
        return False
    from . import auth

    try:
        claims = auth.decode_token(token, expected_type="elevation")
    except auth.AuthError:
        return False
    return str(claims.get("sub") or "") == user_id


def request_identity(request: Any) -> str:
    """İsteğin kimlik bağlamı: user:<id> | device:<id> | local."""
    state = getattr(request, "state", None)
    user = getattr(state, "user", None) or {}
    if user.get("id"):
        return f"user:{user['id']}"
    device = getattr(state, "device", None) or {}
    if device.get("device_id"):
        return f"device:{device['device_id']}"
    return "local"
