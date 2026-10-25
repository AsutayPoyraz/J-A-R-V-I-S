"""Google Home SDM OAuth, discovery and command endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

from ..integrations import google_home
from .. import security
from .guards import require_permission

router = APIRouter()
logger = logging.getLogger("jarvis.api.smart_home")


def _owner(request: Request) -> str:
    return security.request_owner(request)


@router.get("/api/smart-home/status")
def smart_home_status(request: Request) -> dict[str, Any]:
    return google_home.status(_owner(request))


@router.get("/api/smart-home/oauth/start")
def oauth_start(request: Request) -> dict[str, str]:
    try:
        return {"authorization_url": google_home.authorization_url(
            _owner(request), request.app.state.google_home_oauth_states
        )}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/smart-home/oauth/callback", response_class=HTMLResponse)
def oauth_callback(request: Request, code: str = "", state: str = "", error: str = "") -> str:
    if error:
        return "<h2>Google Home bağlantısı iptal edildi.</h2><script>window.close()</script>"
    try:
        google_home.complete_oauth(code, state, request.app.state.google_home_oauth_states)
    except Exception:
        logger.exception("Google Home OAuth callback failed")
        return "<h2>Google Home bağlantısı kurulamadı.</h2><p>Panelden tekrar deneyin.</p>"
    return "<h2>Google Home bağlandı.</h2><p>Bu pencereyi kapatabilirsiniz.</p><script>window.close()</script>"


@router.post("/api/smart-home/disconnect")
def disconnect(request: Request) -> dict[str, bool]:
    google_home.disconnect(_owner(request))
    return {"disconnected": True}


@router.get("/api/smart-home/devices")
def devices(request: Request) -> dict[str, Any]:
    try:
        return google_home.list_devices(_owner(request))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Home cihazları alınamadı: {exc}") from exc


class CommandBody(BaseModel):
    device_id: str = Field(min_length=1, max_length=300)
    action: str = Field(pattern="^(on|off|brightness|temperature)$")
    value: float | None = Field(default=None, ge=0, le=100)


@router.post("/api/smart-home/command")
def send_command(payload: CommandBody, request: Request) -> dict[str, Any]:
    require_permission(request, "smart_home")  # madde 25: hassas işlem kapısı
    try:
        return google_home.command(_owner(request), payload.device_id, payload.action, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cihaz komutu başarısız: {exc}") from exc
