"""Sohbet çekirdeği — REST ucu ve sesli modun birlikte kullandığı hatt.

Buradaki ``run_chat`` hem POST /api/chat hem de sesli moddan gelen
sözlü komutları işler; tek gerçek (source of truth) budur.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .. import config
from ..core import context as chat_context
from ..core.stats import StatsMonitor
from ..llm.provider import ChatProvider, ProviderError
from ..llm.tools import TOOL_SPECS, execute_tool
from ..store import database

logger = logging.getLogger("jarvis.chat")

MAX_TOOL_HOPS = 3

SYSTEM_PROMPT_TR = (
    "Sen J.A.R.V.I.S adını taşıyan kişisel bir asistansın. "
    "Kullanıcınla doğal, saygılı ve akıcı Türkçe konuş; gerektiğinde "
    "'efendim' gibi kibar bir üslup kullanabilirsin. Yanıtlarını kısa ve öz tut. "
    "Sistem saati, hava durumu ve bilgisayar durumu gibi bilgilere yalnızca "
    "sana verilen araçlar (get_system_stats, get_current_time, get_weather) "
    "aracılığıyla erişebilirsin; bu bilgileri asla tahmin etme. "
    "Kullanıcı dosya silme, bilgisayarı kapatma gibi yıkıcı bir işlem isterse "
    "onay olmadan yapamayacağını açıkça belirt; shell komutu çalıştırma "
    "yetkin yoktur."
)

SYSTEM_PROMPT_EN = (
    "You are a personal assistant named J.A.R.V.I.S. "
    "Speak naturally, respectfully and fluently in English. Keep answers short "
    "and to the point. You can only access system clock, weather and computer "
    "status through the given tools (get_system_stats, get_current_time, "
    "get_weather) — never guess such facts. If the user asks for a destructive "
    "action (deleting files, shutting down the computer), clearly state that "
    "you cannot do it without confirmation; you have no shell access."
)


# Madde 1: konuşma modları — sistem promptuna üslup talimatı eklenir.
_MODE_TONE = {
    "formal": {
        "tr": (
            "Üslup: resmî ve profesyonel — yönetim kurulu sunumu gibi ölçülü, "
            "saygılı ve net konuş; şakaya girmeden bilgiyi aktar."
        ),
        "en": (
            "Tone: formal and professional — measured, respectful and clear, "
            "like a board-room briefing; convey information without jokes."
        ),
    },
    "casual": {
        "tr": (
            "Üslup: samimi bir arkadaş gibi — esprili, rahat ve sıcak konuş; "
            "'efendim' gibi resmî hitaplardan kaçın, hafif espri yapabilirsin."
        ),
        "en": (
            "Tone: casual like a close friend — relaxed, warm and playful; "
            "avoid formal honorifics, light humor is welcome."
        ),
    },
    "adaptive": {
        "tr": (
            "Üslup: duruma göre uyum sağla — araştırma/bilgi aktarımında resmî "
            "ve net ol; kullanıcı şaka yaptığında samimi ve esprili ol; yeniden "
            "soru sorulduğunda resmî tona dön."
        ),
        "en": (
            "Tone: adaptive to context — formal and precise for research and "
            "factual answers, friendly and playful when the user jokes, and "
            "back to formal when a serious question follows."
        ),
    },
}


def build_system_prompt(language: str = "tr", mode: str = "adaptive") -> str:
    """Madde 3 + Madde 1: dil ve konuşma modu sistem promptunu belirler."""
    lang = language if language in config.ALLOWED_LANGUAGES else "tr"
    if mode not in config.ALLOWED_CONVERSATION_MODES:
        mode = config.DEFAULT_CONVERSATION_MODE
    base = SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_TR
    return f"{base} {_MODE_TONE[mode][lang]}"


# Geriye dönük takma ad: testler ve diğer modüller TR promptu tek isimden okur.
SYSTEM_PROMPT = SYSTEM_PROMPT_TR


async def run_chat(
    message: str,
    provider: ChatProvider,
    monitor: Optional[StatsMonitor] = None,
    *,
    persist: bool = True,
    source: str = "text",
    owner_id: str = "local",
    language: str = "tr",
    mode: str = "adaptive",
) -> dict[str, Any]:
    """Bir kullanıcı iletisini uçtan uca işler.

    persist=False yalnızca içsel denemeler içindir; üretimde her mesaj
    geçmişe yazılır (gereksinim 5.3: konuşma geçmişi yerelde saklanır).
    ``language`` sistem prompt dilini (madde 3), ``mode`` üslubu (madde 1:
    formal/casual/adaptive) seçer.
    """
    message = (message or "").strip()

    # Madde 18: araçların (save_memory vb.) doğru sahibe yazması için bağlam.
    chat_context.set_owner(owner_id)

    if persist:
        database.add_message("user", message, owner_id=owner_id)
        database.audit("chat.message", detail=f"[{source}] {message[:200]}")

    # Madde 18: Memory Bank — kalıcı kayıtlar sistem bağlamına eklenir.
    memory_block = ""
    if persist:
        try:
            memories = database.list_memories(owner_id, limit=20)
        except Exception:  # noqa: BLE001 — hafıza hatası sohbeti bloklamasın
            memories = []
        if memories:
            lines = "\n".join(f"- {m['content']}" for m in memories)
            memory_block = (
                "\n\n[Kullanıcı hakkında kalıcı kayıtlar — Memory Bank]\n" + lines
            )

    llm_messages: list[dict] = [
        {
            "role": "system",
            "content": build_system_prompt(language, mode) + memory_block,
        }
    ]
    if persist:
        for row in database.get_messages(limit=24, owner_id=owner_id):
            llm_messages.append({"role": row["role"], "content": row["content"]})
    else:
        llm_messages.append({"role": "user", "content": message})

    used_tools: list[str] = []
    final: Optional[str] = None
    try:
        for _hop in range(MAX_TOOL_HOPS):
            result = await provider.chat(llm_messages, TOOL_SPECS)
            if not result.tool_calls:
                if result.content:
                    final = result.content.strip()
                break
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in result.tool_calls
                    ],
                }
            )
            for tc in result.tool_calls:
                output = await execute_tool(tc.name, tc.arguments, monitor=monitor)
                used_tools.append(tc.name)
                llm_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(output, ensure_ascii=False),
                    }
                )
    except ProviderError as exc:
        logger.warning("LLM çağrısı başarısız: %s", exc)
        reply = (
            "Üzgünüm efendim, yanıt alamadım. Yapay zekâ sağlayıcısına şu an "
            "ulaşılamıyor gibi görünüyor."
        )
        if persist:
            database.add_message("assistant", reply, owner_id=owner_id)
            database.audit("chat.error", detail=str(exc)[:400])
        return {
            "reply": reply,
            "used_tools": [],
            "provider": provider.name,
            "model": provider.model,
            "error": True,
        }

    if not final:
        final = (
            "Üzgünüm, şu an isteğinize anlamlı bir yanıt oluşturamadım. "
            "Lütfen tekrar dener misiniz?"
        )

    if persist:
        database.add_message("assistant", final, owner_id=owner_id)
    return {
        "reply": final,
        "used_tools": used_tools,
        "provider": provider.name,
        "model": provider.model,
        "error": False,
    }
