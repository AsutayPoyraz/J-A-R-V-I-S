"""LLM araç (function calling) tanımları ve yürütme.

Güvenlik: Burada YALNIZCA okuma amaçlı araçlar tanımlıdır. Shell komutu
çalıştıran, dosya silen vb. yıkıcı araçlar kasıtlı olarak YOKTUR
(gereksinim 5.3). Faz 5'te dosya transferi eklendiğinde de kullanıcı onayı
zorunlu tutulacaktır.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Any, Optional

from ..core import weather as weather_module

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": (
                "Bilgisayarın canlı sistem istatistiklerini getirir: CPU yüzdesi, "
                "çekirdek sayısı, RAM ve disk kullanımı, çalışma süresi, sistem yükü."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Şu anki yerel tarih ve saati getirir.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Şehir için güncel hava durumunu getirir. Şehir verilmezse "
                "ayarlanmış varsayılan şehir kullanılır. Örnek: 'Istanbul,TR'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Hava durumu sorgulanacak şehir (örn. 'Istanbul,TR').",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": (
                "Kullanıcı için hatırlatıcı/alarm oluşturur. due_at daima yerel ISO "
                "biçimindedir: YYYY-MM-DDTHH:MM:SS. 'Yarın sabah 9' gibi ifadeleri "
                "get_current_time aracıyla öğrendiğin şimdiki zamandan hesapla."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Hatırlatmanın içeriği (örn. 'ilaç iç')."},
                    "due_at": {"type": "string", "description": "Yerel ISO tarih-saat: YYYY-MM-DDTHH:MM:SS"}
                },
                "required": ["title", "due_at"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Bekleyen ve çalan hatırlatıcıları listeler.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ack_active_alarms",
            "description": (
                "Çalan (aktif) alarmları susturur. Kullanıcı 'tamam', 'kapat', 'dur' "
                "gibi bir onay verdiğinde MUTLAKA bu aracı çağır."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_reminder",
            "description": "Bir hatırlatıcıyı kalıcı olarak siler.",
            "parameters": {
                "type": "object",
                "properties": {"reminder_id": {"type": "integer"}},
                "required": ["reminder_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Kullanıcı kalıcı olarak hatırlanmasını istediği bir bilgiyi "
                "(madde 18 Memory Bank) kaydeder. Örn. 'doğum günüm 3 Nisan' "
                "gibi kısa, kendine yeterli bir cümle yaz."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Hatırlanacak bilgi (tek cümle)."}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Web'de güncel arama yapar (Özellik 1). Marka/model/tarih/isim "
                "gibi olgusal sorularda yanıtını doğrulamak için kullan; "
                "dönen kaynak URL + özet parçalarını dikkate al."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Arama sorgusu (kısa, anahtar kelimeli)."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": (
                "Özellik 6: yeni görev oluşturur. Kullanıcı 'yarına kadar X'i "
                "bitir' gibi bir görev talep ettiğinde çağır. due_at yerel ISO "
                "biçiminde: YYYY-MM-DD (tarih) veya YYYY-MM-DDTHH:MM:SS."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Görev başlığı."},
                    "project": {"type": "string", "description": "Proje adı (yoksa oluşturulur)."},
                    "priority": {"type": "string", "description": "low | medium | high | urgent"},
                    "due_date": {"type": "string", "description": "Hedef tarih (yerel ISO)."}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Görevleri listeler; proje adı ve/veya durum filtresi alınır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Proje adı (opsiyonel)."},
                    "status": {"type": "string", "description": "todo | in_progress | done"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Bir görevi 'done' olarak işaretler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "Tamamlanacak görevin kimliği."}
                },
                "required": ["task_id"]
            }
        }
    }
]

VALID_TOOL_NAMES = {spec["function"]["name"] for spec in TOOL_SPECS}


async def execute_tool(
    name: str,
    arguments: Optional[dict[str, Any]],
    monitor: Any = None,
) -> dict[str, Any]:
    """Aracı yürütür ve JSON-uyumlu bir sözlük döndürür."""
    arguments = arguments or {}

    if name == "get_system_stats":
        if monitor is not None:
            data = monitor.snapshot()
            if data:
                return data
        return {"error": "istatistikler henüz hazır değil, kısa süre sonra tekrar dene"}

    if name == "get_current_time":
        return {
            "datetime": datetime.datetime.now().isoformat(timespec="seconds"),
            "timezone": datetime.datetime.now().astimezone().tzname() or "",
        }

    if name == "get_weather":
        city = str(arguments.get("city") or "").strip() or None
        # Ağ çağrısı olay döngüsünü bloklamasın:
        return await asyncio.to_thread(weather_module.get, city)

    if name in ("create_reminder", "list_reminders", "delete_reminder", "ack_active_alarms"):
        from ..reminders import service as _reminder_service

        _rem = _reminder_service.SERVICE
        if _rem is None:
            return {"error": "hatırlatıcı servisi hazır değil"}
        if name == "create_reminder":
            try:
                row = await asyncio.to_thread(
                    _rem.create,
                    str(arguments.get("title") or ""),
                    str(arguments.get("due_at") or ""),
                )
                return {"created": row}
            except ValueError as exc:
                return {"error": str(exc)}
        if name == "list_reminders":
            return {"reminders": await asyncio.to_thread(_rem.list)}
        if name == "delete_reminder":
            ok = await asyncio.to_thread(_rem.delete, int(arguments.get("reminder_id") or 0))
            return {"deleted": ok}
        return {"acked": await asyncio.to_thread(_rem.ack_all, "voice")}

    if name == "save_memory":
        # Madde 18: Memory Bank — aktif sohbet sahibine yazar (core.context).
        # Düzeltme (v11): context jarvis_agent.core altındadır; eski '. import
        # context' referansı ImportError üretiyordu (test edilmemiş gizli bug).
        from ..core import context as _chat_context
        from ..store import database as _database

        content = str(arguments.get("content") or "").strip()
        mid = await asyncio.to_thread(
            _database.add_memory, _chat_context.get_owner(), content
        )
        if mid is None:
            return {"saved": False, "reason": "misafir oturum veya boş içerik"}
        return {"saved": True, "id": mid}

    if name == "web_search":
        # Özellik 1: web doğrulaması — engellemeyen thread'de çalışır.
        from . import websearch as _websearch

        query = str(arguments.get("query") or "").strip()
        if not query:
            return {"results": [], "error": "empty_query"}
        return await asyncio.to_thread(_websearch.web_search, query)

    if name in ("create_task", "list_tasks", "complete_task"):
        # Özellik 6: görev araçları — aktif sohbet sahibine yazar.
        from ..core import context as _chat_context
        from ..store import v11 as _v11

        owner = _chat_context.get_owner()
        if name == "create_task":
            task = await asyncio.to_thread(
                _v11.create_task,
                owner,
                str(arguments.get("title") or "").strip(),
                str(arguments.get("project") or "").strip(),
                str(arguments.get("priority") or "medium").strip(),
                str(arguments.get("due_date") or "").strip(),
            )
            if task is None:
                return {"created": False, "reason": "misafir oturum veya boş başlık"}
            return {"created": True, "task": task}
        if name == "list_tasks":
            project = str(arguments.get("project") or "").strip()
            status = str(arguments.get("status") or "").strip()
            tasks = await asyncio.to_thread(_v11.list_tasks, owner, None, status or None)
            if project:
                lowered = project.lower()
                tasks = [
                    t for t in tasks
                    if lowered in str(t.get("project_name") or "").lower()
                    or lowered in str(t.get("title") or "").lower()
                ]
            return {"tasks": tasks[:20]}
        task_id = int(arguments.get("task_id") or 0)
        task = await asyncio.to_thread(_v11.complete_task, owner, task_id)
        if task is None:
            return {"completed": False, "reason": "görev bulunamadı veya misafir"}
        return {"completed": True, "task": task}

    return {"error": f"bilinmeyen araç: {name}"}

# === Faz 5-6-7 entegrasyon araç köprüsü (INT57) ===
# int57_bridge: mail/haber/dosya/akıllı ev/WhatsApp/e-posta araçlarını
# TOOL_SPECS'e ekler ve execute_tool'u sarmalar (idempotent).
from .int57_bridge import install_int57_bridge as _int57_install  # noqa: E402

_int57_install(globals())
