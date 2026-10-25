"""Madde 31: Sentry gözlemlenebilirlik — opsiyonel ve sızdırmaz.

- SENTRY_DSN boşsa hiçbir şey yapılmaz (yerel kurulumda sıfır bağımlılık etkisi).
- DSN yalnızca .env'den okunur; kodda gömülü sırrı yoktur.
- before_send filtresi hassas alanları (token, şifre, şifreli not gövdesi,
  authorization başlığı) olaydan siler — gizli sohbet içeriği Sentry'ye gitmez.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("jarvis.observability")

# Sentry'ye asla gönderilmeyecek alan adları (küçük harf normalleştirilir).
_SENSITIVE_KEYS = {
    "authorization", "password", "password_hash", "token", "access_token",
    "refresh_token", "elevation", "x-elevation-token", "pairing_token",
    "title_cipher", "body_cipher", "otp", "secret", "api_key", "cookie",
}


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any]:
    """Sentry before_send: hassas anahtarları ve şüpheli değerleri temizler."""
    def _clean(obj: Any, depth: int = 0) -> Any:
        if depth > 6:
            return "[truncated]"
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if str(k).lower() in _SENSITIVE_KEYS:
                    out[k] = "[filtered]"
                else:
                    out[k] = _clean(v, depth + 1)
            return out
        if isinstance(obj, list):
            return [_clean(v, depth + 1) for v in obj[:50]]
        if isinstance(obj, str) and len(obj) > 2000:
            return obj[:2000] + "…[truncated]"
        return obj

    return _clean(event)  # type: ignore[return-value]


def init_sentry() -> bool:
    """DSN varsa Sentry'yi başlatır. Dönüş: aktif mi? (testler için)"""
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        log.info("SENTRY_DSN boş — Sentry devre dışı (madde 31: opsiyonel).")
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:  # bağımlılık yoksa uygulama çalışmaya devam eder
        log.warning("sentry-sdk kurulu değil; SENTRY_DSN yoksayıldı.")
        return False

    environment = (os.getenv("SENTRY_ENVIRONMENT") or "production").strip()
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE") or 0.1),
        before_send=scrub_event,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        send_default_pii=False,  # kullanıcı IP/kimlik bilgisi gönderilmez
    )
    log.info("Sentry başlatıldı (environment=%s).", environment)
    return True