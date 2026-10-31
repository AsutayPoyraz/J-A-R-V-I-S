"""Özellik 1 testleri: fact-check sınıflandırıcı, merkezî prompt, web_search."""
from __future__ import annotations

import asyncio

from jarvis_agent.llm import system_prompt as sp


# ── fact_check_needed (Clio 4 senaryosu dahil) ───────────────────────────────

def test_fact_check_classifier_clio4_case():
    assert sp.fact_check_needed("Clio 4 hangi markanın aracıdır?") is True
    assert sp.fact_check_needed("Einstein ne zaman doğdu?") is True
    assert sp.fact_check_needed("Türkiye'nin başkenti nedir?") is True
    assert sp.fact_check_needed("Python kim icat etti?") is True
    # Genel sohbet / yaratıcı istekler / araç soruları atlanır.
    assert sp.fact_check_needed("merhaba nasılsın") is False
    assert sp.fact_check_needed("bana bir şiir yaz") is False
    assert sp.fact_check_needed("saat kaç") is False
    assert sp.fact_check_needed("hava durumu nasıl") is False
    assert sp.fact_check_needed("") is False
    assert sp.fact_check_needed("ab") is False


def test_system_prompt_centralized_and_iq_identity():
    prompt = sp.build_system_prompt("tr")
    assert "IQ 200-250" in prompt
    assert "ansiklopedik" in prompt
    assert "J.A.R.V.I.S" in prompt
    # Merkezî kaynak: chat.service yeniden dışa aktarır (geriye dönük uyum).
    from jarvis_agent.chat.service import SYSTEM_PROMPT_TR

    assert SYSTEM_PROMPT_TR is sp.SYSTEM_PROMPT_TR


def test_system_prompt_modes_and_persona():
    formal = sp.build_system_prompt("tr", mode="formal")
    casual = sp.build_system_prompt("tr", mode="casual")
    assert "resmî" in formal and "samimi" in casual
    assert "Zeynep" in sp.build_system_prompt("tr", persona_name="Zeynep")
    # Geçersiz mod → varsayılan (prompt injection'a kapalı).
    assert sp.build_system_prompt("tr", mode="jailbreak") == sp.build_system_prompt(
        "tr", mode="adaptive"
    )


def test_web_search_offline_graceful(monkeypatch):
    from jarvis_agent.llm import websearch

    def _raise(*a, **k):
        raise websearch.httpx.ConnectError("offline")

    monkeypatch.setattr(websearch.httpx, "get", _raise)
    monkeypatch.setattr(websearch, "_DDGS_AVAILABLE", False)
    result = websearch.web_search("test sorgu")
    assert result["error"] == "offline" and result["results"] == []
    assert websearch.web_search("")["error"] == "empty_query"


def test_web_search_sources_limited():
    block = sp.sources_block(
        [{"title": f"t{i}", "url": f"u{i}", "snippet": f"s{i}"} for i in range(6)],
        limit=3,
    )
    assert block.count("(kaynak:") == 3  # 3 kaynak sınırı (Özellik 1.4)


def test_run_chat_fact_check_offline_note(monkeypatch):
    from jarvis_agent.chat import service as chat_service

    class _Provider:
        name = "mock"
        model = "mock-1"

        async def chat(self, messages, tools=None):
            from jarvis_agent.llm.provider import ChatResult

            return ChatResult(content="Clio 4 Volkswagen'in aracıdır.")

    async def _fake_execute(name, args, monitor=None):
        return {"results": [], "error": "offline"}

    monkeypatch.setattr(chat_service, "execute_tool", _fake_execute)
    result = asyncio.run(
        chat_service.run_chat("Clio 4 hangi markanın?", _Provider(), persist=False)
    )
    assert result["error"] is False
    assert "Çevrimdışıyım" in result["reply"]
    assert "web_search" in result["used_tools"]


def test_run_chat_fact_check_correction(monkeypatch):
    """Web sonucu taslakla çelişirse 'Web'den doğruladım:' ile düzeltme gelir."""
    from jarvis_agent.chat import service as chat_service
    from jarvis_agent.llm.provider import ChatResult

    class _Provider:
        name = "mock"
        model = "mock-1"
        calls = 0

        async def chat(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return ChatResult(content="Volkswagen Clio üretir.")
            return ChatResult(content="Clio 4, Renault'nun bir modelidir.")

    async def _fake_execute(name, args, monitor=None):
        return {
            "results": [
                {"title": "Renault", "url": "https://renault.com",
                 "snippet": "Clio Renault tarafından üretilir."},
            ],
            "provider": "duckduckgo",
            "error": "",
        }

    monkeypatch.setattr(chat_service, "execute_tool", _fake_execute)
    provider = _Provider()
    result = asyncio.run(
        chat_service.run_chat("Clio 4 hangi markanın?", provider, persist=False)
    )
    assert result["reply"].startswith("Web'den doğruladım:")
    assert "Renault" in result["reply"]


# ── Özellik 18: router fallback zinciri ─────────────────────────────────────

def test_llm_router_fallback_chain_priority():
    from jarvis_agent.llm import router as llm_router

    chain = llm_router.fallback_chain("")
    assert chain[0] == "gemini"          # Yeni öncelik: gemini başta
    assert chain[1] == "deepseek"
    assert "groq" in chain[:4] and "llama" in chain[:4]
    assert chain[-1] == "mock"           # mock daima son çare
    pref = llm_router.fallback_chain("groq")
    assert pref[0] == "groq" and pref[1] == "gemini"


def test_llm_router_falls_back_to_mock(rig):
    """Hiçbir anahtar yoksa zincir mock'a düşer (rig .env anahtarlarını izole eder)."""
    from jarvis_agent.llm import router as llm_router

    result = asyncio.run(
        llm_router.route_with_fallback([{"role": "user", "content": "selam"}])
    )
    assert result.used_provider == "mock"
    assert result.content


def test_deepseek_think_blocks_stripped():
    from jarvis_agent.llm.deepseek_provider import strip_think_blocks

    open_tag, close_tag = "<" + "think" + ">", "</" + "think" + ">"
    raw = f"{open_tag}düşüneyim önce{close_tag}Clio 4 Renault'nun aracıdır."
    assert strip_think_blocks(raw) == "Clio 4 Renault'nun aracıdır."
    assert "düşünme" not in strip_think_blocks(f"{open_tag}iç düşünme")


def test_gemini_provider_config():
    from jarvis_agent.llm.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test", model="gemini-2.0-flash")
    assert provider.name == "gemini"
    assert "generativelanguage.googleapis.com" in provider.base_url

