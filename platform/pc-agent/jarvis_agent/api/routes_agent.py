"""Bölüm E uçları — Memory Bank (18), özel komutlar (22), ekran analizi/otomasyon (9),
üretkenlik: notlar ve yapılacaklar (23).

Kurallar:
- Tüm uçlar owner etiketiyle çalışır; misafir (madde 6) okuma dışındaki
  işlemlerde 403 alır (guards.require_not_guest).
- Ekran otomasyonu yalnızca JARVIS_GUI_AUTOMATION=1 iken çalışır; aksi halde
  409 döner. Uygulama açma beyaz listeyle sınırlıdır (core.screen).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..core import screen
from ..store import database
from .guards import require_not_guest

router = APIRouter()


def _owner(request: Request) -> str:
    return security.request_owner(request)


# ── Memory Bank (madde 18) ───────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


@router.get("/api/memory")
def list_memory(request: Request, query: str = "", limit: int = 20) -> dict:
    return {
        "memories": database.list_memories(_owner(request), limit=limit, query=query)
    }


@router.post("/api/memory")
def create_memory(payload: MemoryCreate, request: Request) -> dict:
    require_not_guest(request)  # madde 6: misafir kalıcı bilgi yazamaz
    mid = database.add_memory(_owner(request), payload.content)
    if mid is None:
        raise HTTPException(status_code=422, detail="Bilgi kaydedilemedi.")
    return {"saved": True, "id": mid}


@router.delete("/api/memory/{memory_id}")
def remove_memory(memory_id: int, request: Request) -> dict:
    require_not_guest(request)
    if not database.delete_memory(_owner(request), memory_id):
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    return {"deleted": True}


# ── Özel komutlar (madde 22) ─────────────────────────────────────────────────

ALLOWED_COMMAND_ACTIONS = ("reply_text", "open_app")


class CommandCreate(BaseModel):
    phrase: str = Field(min_length=2, max_length=60)
    action_type: str = Field(min_length=3, max_length=20)
    action_payload: str = Field(default="", max_length=500)


@router.get("/api/commands")
def list_commands(request: Request) -> dict:
    return {"commands": database.list_custom_commands(_owner(request))}


@router.post("/api/commands")
def create_command(payload: CommandCreate, request: Request) -> dict:
    require_not_guest(request)
    if payload.action_type not in ALLOWED_COMMAND_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail="action_type 'reply_text' veya 'open_app' olmalı.",
        )
    if payload.action_type == "open_app":
        if not payload.action_payload.strip():
            raise HTTPException(status_code=422, detail="open_app için uygulama adı gerekli.")
        if payload.action_payload.strip().lower() not in screen.APP_COMMANDS:
            raise HTTPException(
                status_code=422,
                detail=f"Uygulama beyaz listede yok. İzinliler: {', '.join(screen.list_apps())}",
            )
    cid = database.add_custom_command(
        _owner(request), payload.phrase, payload.action_type, payload.action_payload
    )
    if cid is None:
        raise HTTPException(status_code=422, detail="Komut kaydedilemedi (yinelenen ifade?).")
    return {"saved": True, "id": cid}


@router.delete("/api/commands/{command_id}")
def remove_command(command_id: int, request: Request) -> dict:
    require_not_guest(request)
    if not database.delete_custom_command(_owner(request), command_id):
        raise HTTPException(status_code=404, detail="Komut bulunamadı.")
    return {"deleted": True}


# ── Üretkenlik: notlar ve yapılacaklar (madde 23) ────────────────────────────

class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=4000)


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TodoUpdate(BaseModel):
    done: bool


@router.get("/api/notes")
def notes_list(request: Request, query: str = "", limit: int = 50) -> dict:
    return {"notes": database.list_notes(_owner(request), limit=limit, query=query)}


@router.post("/api/notes")
def notes_create(payload: NoteCreate, request: Request) -> dict:
    require_not_guest(request)  # madde 6/23: misafir kalıcı not yazamaz
    nid = database.add_note(_owner(request), payload.title, payload.content)
    if nid is None:
        raise HTTPException(status_code=422, detail="Not kaydedilemedi (başlık gerekli).")
    return {"saved": True, "id": nid}


@router.delete("/api/notes/{note_id}")
def notes_delete(note_id: int, request: Request) -> dict:
    require_not_guest(request)
    if not database.delete_note(_owner(request), note_id):
        raise HTTPException(status_code=404, detail="Not bulunamadı.")
    return {"deleted": True}


@router.get("/api/notes/export")
def notes_export(request: Request):
    """Madde 20: Collaborative Notes MVP — notları Markdown olarak indirir.

    Notion/OneNote API'leri bu ortamda OAuth olmadan erişilemediği için
    standart dosya dışa aktarma sunulur (raporda KISMEN olarak işaretlenir).
    """
    notes = database.list_notes(_owner(request), limit=500)
    lines = ["# JARVIS Notları", ""]
    for n in notes:
        lines.append(f"## {n.get('title', '')}")
        lines.append("")
        lines.append(str(n.get("content", "")))
        lines.append("")
    from fastapi.responses import Response  # yerel import: sadece bu uç kullanır

    return Response(
        content="\n".join(lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jarvis-notes.md"'},
    )


@router.get("/api/todos")
def todos_list(request: Request, limit: int = 100) -> dict:
    return {"todos": database.list_todos(_owner(request), limit=limit)}


@router.post("/api/todos")
def todos_create(payload: TodoCreate, request: Request) -> dict:
    require_not_guest(request)
    tid = database.add_todo(_owner(request), payload.title)
    if tid is None:
        raise HTTPException(status_code=422, detail="Yapılacak kaydedilemedi.")
    return {"saved": True, "id": tid}


@router.put("/api/todos/{todo_id}")
def todos_update(todo_id: int, payload: TodoUpdate, request: Request) -> dict:
    require_not_guest(request)
    if not database.set_todo_done(_owner(request), todo_id, payload.done):
        raise HTTPException(status_code=404, detail="Yapılacak bulunamadı.")
    return {"updated": True}


@router.delete("/api/todos/{todo_id}")
def todos_delete(todo_id: int, request: Request) -> dict:
    require_not_guest(request)
    if not database.delete_todo(_owner(request), todo_id):
        raise HTTPException(status_code=404, detail="Yapılacak bulunamadı.")
    return {"deleted": True}


# ── Ekran analizi ve sınırlı otomasyon (madde 9) ─────────────────────────────

class ScreenAnalyzeBody(BaseModel):
    question: str = Field(default="", max_length=300)


class ScreenActionBody(BaseModel):
    action: str = Field(min_length=3, max_length=10)  # scroll | type | open
    delta: int | None = Field(default=None, ge=-5000, le=5000)
    text: str | None = Field(default=None, max_length=200)
    app: str | None = Field(default=None, max_length=20)


@router.get("/api/screen/apps")
def screen_apps() -> dict:
    return {"apps": screen.list_apps()}


@router.post("/api/screen/analyze")
def screen_analyze(payload: ScreenAnalyzeBody, request: Request) -> dict:
    require_not_guest(request)  # ekran bilgisi cihaz verisidir
    result = screen.analyze_screen(payload.question.strip() or None)
    return result


@router.post("/api/screen/action")
def screen_action(payload: ScreenActionBody, request: Request) -> dict:
    require_not_guest(request)
    try:
        if payload.action == "scroll":
            return screen.scroll(payload.delta if payload.delta is not None else -600)
        if payload.action == "type":
            if not payload.text:
                raise HTTPException(status_code=422, detail="type için text gerekli.")
            return screen.type_text(payload.text)
        if payload.action == "open":
            if not payload.app:
                raise HTTPException(status_code=422, detail="open için app gerekli.")
            return screen.open_app(payload.app)
    except RuntimeError as exc:
        # automation_disabled / pyautogui_missing / vision_* → 409
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise HTTPException(
        status_code=422, detail="action 'scroll', 'type' veya 'open' olmalı."
    )
