"""Bölüm G API uçları — madde 25 (gizlilik/güvenlik) ve madde 27 (sağlık).

Madde 25:
- Gizli notlar: istemci AES-GCM ile şifreler, sunucu yalnız opak şifreli metin
  saklar (E2EE MVP — anahtar sunucuya hiç gitmez; sınırlar FİNAL raporunda).
- İzin yönetimi: hassas işlemler (shutdown, dosya, kamera, akıllı ev) için
  owner bazlı aç/kapa; enforcement guards.require_permission ile yapılır.
- Güvenlik denetimi: owner bazlı olay listesi + CSV indirme.

Madde 27:
- Ruh hâli (mood) seçimi → sohbet üslubuna girdi (chat/service).
- Günlük kullanım: chat'te touch_usage() ile saniye sayılır; limit aşılırsa
  sohbet ucu 429 + code=daily_limit_reached döner.
"""
from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import security
from ..store import database, section_g
from .guards import require_not_guest

log = logging.getLogger("jarvis.api.privacy")
router = APIRouter()


def _ctx(request: Request) -> dict:
    """Ortak bağlam: owner çöz + misafiri reddet (kalıcı kayıt ilkesi)."""
    require_not_guest(request)
    return {"owner_id": security.request_owner(request)}


# ── Madde 25: gizli notlar (istemci tarafı şifreli) ──────────────────────────

class SecureNoteBody(BaseModel):
    title_cipher: str = Field(min_length=1, max_length=6000)
    body_cipher: str = Field(min_length=1, max_length=60000)


@router.get("/api/privacy/notes")
def privacy_notes_list(ctx: dict = Depends(_ctx)) -> dict:
    return {"notes": section_g.list_secure_notes(ctx["owner_id"])}


@router.post("/api/privacy/notes")
def privacy_notes_create(body: SecureNoteBody, ctx: dict = Depends(_ctx)) -> dict:
    # Not: Sunucu şifreyi AÇMAZ/DOĞRULAMAZ; opak base64 bekler, uzunluk sınırlı.
    nid = section_g.add_secure_note(
        ctx["owner_id"], body.title_cipher, body.body_cipher
    )
    if nid is None:
        raise HTTPException(status_code=422, detail="Şifreli not biçimi geçersiz.")
    return {"id": nid}


@router.delete("/api/privacy/notes/{note_id}")
def privacy_notes_delete(note_id: int, ctx: dict = Depends(_ctx)) -> dict:
    if not section_g.delete_secure_note(ctx["owner_id"], note_id):
        raise HTTPException(status_code=404, detail="Not bulunamadı.")
    return {"deleted": True}


# ── Madde 25: izin yönetimi ──────────────────────────────────────────────────

class PermissionBody(BaseModel):
    allowed: bool


@router.get("/api/privacy/permissions")
def privacy_permissions(ctx: dict = Depends(_ctx)) -> dict:
    return {
        "permissions": section_g.get_permissions(ctx["owner_id"]),
        "known": list(section_g.PERMISSIONS),
    }


@router.put("/api/privacy/permissions/{key}")
def privacy_permission_set(
    key: str, body: PermissionBody, ctx: dict = Depends(_ctx)
) -> dict:
    if key not in section_g.PERMISSIONS:
        raise HTTPException(status_code=422, detail="Bilinmeyen izin anahtarı.")
    section_g.set_permission(ctx["owner_id"], key, body.allowed)
    section_g.audit(
        ctx["owner_id"],
        "privacy.permission_changed",
        detail=f"{key}={'on' if body.allowed else 'off'}",
    )
    return {"key": key, "allowed": body.allowed}


# ── Madde 25: güvenlik denetim kaydı (indirilebilir) ─────────────────────────

@router.get("/api/privacy/audit")
def privacy_audit(days: int = 30, limit: int = 200, ctx: dict = Depends(_ctx)) -> dict:
    days = max(1, min(days, 365))
    limit = max(1, min(limit, 1000))
    return {"entries": section_g.list_audit(ctx["owner_id"], days=days, limit=limit)}


@router.get("/api/privacy/audit/export.csv")
def privacy_audit_export(days: int = 90, ctx: dict = Depends(_ctx)):
    """CSV indirme (madde 25: Security Audit Log indirilebilir)."""
    days = max(1, min(days, 365))
    rows = section_g.list_audit(ctx["owner_id"], days=days, limit=1000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "event_type", "detail", "ip"])
    for r in rows:
        writer.writerow([r.get("created_at", ""), r.get("event_type", ""),
                         r.get("detail", ""), r.get("ip", "")])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jarvis-security-audit.csv"'},
    )


# ── Madde 27: sağlık — ruh hâli ve kullanım ─────────────────────────────────

class MoodBody(BaseModel):
    mood: str = Field(min_length=3, max_length=16)


@router.get("/api/health/wellbeing")
def health_wellbeing(ctx: dict = Depends(_ctx)) -> dict:
    """Mood + günlük kullanım + mola/limit ayarları tek yanıtta."""
    row = database.get_user_settings(ctx["owner_id"])
    usage = section_g.usage_today(ctx["owner_id"])
    return {
        "mood": section_g.get_mood(ctx["owner_id"]),
        "moods": list(section_g.MOODS),
        "used_seconds": usage.get("used_seconds", 0),
        "daily_limit_minutes": int(row.get("daily_limit_minutes") or 0),
        "focus_mode": bool(row.get("focus_mode", 0)),
        "break_reminder_minutes": int(row.get("break_reminder_minutes") or 0),
        "privacy_mode": bool(row.get("privacy_mode", 0)),
    }


@router.put("/api/health/mood")
def health_mood(body: MoodBody, ctx: dict = Depends(_ctx)) -> dict:
    if body.mood not in section_g.MOODS:
        raise HTTPException(status_code=422, detail="Geçersiz ruh hâli.")
    section_g.set_mood(ctx["owner_id"], body.mood)
    # user_settings.mood'a da yaz: chat prompt'u oradan okur.
    database.update_user_settings(ctx["owner_id"], {"mood": body.mood,
                                                    "mood_updated_at": section_g._now()})
    section_g.audit(ctx["owner_id"], "health.mood", detail=body.mood)
    return {"mood": body.mood}