"""Ayarlar uçları — kullanıcıya özel tema/şehir/dil/panel konumu (Bölüm A).

Kurallar:
- Her istek ``request.state.owner`` etiketiyle gelir (app.py middleware);
  ayarlar bu etikete göre user_settings tablosunda izole tutulur.
- Misafirler (owner 'guest:*') ayar GÖRÜR ama kalıcı yazamaz (madde 6).
- Tema değerleri config.ALLOWED_BG_COLORS ile sınırlıdır (madde 4: bordo dahil).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import config
from ..store import database

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Kısmi ayar güncellemesi; yalnızca gönderilen alanlar değişir."""

    background_color: str | None = None
    city: str | None = None
    language: str | None = None
    chat_position: str | None = None
    conversation_mode: str | None = None
    # Madde 14: TTS tercihleri
    tts_rate: float | None = None
    tts_voice: str | None = None
    # Özel palet: {"accent": "r g b", "accent_soft": "r g b", "bg_page": "#hex"}
    custom_palette: dict[str, str] | None = None


@router.get("/api/settings")
def get_settings(request: Request) -> dict:
    owner = getattr(request.state, "owner", "local")
    row = database.get_user_settings(owner)
    theme = row["theme"] if row["theme"] in config.ALLOWED_BG_COLORS else config.DEFAULT_BG_COLOR
    language = row["language"] if row["language"] in config.ALLOWED_LANGUAGES else config.DEFAULT_LANGUAGE
    position = (
        row["chat_position"]
        if row["chat_position"] in config.ALLOWED_CHAT_POSITIONS
        else config.DEFAULT_CHAT_POSITION
    )
    return {
        "background_color": theme,
        "city": row["city"],
        "language": language,
        "chat_position": position,
        "conversation_mode": _mode(row),
        "custom_palette": _palette(row),
        "tts_rate": _tts_rate(row),
        "tts_voice": _tts_voice(row),
        "twofa_enabled": bool(row.get("twofa_enabled", 1)),
        # "guest" test sözleşmesi; owner_is_guest geriye dönük uyumluluk için.
        "guest": database.is_guest(owner),
        "owner_is_guest": database.is_guest(owner),
        "allowed_background_colors": list(config.ALLOWED_BG_COLORS),
        "allowed_languages": list(config.ALLOWED_LANGUAGES),
        "allowed_chat_positions": list(config.ALLOWED_CHAT_POSITIONS),
        "allowed_conversation_modes": list(config.ALLOWED_CONVERSATION_MODES),
        "allowed_tts_voices": list(config.ALLOWED_TTS_VOICES),
    }


def _mode(row: dict) -> str:
    mode = str(row.get("conversation_mode") or config.DEFAULT_CONVERSATION_MODE)
    return mode if mode in config.ALLOWED_CONVERSATION_MODES else config.DEFAULT_CONVERSATION_MODE


def _palette(row: dict) -> dict[str, str] | None:
    raw = row.get("custom_palette")
    if not raw:
        return None
    try:
        import json

        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return {k: str(v) for k, v in parsed.items() if k in config.ALLOWED_PALETTE_KEYS}


def _tts_rate(row: dict) -> float:
    """Madde 14: hız 0.5-2.0 aralığına kırpılır."""
    try:
        return min(2.0, max(0.5, float(row.get("tts_rate") or 1.0)))
    except (TypeError, ValueError):
        return 1.0


def _tts_voice(row: dict) -> str:
    voice = row.get("tts_voice")
    return voice if voice in config.ALLOWED_TTS_VOICES else config.DEFAULT_TTS_VOICE


@router.put("/api/settings")
def update_settings(request: Request, payload: SettingsUpdate) -> dict:
    owner = getattr(request.state, "owner", "local")
    if database.is_guest(owner):
        # Madde 6/16: misafir oturumda kalıcı ayar yazma yok (401: kimlik gerekir).
        raise HTTPException(
            status_code=401, detail="Misafir oturumda ayarlar kalıcı olarak değiştirilemez."
        )

    patch: dict[str, str] = {}
    if payload.background_color is not None:
        if payload.background_color not in config.ALLOWED_BG_COLORS:
            raise HTTPException(status_code=422, detail="Geçersiz arka plan rengi.")
        patch["theme"] = payload.background_color
    if payload.language is not None:
        if payload.language not in config.ALLOWED_LANGUAGES:
            raise HTTPException(status_code=422, detail="Geçersiz dil.")
        patch["language"] = payload.language
    if payload.chat_position is not None:
        if payload.chat_position not in config.ALLOWED_CHAT_POSITIONS:
            raise HTTPException(status_code=422, detail="Geçersiz panel konumu.")
        patch["chat_position"] = payload.chat_position
    if payload.city is not None:
        city = payload.city.strip()
        if not (1 <= len(city) <= 64):
            raise HTTPException(
                status_code=422, detail="Şehir adı 1-64 karakter olmalı."
            )
        patch["city"] = city
    if payload.conversation_mode is not None:
        if payload.conversation_mode not in config.ALLOWED_CONVERSATION_MODES:
            raise HTTPException(status_code=422, detail="Geçersiz konuşma modu.")
        patch["conversation_mode"] = payload.conversation_mode
    if payload.tts_voice is not None:
        if payload.tts_voice not in config.ALLOWED_TTS_VOICES:
            raise HTTPException(status_code=422, detail="Geçersiz TTS sesi.")
        patch["tts_voice"] = payload.tts_voice
    if payload.tts_rate is not None:
        if not (0.5 <= payload.tts_rate <= 2.0):
            raise HTTPException(
                status_code=422, detail="TTS hızı 0.5-2.0 arasında olmalı."
            )
        patch["tts_rate"] = round(payload.tts_rate, 2)
    if payload.custom_palette is not None:
        import json
        import re

        rgb = re.compile(r"^\d{1,3} \d{1,3} \d{1,3}$")
        hex_color = re.compile(r"^#[0-9a-fA-F]{6}$")
        palette: dict[str, str] = {}
        for key, value in payload.custom_palette.items():
            if key not in config.ALLOWED_PALETTE_KEYS:
                raise HTTPException(status_code=422, detail="Geçersiz palet anahtarı.")
            value = str(value).strip()
            pattern = hex_color if key == "bg_page" else rgb
            if not pattern.fullmatch(value):
                raise HTTPException(status_code=422, detail="Geçersiz renk biçimi.")
            if key != "bg_page":
                parts = [int(p) for p in value.split()]
                if any(p > 255 for p in parts):
                    raise HTTPException(status_code=422, detail="Geçersiz renk değeri.")
            palette[key] = value
        patch["custom_palette"] = json.dumps(palette) if palette else ""

    if patch:
        database.update_user_settings(owner, patch)
        database.audit(
            "settings.update",
            actor=owner,
            detail=",".join(f"{k}={v}" for k, v in sorted(patch.items()))[:200],
        )
        # Prompt 9: aynı sahibin diğer cihazlarına (ve aynı kullanıcının tüm
        # telefonlarına) yayınla. WS yoksa sessizce geç.
        _broadcast_settings_update(request, owner, patch)
    return get_settings(request)


def _broadcast_settings_update(request: Request, owner: str, patch: dict) -> None:
    from . import ws as ws_module

    user = getattr(getattr(request, "state", None), "user", None) or {}
    event = {
        "type": "settings.changed",
        "owner": owner,
        "changes": {k: v for k, v in patch.items() if k not in ("custom_palette",)},
        "custom_palette": get_settings(request).get("custom_palette"),
    }
    try:
        import asyncio

        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _publish() -> None:
        await ws_module.manager.publish_to_owner(owner, event)
        user_id = str(user.get("id") or "")
        if user_id:
            await ws_module.manager.publish_to_user(user_id, event)

    loop.create_task(_publish())
