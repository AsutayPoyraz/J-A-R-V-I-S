"""Kullanıcıya özel API anahtarları uçları (Özellik 5B).

Kurallar:
- Yalnızca JWT ile doğrulanmış kullanıcılar (misafir/local hariç) 200 alır;
  aksi halde 401/403.
- Değerler Fernet (JARVIS_MASTER_KEY) ile şifreli saklanır; listelemede
  değer ASLA dönmez (yalnızca has_value + updated_at).
- POST /test/{name}: anahtarı gerçek sağlayıcıya ping atar (ağ gerektirir).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from ..store import user_keys

logger = logging.getLogger("jarvis.api.user_settings")

router = APIRouter()

# Kaydedilebilir anahtar adları (mega prompt 5B listesi; F18 ile genişletildi).
ALLOWED_KEY_NAMES = (
    "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "SERPAPI_KEY", "OWM_API_KEY",
    "HA_URL", "HA_TOKEN", "CALLMEBOT_PHONE", "CALLMEBOT_KEY",
    "RELAY_URL", "RELAY_TOKEN", "WOL_NODE_URL", "WOL_NODE_SECRET",
)


def _require_user(request: Request) -> str:
    """JWT kullanıcı kimliğini zorunlu kılar; yoksa 401 döner."""
    user = getattr(getattr(request, "state", None), "user", None) or {}
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Bu özellik için giriş yapmalısınız.")
    return user_id


class KeyValueBody(BaseModel):
    value: str = Field(min_length=0, max_length=2048)


def database_audit(request: Request, detail: str) -> None:
    from ..store import database

    user = getattr(getattr(request, "state", None), "user", None) or {}
    database.audit(
        "user.api_keys", actor=f"user:{user.get('id') or '?'}", detail=detail[:120]
    )


@router.get("/api/user/api-keys")
def list_api_keys(request: Request) -> dict:
    user_id = _require_user(request)
    rows = user_keys.list_keys(user_id)
    by_name = {r["key_name"]: r for r in rows}
    items = []
    for name in ALLOWED_KEY_NAMES:
        row = by_name.get(name)
        items.append(
            {
                "key_name": name,
                "has_value": bool(row),
                "updated_at": row["updated_at"] if row else None,
            }
        )
    return {"keys": items}


@router.put("/api/user/api-keys/{name}")
def put_api_key(name: str, payload: KeyValueBody, request: Request) -> dict:
    user_id = _require_user(request)
    key_name = name.strip().upper()
    if key_name not in ALLOWED_KEY_NAMES:
        raise HTTPException(status_code=422, detail="Bilinmeyen anahtar adı.")
    if not user_keys.set_key(user_id, key_name, payload.value.strip()):
        raise HTTPException(status_code=500, detail="Anahtar kaydedilemedi.")
    database_audit(request, f"api_keys.set:{key_name}")
    return {"ok": True, "key_name": key_name}


@router.delete("/api/user/api-keys/{name}")
def delete_api_key(name: str, request: Request) -> dict:
    user_id = _require_user(request)
    key_name = name.strip().upper()
    if not user_keys.delete_key(user_id, key_name):
        raise HTTPException(status_code=404, detail="Anahtar bulunamadı.")
    database_audit(request, f"api_keys.delete:{key_name}")
    return {"ok": True}


@router.post("/api/user/api-keys/test/{name}")
def test_api_key(name: str, request: Request) -> dict:
    """Kayıtlı (veya .env'deki) anahtarla gerçek sağlayıcıya ping atar."""
    user_id = _require_user(request)
    key_name = name.strip().upper()
    value = user_keys.get_key(user_id, key_name) or _env_fallback(key_name)
    if not value:
        return {"ok": False, "detail": "Anahtar tanımlı değil."}
    result = _ping_provider(key_name, value)
    database_audit(
        request, f"api_keys.test:{key_name}:{'ok' if result['ok'] else 'fail'}"
    )
    return result


def _env_fallback(key_name: str) -> str:
    mapping = {
        "GROQ_API_KEY": config.GROQ_API_KEY,
        "OPENAI_API_KEY": config.OPENAI_API_KEY,
        "ANTHROPIC_API_KEY": config.ANTHROPIC_API_KEY,
        "GEMINI_API_KEY": config.GEMINI_API_KEY,
        "DEEPSEEK_API_KEY": config.DEEPSEEK_API_KEY,
        "SERPAPI_KEY": config.env("JARVIS_SERPAPI_KEY"),
        "OWM_API_KEY": config.OWM_API_KEY,
        "HA_URL": config.env("JARVIS_HA_URL"),
        "HA_TOKEN": config.env("JARVIS_HA_TOKEN"),
        "CALLMEBOT_PHONE": config.env("JARVIS_CALLMEBOT_PHONE"),
        "CALLMEBOT_KEY": config.env("JARVIS_CALLMEBOT_KEY"),
        "RELAY_URL": config.RELAY_URL,
        "RELAY_TOKEN": config.RELAY_TOKEN,
        "WOL_NODE_URL": config.env("JARVIS_WOL_NODE_URL"),
        "WOL_NODE_SECRET": config.env("JARVIS_WOL_NODE_SECRET"),
    }
    return mapping.get(key_name, "")


def _ping_provider(key_name: str, value: str) -> dict:
    """Anahtarı gerçek API'ye kısa bir istekle test eder."""
    import httpx

    probes = {
        "GROQ_API_KEY": (
            "https://api.groq.com/openai/v1/models",
            {"Authorization": f"Bearer {value}"},
        ),
        "OPENAI_API_KEY": (
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {value}"},
        ),
        "GEMINI_API_KEY": (
            f"https://generativelanguage.googleapis.com/v1beta/models?key={value}",
            {},
        ),
        "DEEPSEEK_API_KEY": (
            "https://api.deepseek.com/models",
            {"Authorization": f"Bearer {value}"},
        ),
        "ANTHROPIC_API_KEY": (
            "https://api.anthropic.com/v1/models",
            {"x-api-key": value, "anthropic-version": "2023-06-01"},
        ),
        "SERPAPI_KEY": (f"https://serpapi.com/account?api_key={value}", {}),
    }
    probe = probes.get(key_name)
    if probe is None:
        # URL/telefon tipi anahtarlar için yalnızca biçim denetimi yapılır.
        return {"ok": bool(value.strip()), "detail": "biçim denetimi (canlı ping yok)"}
    url, headers = probe
    try:
        resp = httpx.get(url, headers=headers, timeout=8.0)
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": f"ağ hatası: {exc}"}
    return {
        "ok": resp.status_code in (200, 201),
        "status": resp.status_code,
        "detail": "geçerli" if resp.status_code == 200 else f"HTTP {resp.status_code}",
    }

