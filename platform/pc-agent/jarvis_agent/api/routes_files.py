"""Dosya transferi uçları — telefon <-> PC paylaşım klasörü.

Güvenlik (integrations/files.py içinde): yol kaçışı engelli, ad sanitizeli,
50 MB sınırı (JARVIS_MAX_UPLOAD_MB ile değiştirilebilir), uzantı
allow-list/deny-list. Telefondan gelen dosyalar Downloads'a kaydedilir;
PC'ye WebSocket bildirimi (files.received) gönderilir.
Silme KRİTİK işlem sayılır: 2FA elevation ister (madde 15, routes_critical).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Query, Request
from fastapi import UploadFile
from fastapi.responses import FileResponse

from ..core import counters
from ..integrations import files as files_module
from .. import security
from ..store import database, section_f
from . import guards
from .routes_critical import require_elevation

logger = logging.getLogger("jarvis.api.files")

router = APIRouter()


@router.get("/api/files")
def list_files(request: object = None) -> dict:
    data = files_module.list_files()
    data["uploads_directory"] = str(files_module.uploads_dir())
    return data


@router.post("/api/files/upload")
async def upload_file(request: Request, file: UploadFile = File(...)) -> dict:
    if file.size is not None and file.size > files_module.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya {files_module.MAX_UPLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor.",
        )
    data = await file.read(files_module.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="Boş dosya.")
    if len(data) > files_module.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya {files_module.MAX_UPLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor.",
        )
    try:
        result = files_module.write_file(file.filename or "dosya", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (PermissionError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    counters.bump_command_count()
    database.audit("files.upload", detail=result["name"])
    # Bölüm F (madde 21): dosya XP'si — sunucu tarafında, misafir hariç.
    if not security.is_guest(request):
        owner = security.request_owner(request)
        section_f.award_xp(owner, "file")
        section_f.log_activity(owner, "file.upload", str(result.get("name", ""))[:60])
    _notify_pc(result)
    return result


def _notify_pc(result: dict) -> None:
    """PC'deki açık arayüzlere "dosya geldi" olayı yayınlar (WS)."""
    from . import ws as ws_module

    try:
        import asyncio

        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    from .. import config, security

    event = {
        "type": "files.received",
        "name": result.get("name"),
        "size": result.get("size"),
        "directory": result.get("directory"),
    }

    async def _publish() -> None:
        for owner in (f"local", "*all*"):
            if owner == "*all*":
                break
            await ws_module.manager.publish_to_owner(owner, event)
        _ = (config, security)

    loop.create_task(_publish())


@router.delete("/api/files/{name}")
def delete_file_endpoint(name: str, request: Request) -> dict:
    """Paylaşılan dosyayı siler — kritik işlem: 2FA elevation ister (madde 15).

    Loopback (PC) istekleri güvenilir kabul edilir; uzak istemcilerden
    X-Elevation-Token beklenir (yoksa 403 + code=2fa_elevation_required).
    """
    require_elevation(request)
    safe = files_module.sanitize_name(name)
    try:
        result = files_module.delete_file(safe)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    database.audit("files.delete", actor="elevated", detail=safe)
    return result


@router.get("/api/files/download")
def download_file(name: str = Query(...)) -> FileResponse:
    safe = files_module.sanitize_name(name)
    try:
        data_path = files_module.shared_dir() / safe
        resolved = files_module.read_file(safe)
        _ = len(resolved)  # okunabilirlik kontrolü
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    database.audit("files.download", detail=safe)
    return FileResponse(
        data_path,
        filename=safe,
        media_type="application/octet-stream",
    )
