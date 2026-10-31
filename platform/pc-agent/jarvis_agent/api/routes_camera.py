"""Kamera uçları."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from ..core import counters
from ..store import database
from ..camera.service import CameraError
from .guards import require_permission

logger = logging.getLogger("jarvis.api.camera")

router = APIRouter()


def _service(request: Request):
    return request.app.state.camera


def _to_503(exc: CameraError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.post("/api/camera/open")
def camera_open(request: Request) -> dict:
    require_permission(request, "camera")  # madde 25: hassas işlem kapısı
    try:
        status = _service(request).open()
    except CameraError as exc:
        logger.info("Kamera açılamadı: %s", exc)
        raise _to_503(exc) from exc
    counters.bump_command_count()
    database.audit("camera.open")
    return status


@router.post("/api/camera/close")
def camera_close(request: Request) -> dict:
    status = _service(request).close()
    counters.bump_command_count()
    database.audit("camera.close")
    return status


@router.get("/api/camera/status")
def camera_status(request: Request) -> dict:
    return _service(request).status()


@router.post("/api/camera/install")
async def camera_install(request: Request) -> dict:
    """Özellik 3.4: opencv-python kurulumu (WS ilerlemesi dahil)."""
    from ..camera import service as cam

    if cam.opencv_installed():
        return {"ok": True, "detail": "opencv-python zaten kurulu.", "progress": cam.install_progress()}
    # Otomatik kurulum kapatılabilir (mega prompt Genel Notlar/3).
    from .. import config

    if config.env("JARVIS_CAMERA_AUTO_INSTALL", "1") == "0":
        raise HTTPException(
            status_code=403,
            detail=(
                "Otomatik kurulum kapalı (JARVIS_CAMERA_AUTO_INSTALL=0). "
                "Manuel komut: pip install opencv-python"
            ),
        )
    result = await asyncio.to_thread(cam.install_opencv)
    # İlerlemeyi WS ile bildir (bağlı istemci varsa).
    try:
        from . import ws as ws_module

        await ws_module.manager.broadcast_all(
            {"type": "camera.install", **result}
        )
    except Exception:  # noqa: BLE001 — WS yoksa kurulum sonucu yeterli
        pass
    return {**result, "progress": cam.install_progress()}


async def _noop() -> None:  # pragma: no cover
    return None


@router.post("/api/camera/capture")
def camera_capture(request: Request) -> dict:
    try:
        result = _service(request).capture()
    except CameraError as exc:
        raise _to_503(exc) from exc
    counters.bump_command_count()
    database.audit("camera.capture")
    return result
