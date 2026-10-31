"""Web ATLAS uçları (Özellik 17) — ChatGPT Canvas benzeri görev motoru.

Web ATLAS ≠ Masaüstü ATLAS: tarayıcıdan çalıştığı için klavye/fare kontrolü
YAPMAZ; desteklenen görev tipleri: metin işleme, kod üretme/açıklama, web
araştırması (Özellik 1 web_search), bilgi tabanı sorgusu (Özellik 8 RAG).
Desteklenmeyenler (GUI otomasyonu vb.) için açık Türkçe mesaj döner.

Kuyruk: asyncio.Queue; eş zamanlı görev limiti JARVIS_ATLAS_MAX_CONCURRENT
(varsayılan 3). Görevler RAM'de yaşar (app.state.atlas_tasks).
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .. import security

logger = logging.getLogger("jarvis.api.atlas")

router = APIRouter()

# GUI/otomasyon görev tipleri web'de DESTEKLENMEZ (mega prompt 17.6).
_UNSUPPORTED_KEYWORDS = (
    "ekranı tıkla", "fare", "klavye", "uygulama aç", "program aç",
    "dosya sil", "yorum yaz", "automation", "gui",
)


def _classify(instruction: str) -> str:
    text = (instruction or "").lower()
    for kw in _UNSUPPORTED_KEYWORDS:
        if kw in text:
            return "unsupported"
    if any(k in text for k in ("araştır", "webde ara", "güncel", "haber", "research")):
        return "research"
    if any(k in text for k in ("kod", "python", "javascript", "fonksiyon", "debug")):
        return "code"
    if any(k in text for k in ("belge", "notlarım", "bilgi tabanım", "dosyalarımda")):
        return "knowledge"
    if any(k in text for k in ("dönüştür", "pdf", "convert")):
        return "convert"
    return "text"


def _max_concurrent() -> int:
    from .. import config

    try:
        return max(1, min(10, int(config.env("JARVIS_ATLAS_MAX_CONCURRENT", "3"))))
    except (TypeError, ValueError):
        return 3


def _tasks_of(app: Any) -> dict[str, dict[str, Any]]:
    if not hasattr(app.state, "atlas_tasks"):
        app.state.atlas_tasks = {}
    return app.state.atlas_tasks


def _subscribers_of(app: Any) -> dict[str, list]:
    if not hasattr(app.state, "atlas_subscribers"):
        app.state.atlas_subscribers = {}
    return app.state.atlas_subscribers


class TaskBody(BaseModel):
    instruction: str = Field(min_length=2, max_length=4000)


@router.post("/api/atlas/task")
async def create_task(payload: TaskBody, request: Request) -> dict:
    """Yeni ATLAS görevi oluşturur ve kuyruğa ekler."""
    if security.is_guest(request):
        raise HTTPException(status_code=403, detail="Misafir ATLAS kullanamaz.")
    kind = _classify(payload.instruction)
    if kind == "unsupported":
        raise HTTPException(
            status_code=422,
            detail=(
                "Bu görev masaüstü uygulamasında kullanılabilir — web ATLAS "
                "klavye/fare kontrolü yapamaz."
            ),
        )
    owner = security.request_owner(request)
    task_id = uuid.uuid4().hex[:12]
    task = {
        "task_id": task_id,
        "owner": owner,
        "instruction": payload.instruction.strip(),
        "type": kind,
        "status": "queued",  # queued | running | done | error
        "steps": [],
        "result": "",
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    _tasks_of(request.app)[task_id] = task
    queue: asyncio.Queue = getattr(request.app.state, "atlas_queue", None)
    if queue is None:
        queue = asyncio.Queue()
        request.app.state.atlas_queue = queue
    await queue.put(task_id)
    return {"task_id": task_id, "type": kind, "status": "queued"}


@router.get("/api/atlas/task/{task_id}")
def get_task(task_id: str, request: Request) -> dict:
    task = _tasks_of(request.app).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    return task


@router.delete("/api/atlas/task/{task_id}")
def cancel_task(task_id: str, request: Request) -> dict:
    task = _tasks_of(request.app).pop(task_id, None)
    if task is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    return {"ok": True, "cancelled": task_id}


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "instruction": task["instruction"],
        "type": task["type"],
        "status": task["status"],
        "steps": task["steps"],
        "result": task["result"],
    }


async def _broadcast(app: Any, task_id: str, event: dict[str, Any]) -> None:
    """Görev abonelerine canlı adım güncellemesi (ws_atlas üzerinden)."""
    for ws in list(_subscribers_of(app).get(task_id, [])):
        try:
            await ws.send_json(event)
        except Exception:  # noqa: BLE001 — kopan abone sessizce düşer
            pass


@router.websocket("/ws/atlas/{task_id}")
async def ws_atlas(websocket: WebSocket, task_id: str) -> None:
    """Canlı görev güncellemeleri (adım durumu + sonuç)."""
    await websocket.accept()
    app = websocket.app
    _subscribers_of(app).setdefault(task_id, []).append(websocket)
    try:
        task = _tasks_of(app).get(task_id)
        if task is not None:
            await websocket.send_json({"type": "snapshot", **_public_task(task)})
        while True:
            await websocket.receive_text()  # keepalive
    except WebSocketDisconnect:
        pass
    finally:
        subs = _subscribers_of(app).get(task_id, [])
        if websocket in subs:
            subs.remove(websocket)


async def _execute(app: Any, task: dict[str, Any]) -> None:
    """Görev tipine göre adımları yürütür; her adımı canlı yayınlar."""
    from ..llm import websearch

    instruction = task["instruction"]
    owner = task["owner"]
    steps: list[dict[str, Any]] = []
    provider = app.state.llm

    async def _step(desc: str, coro) -> Any:
        entry = {"index": len(steps), "description": desc, "status": "running"}
        steps.append(entry)
        await _broadcast(app, task["task_id"], {"type": "step", **entry})
        try:
            result = await coro
            entry["status"] = "done"
            await _broadcast(app, task["task_id"], {"type": "step", **entry})
            return result
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "error"
            entry["detail"] = str(exc)[:200]
            await _broadcast(app, task["task_id"], {"type": "step", **entry})
            raise

    kind = task["type"]
    context = ""
    if kind == "research":
        search = await _step(
            "Web'de araştırma yapılıyor",
            asyncio.to_thread(websearch.web_search, instruction),
        )
        results = (search or {}).get("results") or []
        if results:
            lines = [f"- {r.get('title')}: {r.get('snippet')}" for r in results[:3]]
            context = "\nWeb kaynakları:\n" + "\n".join(lines)
    elif kind == "knowledge":
        from ..knowledge import retriever as rag

        hits = await _step(
            "Bilgi tabanı sorgulanıyor",
            asyncio.to_thread(rag.retrieve, owner, instruction),
        )
        if hits:
            context = "\nBilgi tabanı bulguları:\n" + "\n".join(
                f"- [{h.get('document_name')}] {h['content'][:300]}" for h in hits[:5]
            )

    final = await _step(
        "ATLAS görevi yürütülüyor",
        provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Sen ATLAS'sın: görevleri adım adım yürüten yardımcı. "
                        "Yanıtını adımlar ve net sonuç olarak Türkçe yaz."
                    ),
                },
                {"role": "user", "content": instruction + context},
            ]
        ),
    )
    task["steps"] = steps
    task["result"] = (final.content or "").strip()[:8000]


async def worker_loop(app: Any) -> None:
    """Kuyruğu tüketir; eş zamanlı görev limiti ile çalıştırır (uygulama ömrü)."""
    queue: asyncio.Queue = asyncio.Queue()
    app.state.atlas_queue = queue
    semaphore = asyncio.Semaphore(_max_concurrent())
    while True:
        task_id = await queue.get()
        task = _tasks_of(app).get(task_id)
        if task is None:
            continue
        async def _run(t=task) -> None:
            async with semaphore:
                t["status"] = "running"
                await _broadcast(app, t["task_id"], {"type": "status", "status": "running"})
                try:
                    await _execute(app, t)
                    t["status"] = "done"
                    await _broadcast(app, t["task_id"], {"type": "status", "status": "done"})
                except Exception as exc:  # noqa: BLE001
                    logger.exception("ATLAS görevi başarısız")
                    t["status"] = "error"
                    t["result"] = f"Görev hatası: {exc}"
                    await _broadcast(app, t["task_id"], {"type": "status", "status": "error"})
        asyncio.create_task(_run())

