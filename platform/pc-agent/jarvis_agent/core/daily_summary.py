"""Günlük özet — üretim, zamanlama ve dağıtım (Özellik 11).

Varsayım (kod başında açık): APScheduler yerine hafif bir asyncio
zamanlayıcı kullanılır — her gece saat 21:00'de (yerel saat,
``JARVIS_DAILY_SUMMARY_HOUR`` ile değiştirilebilir) özet üretilir.
Ek bağımlılık gerektirmez; testlerde ``scheduler_loop`` çağrılmaz.

Dağıtım kanalları (.env):
- JARVIS_DAILY_SUMMARY_WHATSAPP=1 → mevcut CallMeBot entegrasyonu
- sohbet bildirimi (WS) varsayılan açıktır.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Optional

from .. import config
from ..store import database
from ..store import v11

logger = logging.getLogger("jarvis.core.daily_summary")

OWNER_SCOPE_LIMIT = 50  # tek turda özetlenecek maksimum sahip (kişisel kullanım)


def _summary_hour() -> int:
    try:
        return max(0, min(23, int(config.env("JARVIS_DAILY_SUMMARY_HOUR", "21"))))
    except (TypeError, ValueError):
        return 21


def _disabled() -> bool:
    return config.env("JARVIS_DAILY_SUMMARY_DISABLED", "").strip() == "1"


async def scheduler_loop(app: Any) -> None:
    """Her gece 21:00'de (yerel) özet üretir; uygulamayla birlikte durur."""
    if _disabled():
        logger.info("Günlük özet zamanlayıcısı kapalı (JARVIS_DAILY_SUMMARY_DISABLED=1)")
        return
    try:
        while True:
            now = datetime.datetime.now()
            target = now.replace(hour=_summary_hour(), minute=0, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            logger.info(
                "Günlük özet zamanlayıcısı: sonraki çalışma %s (%.0f sn sonra)",
                target.isoformat(timespec="minutes"),
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            await run_daily_cycle(app)
    except asyncio.CancelledError:
        return
    except Exception:  # noqa: BLE001 — zamanlayıcı asla uygulamayı düşürmesin
        logger.exception("Günlük özet zamanlayıcısı beklenmedik hata verdi")


def _active_owners(limit: int = OWNER_SCOPE_LIMIT) -> list[str]:
    """Bugün sohbet etmiş sahipleri döndürür (misafirler hariç)."""
    today = datetime.date.today().isoformat()
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT owner_id FROM messages WHERE created_at >= ? "
            "AND owner_id NOT LIKE 'guest:%' LIMIT ?",
            (today, limit),
        ).fetchall()
    return [r["owner_id"] for r in rows]


def _collect_stats(owner_id: str) -> dict[str, Any]:
    """Günün verisi: sohbet sayısı, konular, tamamlanan görevler, alışkanlıklar."""
    today = datetime.date.today().isoformat()
    stats: dict[str, Any] = {"date": today, "chat_count": 0, "topics": []}
    try:
        with database.closing(database.connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE owner_id = ? AND "
                "created_at >= ? AND role = 'user'",
                (owner_id, today),
            ).fetchone()
            stats["chat_count"] = int(row["n"]) if row else 0
            topics = conn.execute(
                "SELECT content FROM messages WHERE owner_id = ? AND "
                "created_at >= ? AND role = 'user' ORDER BY id DESC LIMIT 8",
                (owner_id, today),
            ).fetchall()
            stats["topics"] = [t["content"][:60] for t in topics]
    except Exception:  # noqa: BLE001
        pass
    stats["tasks_done"] = v11.tasks_done_today(owner_id)
    habits = v11.list_habits(owner_id)
    stats["habits_total"] = len(habits)
    stats["habits_done"] = sum(1 for h in habits if h.get("today_done"))
    return stats


def _fallback_summary(stats: dict[str, Any]) -> str:
    """LLM yoksa kural tabanlı Türkçe özet."""
    lines = [
        f"Günlük Özet ({stats['date']}):",
        f"- Bugün bana {stats.get('chat_count', 0)} mesaj yazdın.",
    ]
    if stats.get("topics"):
        lines.append("- Öne çıkan konular: " + ", ".join(stats["topics"][:4]))
    lines.append(f"- Tamamlanan görev sayısı: {stats.get('tasks_done', 0)}")
    lines.append(
        f"- Alışkanlıklar: {stats.get('habits_done', 0)}/{stats.get('habits_total', 0)} tamamlandı."
    )
    lines.append("- Yarın için: en verimli saatlerinde yoğun görevleri planla.")
    return "\n".join(lines)


async def _llm_summary(app: Any, stats: dict[str, Any]) -> Optional[str]:
    """LLM ile 150-200 kelimelik Türkçe özet; hata halinde None."""
    provider = getattr(app.state, "llm", None)
    if provider is None:
        return None
    prompt = (
        "Aşağıdaki verilerle kullanıcının GÜNLÜK özetini 150-200 kelime "
        "arasında, samimi ama profesyonel Türkçe yaz. Madde işaretleri "
        f"kullanabilirsin. Veriler: {stats}"
    )
    try:
        result = await provider.chat([{"role": "user", "content": prompt}])
        content = (result.content or "").strip()
        return content or None
    except Exception as exc:  # noqa: BLE001 — sağlayıcı hatası özeti bloklamaz
        logger.warning("Günlük özet LLM üretimi başarısız: %s", exc)
        return None


async def _distribute(app: Any, owner_id: str, content: str, channels: str) -> list[str]:
    """Özeti istenen kanallara gönderir; başarılı kanal listesi döner."""
    sent: list[str] = []
    channel_list = [c.strip().lower() for c in (channels or "chat").split(",") if c.strip()]
    if "whatsapp" in channel_list and config.env("JARVIS_DAILY_SUMMARY_WHATSAPP") == "1":
        try:
            from ..integrations import whatsapp

            result = await asyncio.to_thread(whatsapp.send, content)
            if result:
                sent.append("whatsapp")
        except Exception as exc:  # noqa: BLE001
            logger.warning("WhatsApp özet gönderimi başarısız: %s", exc)
    if "chat" in channel_list or not sent:
        try:
            from ..api import ws as ws_module

            await ws_module.manager.publish_to_owner(
                owner_id, {"type": "daily.summary", "content": content}
            )
            sent.append("chat")
        except Exception as exc:  # noqa: BLE001
            logger.warning("WS özet bildirimi başarısız: %s", exc)
    return sent


async def generate_for_owner(app: Any, owner_id: str, channels: str = "chat") -> dict:
    """Tek sahip için özet üretir + kaydeder + dağıtır (endpoint ve zamanlayıcı)."""
    if database.is_guest(owner_id):
        return {"ok": False, "detail": "misafir oturum"}
    stats = _collect_stats(owner_id)
    content = await _llm_summary(app, stats) or _fallback_summary(stats)
    date = stats["date"]
    saved = v11.save_summary(owner_id, date, content, channels)
    sent = await _distribute(app, owner_id, content, channels)
    return {"ok": True, "date": date, "summary": content, "sent": sent, "saved": saved}


async def run_daily_cycle(app: Any) -> int:
    """Aktif sahipler için özet döngüsü; üretilen özet sayısını döndürür."""
    owners = _active_owners()
    produced = 0
    for owner_id in owners:
        try:
            channels = "chat"
            if config.env("JARVIS_DAILY_SUMMARY_WHATSAPP") == "1":
                channels = "chat,whatsapp"
            result = await generate_for_owner(app, owner_id, channels)
            if result.get("ok"):
                produced += 1
        except Exception:  # noqa: BLE001
            logger.exception("Günlük özet üretilemedi: %s", owner_id)
    logger.info("Günlük özet döngüsü tamamlandı: %s özet", produced)
    return produced

