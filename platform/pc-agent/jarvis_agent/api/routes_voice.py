"""Sesli mod uçları — mikrofon durumu, açma/kapama, sesli oturum, ayarlar.

Mikrofonun dinleme durumu arayüzde HER ZAMAN görünür olmalıdır
(gereklim 5.4); bu yüzden /api/voice/status her an sorgulanabilir ve
durum WS istatistik akışına da eklenmiştir.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..store import database
from ..voice.textmatch import normalize

logger = logging.getLogger("jarvis.api.voice")

router = APIRouter()


def _service(request: Request):
    return request.app.state.voice


@router.get("/api/voice/status")
def voice_status(request: Request) -> dict:
    return _service(request).status()


@router.get("/api/voice/devices")
def voice_devices(request: Request) -> dict:
    """Özellik 14.3: ses cihazları listesi (ayarlar sayfası dropdown'u)."""
    from ..voice import audio as audio_module

    devices = audio_module.list_input_devices()
    inputs = [d for d in devices if d["max_input_channels"] > 0]
    return {
        "devices": devices,
        "inputs": inputs,
        "selected": _selected_device_index(audio_module),
        "sd_available": audio_module._SD_AVAILABLE,
    }


def _selected_device_index(audio_module) -> Optional[int]:
    import os

    override = os.getenv("JARVIS_AUDIO_INPUT_DEVICE", "").strip()
    if override.isdigit():
        return int(override)
    try:
        return audio_module.resolve_input_device()
    except Exception:  # noqa: BLE001
        return None


@router.post("/api/voice/start")
def voice_start(request: Request) -> dict:
    service = _service(request)
    if not service.status().get("mic_available"):
        raise HTTPException(status_code=503, detail="Bu cihazda mikrofon bulunamadı.")
    result = service.start()
    database.audit("voice.start")
    return result


@router.post("/api/voice/stop")
def voice_stop(request: Request) -> dict:
    result = _service(request).stop()
    database.audit("voice.stop")
    return result


@router.post("/api/voice/mode/on")
def voice_mode_on(request: Request, payload: Optional[dict] = None) -> dict:
    """Sesli oturumu elle başlat (UI butonu / yazılı komut)."""
    service = _service(request)
    if not service.status().get("mic_available"):
        raise HTTPException(status_code=503, detail="Bu cihazda mikrofon bulunamadı.")
    reason = "ui_button"
    response = "Buyrun efendim, size nasıl yardımcı olabilirim?"
    if payload and isinstance(payload.get("reason"), str):
        reason = payload["reason"][:60]
    if payload and isinstance(payload.get("greeting"), str):
        response = payload["greeting"][:300]
    return service.start_voice_mode(reason=reason, response=response)


@router.post("/api/voice/mode/off")
def voice_mode_off(request: Request) -> dict:
    """Sesli oturumdan çık (wake dinlemeye dön; mikrofon açık kalır)."""
    _service(request).exit_voice_mode()
    return _service(request).status()


@router.post("/api/voice/say")
def voice_say(request: Request, payload: dict) -> dict:
    """Metni sesli oku (test ve hatırlatıcı duyuruları için)."""
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Metin boş olamaz.")
    if len(text) > 2000:
        raise HTTPException(status_code=422, detail="Metin çok uzun (maks 2000).")
    service = _service(request)
    # Madde 7/14: TTS ses/hız tercihi isteğin sahibinden okunur.
    ok = service.speak(text, owner_id=security.request_owner(request))
    return {"spoken": ok}


class VoiceSettingsUpdate(BaseModel):
    wake_phrases: Optional[list[str]] = Field(default=None)
    wake_response: Optional[str] = Field(default=None)
    exit_phrases: Optional[list[str]] = Field(default=None)
    clap_enabled: Optional[bool] = None
    clap_sensitivity: Optional[float] = Field(default=None, ge=1.0, le=20.0)


@router.get("/api/voice/settings")
def get_voice_settings(request: Request) -> dict:
    return _service(request).status()


@router.put("/api/voice/settings")
def update_voice_settings(payload: VoiceSettingsUpdate, request: Request) -> dict:
    service = _service(request)
    settings = service.settings

    if payload.wake_phrases is not None:
        cleaned = [normalize(p) for p in payload.wake_phrases if p and p.strip()]
        cleaned = [p for p in cleaned if len(p) >= 4][:12]
        if not cleaned:
            raise HTTPException(status_code=422, detail="En az bir uyandırma ifadesi gerekli.")
        settings.wake_phrases = cleaned
    if payload.wake_response is not None and payload.wake_response.strip():
        default_phrase = settings.wake_phrases[0] if settings.wake_phrases else "hey jarvis"
        settings.wake_responses = {default_phrase: payload.wake_response.strip()[:200]}
    if payload.exit_phrases is not None:
        cleaned = [normalize(p) for p in payload.exit_phrases if p and p.strip()]
        settings.exit_phrases = [p for p in cleaned if len(p) >= 3][:12] or ["kapat", "cikis"]
    if payload.clap_enabled is not None:
        settings.clap_enabled = bool(payload.clap_enabled)
    if payload.clap_sensitivity is not None:
        settings.clap_sensitivity = float(payload.clap_sensitivity)

    service.apply_settings()
    settings.persist()
    database.audit(
        "voice.settings_update",
        detail=f"clap={settings.clap_enabled}/{settings.clap_sensitivity} "
               f"wake={len(settings.wake_phrases)}",
    )
    return service.status()
