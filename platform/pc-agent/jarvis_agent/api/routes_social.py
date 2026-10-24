"""Bölüm F uçları (madde 19/20/21/24): paylaşılan oturumlar, makrolar,
sesli notlar, dosya etiket/arama, Cloud Backup, gamification ve analitik.

Kurallar:
- Tüm uçlar owner etiketiyle çalışır (security.request_owner).
- Misafir (madde 6) kalıcı kayıt gerektiren tüm uçlarda 403 alır.
- XP yalnızca sunucu içinde yazılır (istemciye XP ucu yoktur, madde 21).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from .. import security
from ..integrations import files as files_mod
from ..store import section_f
from . import guards
from . import ws  # noqa: F401  (rota modülleri tek noktadan)
from .ws import manager as _ws_manager

log = logging.getLogger("jarvis.social")

router = APIRouter(prefix="/api", tags=["social"])


def _require_auth(request: Request) -> dict:
    """Owner çözümler + misafir isteğini 403 ile reddeder (madde 6)."""
    guards.require_not_guest(request)
    return {"owner_id": security.request_owner(request), "request": request}


def _ws_notify(owner_id: str, payload: dict) -> None:
    """Bağlı WS istemcilerine olay bildirimi (en iyi çaba, akışı bozmaz)."""
    try:
        _ws_manager.publish_to_owner(owner_id, payload)
    except Exception as exc:  # kopuk soket vb. — logla, devam et
        log.warning("WS bildirimi başarısız: %s", exc)


class SharedSessionCreate(BaseModel):
    title: str = ""


class SharedJoinBody(BaseModel):
    display_name: str = "guest"


class SharedMessageBody(BaseModel):
    role: str = "user"
    content: str
    display_name: str = "guest"


class MacroBody(BaseModel):
    name: str
    steps: list[dict] = []


@router.post("/shared/sessions")
def create_shared_session(body: SharedSessionCreate, ctx: dict = Depends(_require_auth)):
    """Yeni paylaşımlı oturum aç (6 karakterli kod döner)."""
    code = section_f.create_shared_session(ctx["owner_id"], body.title)
    return {"code": code}


@router.get("/shared/sessions/{code}")
def shared_session_detail(code: str, ctx: dict = Depends(_require_auth)):
    """Oturum bilgisi: SADECE üyeler görebilir (yetkilendirme testi burada)."""
    info = section_f.shared_session_info(code)
    if info is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if ctx["owner_id"] not in {m["owner_id"] for m in info["members"]}:
        raise HTTPException(status_code=403, detail="Not a member")
    return info


@router.post("/shared/members/{code}")
def join_session(code: str, body: SharedJoinBody, ctx: dict = Depends(_require_auth)):
    """Kodla oturuma katıl (katılan, kendi owner_id'siyle üye olur)."""
    ok = section_f.join_shared_session(code, ctx["owner_id"], body.display_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"joined": True}


def _ensure_member(code: str, owner_id: str) -> dict:
    info = section_f.shared_session_info(code)
    if info is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if owner_id not in {m["owner_id"] for m in info["members"]}:
        raise HTTPException(status_code=403, detail="Not a member")
    return info


@router.get("/shared/sessions/{code}/messages")
def shared_messages(code: str, since_id: int = 0, ctx: dict = Depends(_require_auth)):
    """Yeni mesajlar (uzun yoklama; üye olmayan 403)."""
    _ensure_member(code, ctx["owner_id"])
    return {"messages": section_f.list_shared_messages(code, since_id)}


@router.post("/shared/sessions/{code}/messages")
def post_shared_message(code: str, body: SharedMessageBody, ctx: dict = Depends(_require_auth)):
    """Gruba mesaj yaz (user/assistant) — canlı akış WS ile bildirilir."""
    _ensure_member(code, ctx["owner_id"])
    mid = section_f.add_shared_message(
        code, ctx["owner_id"], body.display_name, body.role, body.content
    )
    return {"id": mid}


@router.delete("/shared/sessions/{code}")
def delete_shared_session(code: str, ctx: dict = Depends(_require_auth)):
    """Sadece oturumu açan host silebilir (üye denemesi -> 403)."""
    ok = section_f.delete_shared_session(code, ctx["owner_id"])
    if not ok:
        raise HTTPException(status_code=403, detail="Only the host can delete this session")
    return {"deleted": True}


# ── Makrolar (madde 20) ──────────────────────────────────────────────────────

@router.get("/macros")
def get_macros(ctx: dict = Depends(_require_auth)):
    return {"macros": section_f.list_macros(ctx["owner_id"])}


@router.post("/macros")
def create_macro(body: MacroBody, ctx: dict = Depends(_require_auth)):
    """Yeni kısayol/makro kaydet; ad yinelenirse 409 döner."""
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Macro name required")
    mid = section_f.add_macro(ctx["owner_id"], body.name.strip(), body.steps)
    if mid is None:
        raise HTTPException(status_code=409, detail="Macro name already exists")
    return {"id": mid}


@router.delete("/macros/{macro_id}")
def remove_macro(macro_id: int, ctx: dict = Depends(_require_auth)):
    if not section_f.delete_macro(ctx["owner_id"], macro_id):
        raise HTTPException(status_code=404, detail="Macro not found")
    return {"deleted": True}


# ── Sesli notlar (madde 19) ──────────────────────────────────────────────────

class VoiceNoteBody(BaseModel):
    text: str


@router.get("/voice-notes")
def get_voice_notes(q: str = "", ctx: dict = Depends(_require_auth)):
    return {"notes": section_f.list_voice_notes(ctx["owner_id"], q=q)}


@router.post("/voice-notes")
def create_voice_note(body: VoiceNoteBody, ctx: dict = Depends(_require_auth)):
    """Sesli notun STT ile çevrilmış metni kaydedilir; XP otomatik verilir."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Note text required")
    mid = section_f.add_voice_note(ctx["owner_id"], text)
    return {"id": mid}


@router.delete("/voice-notes/{note_id}")
def remove_voice_note(note_id: int, ctx: dict = Depends(_require_auth)):
    if not section_f.delete_voice_note(ctx["owner_id"], note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": True}


# ── Dosya etiketleri + etiketli arama (madde 19/24) ─────────────────────────

@router.get("/files/tags")
def get_file_tags(ctx: dict = Depends(_require_auth)):
    return {"tags": section_f.file_tags_map(ctx["owner_id"])}


@router.get("/files/search")
def files_search(q: str = "", tag: str = "", ctx: dict = Depends(_require_auth)):
    """Madde 19: dosya arama — ad + owner etiketleri.

    Yalnızca owner'ın etiketlediği dosyalar listelenir; etiketi olmayan
    bir istemci kendi dosyalarını göremez (izolasyon testinin beklentisi).
    """
    tags_map = section_f.file_tags_map(ctx["owner_id"])
    try:
        on_disk = {item["name"] for item in files_mod.list_files().get("files", [])}
    except (OSError, FileNotFoundError):
        on_disk = set()  # paylaşım klasörü yoksa yalnızca etiket eşleşmesine bak
    wanted = section_f.norm_tag(tag)
    results: list[dict] = []
    for name, tags in tags_map.items():
        if on_disk and name not in on_disk:
            continue  # diskten silinmiş dosya etiketi sonuçta yer almaz
        if q and q.lower() not in name.lower():
            continue
        if wanted and wanted not in tags:
            continue
        results.append({"name": name, "tags": tags})
    return {"results": results}


# ── Etkinlik akışı (madde 20: Activity Feed, son 7 gün) ─────────────────────

@router.get("/activity")
def activity_feed(days: int = Query(7, le=30), ctx: dict = Depends(_require_auth)):
    return {"events": section_f.recent_activity(ctx["owner_id"], days=days)}

# ── Gamification (madde 21) — XP yalnızca sunucuda hesaplanır ────────────────

@router.get("/gamify")
def gamify_status(ctx: dict = Depends(_require_auth)):
    status = section_f.gamify_status(ctx["owner_id"])
    status["leaderboard"] = section_f.leaderboard()
    return status


@router.post("/gamify")
def gamify_forbidden():
    """XP manipülasyonu engeli: istemciden XP yazma ucu YOKTUR."""
    raise HTTPException(status_code=405, detail="XP is server-side only")


# ── Analitik (madde 24) ──────────────────────────────────────────────────────

@router.get("/analytics/summary")
def analytics(days: int = Query(14, le=90), ctx: dict = Depends(_require_auth)):
    return section_f.analytics_summary(ctx["owner_id"], days=days)


# ── Not (tek kaynak ilkesi) ──────────────────────────────────────────────────
# Analitik dışa aktarma (/api/analytics/export) ve Cloud Backup
# (/api/backup/export|import) uçları routes_productivity.py içinde tek
# noktadan sunulur; burada kopya rota açılmaz (çift kayıt karışıklık yaratır).