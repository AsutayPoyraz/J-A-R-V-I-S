"""Sohbet çekirdeği — REST ucu ve sesli modun birlikte kullandığı hatt.

Buradaki ``run_chat`` hem POST /api/chat hem de sesli moddan gelen
sözlü komutları işler; tek gerçek (source of truth) budur.

Özellik 1 (Yüksek IQ): sistem promptu ``llm/system_prompt.py``'dan gelir;
olgu soruları web_search ile doğrulanır (``_maybe_fact_check``).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .. import config
from ..core import context as chat_context
from ..core.stats import StatsMonitor
from ..llm import system_prompt
from ..llm.provider import ChatProvider, ProviderError
from ..llm.tools import TOOL_SPECS, execute_tool
from ..store import database

logger = logging.getLogger("jarvis.chat")

MAX_TOOL_HOPS = 3

# Geriye dönük uyumluluk: prompt metinleri ve üslup ekleri artık merkezî
# modülde yaşar (llm/system_prompt.py); eski içe aktarmalar bozulmasın.
SYSTEM_PROMPT_TR = system_prompt.SYSTEM_PROMPT_TR
SYSTEM_PROMPT_EN = system_prompt.SYSTEM_PROMPT_EN
SYSTEM_PROMPT = system_prompt.SYSTEM_PROMPT
build_system_prompt = system_prompt.build_system_prompt

OFFLINE_NOTE = "Çevrimdışıyım, web'den doğrulayamadım efendim."
VERIFIED_NOTE = "Web'den doğruladım:"


# (Üslup ekleri ve build_system_prompt llm/system_prompt.py'ya taşındı — Özellik 1.)


async def _maybe_fact_check(
    provider: ChatProvider, message: str, final: str
) -> tuple[str, list[str]]:
    """Özellik 1: olgu sorularını web_search ile doğrular.

    Dönüş: (nihai yanıt, kullanılan araçlar). Hatalar asla sohbeti bozmaz;
    her kenar durumda taslak yanıt korunur.
    """
    tools_used: list[str] = []
    if config.env("JARVIS_FACT_CHECK", "1") == "0":
        return final, tools_used
    if not system_prompt.fact_check_needed(message):
        return final, tools_used
    try:
        search = await execute_tool("web_search", {"query": message})
    except Exception:  # noqa: BLE001 — doğrulama arızası sohbeti bloklamaz
        logger.exception("web_search araç çağrısı beklenmedik hata verdi")
        return final, tools_used
    if not isinstance(search, dict):
        return final, tools_used
    tools_used.append("web_search")
    if search.get("error") == "offline":
        return f"{final}\n\n({OFFLINE_NOTE})", tools_used
    results = search.get("results") or []
    if not results:
        # Arama boş → yalnızca LLM cevabı sunulur (gereksinim 1 kenar durumu).
        return final, tools_used
    try:
        verify = await provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Sen titiz bir doğrulama editörüsün; yalnızca nihai "
                        "onaylı cevabı düz metin olarak döndürürsün."
                    ),
                },
                {
                    "role": "user",
                    "content": system_prompt.build_fact_check_prompt(
                        message, final, system_prompt.sources_block(results)
                    ),
                },
            ]
        )
    except ProviderError as exc:
        logger.warning("Doğrulama turu başarısız, taslak korunuyor: %s", exc)
        return final, tools_used
    corrected = (verify.content or "").strip()
    if not corrected:
        return final, tools_used
    if corrected.rstrip(".") == final.rstrip("."):
        return final, tools_used
    return f"{VERIFIED_NOTE} {corrected}", tools_used


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
    mood: str = "neutral",
    persona_name: str = "",
    persona_style: str = "classic",
    provider_name: str = "",
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
            "content": build_system_prompt(
                language, mode, mood, persona_name, persona_style
            ) + memory_block,
        }
    ]
    # Özellik 8 (RAG): kullanıcının bilgi tabanından ilgili bölümler eklenir.
    if persist:
        try:
            from ..knowledge import retriever as _rag

            rag_block = _rag.context_block(owner_id, message)
            if rag_block:
                llm_messages[0]["content"] += rag_block
        except Exception:  # noqa: BLE001 — RAG hatası sohbeti bloklamaz
            logger.debug("RAG bağlamı eklenemedi", exc_info=True)
    if persist:
        for row in database.get_messages(limit=24, owner_id=owner_id):
            llm_messages.append({"role": row["role"], "content": row["content"]})
    else:
        llm_messages.append({"role": "user", "content": message})

    used_tools: list[str] = []
    final: Optional[str] = None
    used_provider = provider.name
    fallback_occurred = False

    # Özellik 18: kullanıcı sağlayıcı tercih ettiyse akıllı fallback zinciri
    # kullanılır (tercih başa alınır; mock daima son çaredir).
    router_provider: Optional[Any] = None
    if provider_name and provider_name.lower() not in ("auto", ""):
        from ..llm import router as llm_router

        user_id = owner_id[5:] if owner_id.startswith("user:") else ""
        router_provider = llm_router
        preferred = provider_name.lower()

    try:
        for _hop in range(MAX_TOOL_HOPS):
            if router_provider is not None:
                result = await router_provider.route_with_fallback(
                    llm_messages,
                    TOOL_SPECS,
                    preferred=preferred,
                    user_id=user_id,
                )
            else:
                result = await provider.chat(llm_messages, TOOL_SPECS)
            # Sağlayıcı bağımsız: meta alanları varsa oku (Özellik 18).
            used_provider = getattr(result, "used_provider", "") or used_provider
            fallback_occurred = bool(
                getattr(result, "fallback_occurred", False)
            ) or fallback_occurred
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

    # Özellik 1 (Yüksek IQ): olgu soruları web'den doğrulanır; çelişki varsa
    # web sonucuna öncelik verilir ve yanıt işaretlenir.
    try:
        final, fact_tools = await _maybe_fact_check(provider, message, final)
        for tool_name in fact_tools:
            if tool_name not in used_tools:
                used_tools.append(tool_name)
    except Exception:  # noqa: BLE001 — doğrulama hatası yanıtı bozmamalı
        logger.exception("Fact-check adımı beklenmedik biçimde başarısız oldu")

    if persist:
        database.add_message("assistant", final, owner_id=owner_id)
    return {
        "reply": final,
        "used_tools": used_tools,
        "provider": used_provider,
        "model": getattr(result, "model", "") or provider.model,
        "provider_used": used_provider,
        "fallback_occurred": fallback_occurred,
        "error": False,
    }
