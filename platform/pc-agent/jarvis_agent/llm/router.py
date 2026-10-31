"""LLM yönlendirici — Özellik 18: öncelik sırası + akıllı fallback.

Öncelik (mega prompt): gemini → deepseek → groq → llama (Groq üzerinde
llama-3.3-70b-versatile). Kullanıcı tercih ederirse (``preferred``) o
sağlayıcı başa alınır; yapılandırılmamışlar atlanır; hata/timeout/kota
durumunda sıradakine geçilir.

Anahtar çözünürlüğü (Özellik 5B entegrasyonu): kullanıcı hesabına kaydedilmiş
API anahtarı varsa .env'deki değer yerine O kullanılır (DB > .env > yok).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .. import config
from .provider import ChatProvider, ChatResult, ProviderError

logger = logging.getLogger("jarvis.llm.router")

PROVIDER_PRIORITY = ["gemini", "deepseek", "groq", "llama"]

_KNOWN_PROVIDERS = tuple(PROVIDER_PRIORITY) + ("openai", "anthropic", "ollama", "mock")


class AllProvidersFailedError(ProviderError):
    """Yapılandırılmış hiçbir LLM sağlayıcısından yanıt alınamadı."""


def env_key_for(name: str) -> str:
    """Sağlayıcının .env anahtarını döndürür (bilinen sağlayıcılar)."""
    keys = {
        "gemini": config.GEMINI_API_KEY,
        "deepseek": config.DEEPSEEK_API_KEY,
        "groq": config.GROQ_API_KEY,
        "llama": config.GROQ_API_KEY,
        "openai": config.OPENAI_API_KEY,
        "anthropic": config.ANTHROPIC_API_KEY,
        "ollama": config.OLLAMA_URL,  # URL varlığı yeterli
        "mock": "mock",
    }
    return keys.get(name, "")


def is_configured(name: str, user_id: str = "") -> bool:
    """Sağlayıcı kullanılabilir mi? (kullanıcı anahtarı > .env)."""
    if name not in _KNOWN_PROVIDERS:
        return False
    if name == "mock":
        return True
    if user_id:
        from ..store import user_keys

        if user_keys.resolve_llm_key(name, user_id):
            return True
    return bool(env_key_for(name))


def provider_model(name: str) -> str:
    """Sağlayıcının kullanacağı modeli döndürür."""
    if config.LLM_MODEL:
        return config.LLM_MODEL
    return config.DEFAULT_MODELS.get(name, "mock-1")


def build_provider_for(name: str, user_id: str = "") -> ChatProvider:
    """Adlandırılmış sağlayıcı örneği üretir (kullanıcı anahtarı öncelikli)."""
    from .anthropic_provider import AnthropicProvider
    from .deepseek_provider import DeepSeekProvider
    from .gemini_provider import GeminiProvider
    from .mock_provider import MockProvider
    from .openai_compat import OpenAICompatProvider

    user_key = ""
    if user_id:
        from ..store import user_keys

        user_key = user_keys.resolve_llm_key(name, user_id) or ""

    if name == "gemini":
        key = user_key or config.GEMINI_API_KEY
        if not key:
            raise ProviderError("Gemini API anahtarı yok.")
        return GeminiProvider(api_key=key, model=provider_model("gemini"))
    if name == "deepseek":
        key = user_key or config.DEEPSEEK_API_KEY
        if not key:
            raise ProviderError("DeepSeek API anahtarı yok.")
        return DeepSeekProvider(api_key=key, model=provider_model("deepseek"))
    if name in ("groq", "llama"):
        key = user_key or config.GROQ_API_KEY
        if not key:
            raise ProviderError("Groq API anahtarı yok.")
        model = provider_model("llama") if name == "llama" else config.GROQ_MODEL
        return OpenAICompatProvider(
            name="groq" if name == "groq" else "llama",
            base_url="https://api.groq.com/openai/v1",
            api_key=key,
            model=model,
        )
    if name == "openai":
        key = user_key or config.OPENAI_API_KEY
        if not key:
            raise ProviderError("OpenAI API anahtarı yok.")
        return OpenAICompatProvider(
            name="openai",
            base_url="https://api.openai.com/v1",
            api_key=key,
            model=provider_model("openai"),
        )
    if name == "anthropic":
        key = user_key or config.ANTHROPIC_API_KEY
        if not key:
            raise ProviderError("Anthropic API anahtarı yok.")
        return AnthropicProvider(api_key=key, model=provider_model("anthropic"))
    if name == "ollama":
        url = config.env("JARVIS_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        return OpenAICompatProvider(
            name="ollama",
            base_url=f"{url}/v1",
            api_key="",
            model=provider_model("ollama"),
        )
    return MockProvider()


def fallback_chain(preferred: str = "") -> list[str]:
    """Tercih + öncelik sırasına göre denenecek sağlayıcı zinciri."""
    pref = (preferred or "").strip().lower()
    chain: list[str] = []
    if pref and pref in _KNOWN_PROVIDERS:
        chain.append(pref)
    for name in PROVIDER_PRIORITY:
        if name not in chain:
            chain.append(name)
    # Öncelik listesinde olmayan ama yapılandırılmış olabilecek sağlayıcılar
    # zincirin sonuna eklenir (mock daima en sonda).
    for name in ("openai", "anthropic", "ollama"):
        if name not in chain:
            chain.append(name)
    chain.append("mock")
    return chain


async def route_with_fallback(
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    preferred: str = "",
    user_id: str = "",
) -> ChatResult:
    """Sırayla sağlayıcıları dener; ilk başarılı yanıtı döndürür.

    ChatResult.used_provider / fallback_occurred meta alanları dolar.
    """
    chain = fallback_chain(preferred)
    attempted = 0
    first_error = ""
    for name in chain:
        if not is_configured(name, user_id):
            continue
        attempted += 1
        try:
            provider = build_provider_for(name, user_id)
            result = await provider.chat(messages, tools)
            result.used_provider = name
            result.fallback_occurred = attempted > 1
            if attempted > 1:
                logger.info(
                    "LLM fallback: %s kullanıldı (tercih: %s)",
                    name,
                    preferred or "otomatik",
                )
            return result
        except ProviderError as exc:
            first_error = first_error or str(exc)
            logger.warning(
                "%s sağlayıcısı başarısız, sıradakine geçiliyor: %s", name, exc
            )
            continue
        except (TimeoutError, ConnectionError) as exc:
            first_error = first_error or str(exc)
            logger.warning("%s zaman aşımı/ağ hatası: %s", name, exc)
            continue
    raise AllProvidersFailedError(
        first_error or "Tüm LLM sağlayıcıları başarısız oldu"
    )

