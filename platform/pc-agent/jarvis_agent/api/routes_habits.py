"""Alışkanlık & üretkenlik uçları (Özellik 10)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..store import v11

router = APIRouter()


class HabitBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    frequency: str = Field(default="daily", max_length=12)
    color: str = Field(default="#a78bfa", max_length=16)
    icon: str = Field(default="check", max_length=16)


class HabitLogBody(BaseModel):
    completed: bool = True
    note: str = Field(default="", max_length=200)


class SessionBody(BaseModel):
    focus_minutes: int = Field(default=0, ge=0, le=1440)
    mood: int = Field(default=3, ge=1, le=5)
    notes: str = Field(default="", max_length=500)


@router.get("/api/habits")
def get_habits(request: Request) -> dict:
    return {"habits": v11.list_habits(security.request_owner(request))}


@router.post("/api/habits")
def post_habit(payload: HabitBody, request: Request) -> dict:
    habit = v11.create_habit(
        security.request_owner(request),
        payload.name,
        payload.frequency,
        payload.color,
        payload.icon,
    )
    if habit is None:
        raise HTTPException(status_code=422, detail="Alışkanlık oluşturulamadı.")
    return {"habit": habit}


@router.delete("/api/habits/{habit_id}")
def remove_habit(habit_id: int, request: Request) -> dict:
    if not v11.delete_habit(security.request_owner(request), habit_id):
        raise HTTPException(status_code=404, detail="Alışkanlık bulunamadı.")
    return {"ok": True}


@router.post("/api/habits/{habit_id}/log")
def post_habit_log(habit_id: int, payload: HabitLogBody, request: Request) -> dict:
    ok = v11.log_habit(
        security.request_owner(request), habit_id, payload.completed, payload.note
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Alışkanlık bulunamadı.")
    return {"ok": True}


@router.get("/api/habits/stats")
def get_habit_stats(request: Request) -> dict:
    return v11.habit_stats(security.request_owner(request))


@router.post("/api/productivity/session")
def post_session(payload: SessionBody, request: Request) -> dict:
    session = v11.add_productivity_session(
        security.request_owner(request),
        payload.focus_minutes,
        payload.mood,
        payload.notes,
    )
    if session is None:
        raise HTTPException(status_code=422, detail="Oturum kaydedilemedi.")
    return {"session": session}


@router.get("/api/productivity/insights")
async def get_insights(request: Request, days: int = 7) -> dict:
    """Haftalık veriden AI içgörü üretir (LLM yoksa kural tabanlı özet)."""
    owner = security.request_owner(request)
    data = v11.productivity_insights_data(owner, days=max(1, min(30, days)))
    stats = v11.habit_stats(owner)
    base = {
        "data": data,
        "habits": stats,
        "insight": "",
        "source": "rule",
    }
    if not data:
        base["insight"] = (
            "Henüz yeterli üretkenlik verisi yok; birkaç odak oturumu ekleyin."
        )
        return base
    # Kural tabanlı temel içgörü (her zaman çalışır).
    low_days = [d["date"] for d in data if d["focus_minutes"] < 30]
    best = max(data, key=lambda d: d["focus_minutes"])
    parts = [
        f"En verimli günün {best['date']} ({best['focus_minutes']} dk odak).",
    ]
    if low_days:
        parts.append(
            f"{len(low_days)} günde odak 30 dk altında; yoğun görevleri "
            "verimli saatlere kaydırmayı dene."
        )
    if stats.get("best_streak"):
        parts.append(f"En uzun alışkanlık serin: {stats['best_streak']} gün.")
    base["insight"] = " ".join(parts)
    # LLM varsa daha zengin içgörü (hata sohbeti bozmaz).
    try:
        provider = request.app.state.llm
        prompt = (
            "Aşağıdaki haftalık üretkenlik verisine dayanarak TEK cümlelik "
            "Türkçe bir öneri yaz (veri: "
            f"{base['data']}, alışkanlık istatistikleri: {stats})."
        )
        result = await provider.chat([{"role": "user", "content": prompt}])
        if result.content and result.content.strip():
            base["insight"] = result.content.strip()[:500]
            base["source"] = "llm"
    except Exception:  # noqa: BLE001
        pass
    return base
