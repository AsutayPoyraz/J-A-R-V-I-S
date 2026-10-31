"""Ekran özeti & bağlamsal farkındalık ucu (Özellik 7).

Yol notu: mevcut Bölüm E `POST /api/screen/analyze` (soru bazlı analiz)
ile çakışmaması için F7 uçları `/api/screen/vision` altındadır.
Akış: frontend getDisplayMedia (kullanıcı onaylı) → 30 sn'de bir kare →
POST /api/screen/vision (base64 JPEG) → vision LLM → tek cümle öneri → WS push.

Gizlilik:
- Görüntüler ASLA diske yazılmaz; yalnızca RAM'de işlenir.
- JARVIS_SCREEN_ANALYSIS_DISABLED=1 ile tamamen kapatılır.
"""
from __future__ import annotations

import base64
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from .. import security

logger = logging.getLogger("jarvis.api.screen")

router = APIRouter()

_MAX_IMAGE_BYTES = 1_500_000  # ~1.5 MB
_VISION_PROMPT = (
    "Kullanıcı ne yapıyor? Hangi uygulama açık? Yardımcı olabilecek bir şey "
    "var mı? Türkçe, tek cümle öner. Görüntüde kişisel veri varsa onu asla "
    "tekrar etme."
)


def _disabled() -> bool:
    return config.env("JARVIS_SCREEN_ANALYSIS_DISABLED", "").strip() == "1"


class ScreenFrame(BaseModel):
    image: str = Field(min_length=32, max_length=2_500_000)  # data:image/jpeg;base64,.


def _decode_data_url(image: str) -> bytes:
    raw = image.split(",", 1)[1] if "," in image else image
    try:
        return base64.b64decode(raw, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Geçersiz görüntü verisi.") from exc


async def _vision_via_openai_compat(api_key: str, base_url: str, model: str,
                                    image_b64: str) -> str:
    """OpenAI-uyumlu vision çağrısı (OpenAI / Gemini compat)."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 200,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=headers
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Vision sağlayıcı HTTP {resp.status_code}")
    data = resp.json()
    return str(data["choices"][0].get("message", {}).get("content") or "").strip()


async def _vision_via_anthropic(api_key: str, model: str, image_bytes: bytes) -> str:
    payload = {
        "model": model,
        "max_tokens": 200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.b64encode(image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }
        ],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages", json=payload, headers=headers
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Anthropic HTTP {resp.status_code}")
    data = resp.json()
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(parts).strip()


@router.post("/api/screen/vision")
async def analyze_screen(payload: ScreenFrame, request: Request) -> dict:
    """Kareyi vision modeline gönderir; öneri üretir ve WS ile iletir."""
    if _disabled():
        raise HTTPException(status_code=503, detail="Ekran analizi devre dışı (env).")
    if security.is_guest(request):
        raise HTTPException(status_code=403, detail="Misafir ekran analizi kullanamaz.")
    image_bytes = _decode_data_url(payload.image)
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Görüntü çok büyük (maks ~1.5 MB).")
    image_b64 = base64.b64encode(image_bytes).decode()

    suggestion = ""
    detail = ""
    try:
        if config.GEMINI_API_KEY:
            suggestion = await _vision_via_openai_compat(
                config.GEMINI_API_KEY,
                "https://generativelanguage.googleapis.com/v1beta/openai",
                config.GEMINI_MODEL,
                image_b64,
            )
        elif config.OPENAI_API_KEY:
            openai_model = (
                config.DEFAULT_MODELS["openai"]
                if str(config.DEFAULT_MODELS["openai"]).startswith("gpt-4")
                else "gpt-4o-mini"
            )
            suggestion = await _vision_via_openai_compat(
                config.OPENAI_API_KEY, "https://api.openai.com/v1", openai_model, image_b64
            )
        elif config.ANTHROPIC_API_KEY:
            suggestion = await _vision_via_anthropic(
                config.ANTHROPIC_API_KEY, config.DEFAULT_MODELS["anthropic"], image_bytes
            )
        else:
            detail = "Vision yetenekli sağlayıcı yapılandırılmadı (graceful degradation)."
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — analiz arızası 500 dönmesin
        logger.warning("Ekran analizi başarısız: %s", exc)
        detail = f"analiz hatası: {exc}"

    if not suggestion:
        return {"ok": False, "suggestion": "", "detail": detail or "öneri üretilemedi"}

    owner = security.request_owner(request)
    try:
        from . import ws as ws_module

        await ws_module.manager.publish_to_owner(
            owner, {"type": "screen.suggestion", "suggestion": suggestion}
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Öneri WS gönderimi başarısız: %s", exc)
    return {"ok": True, "suggestion": suggestion}

