"""LLM sağlayıcı katmanı — sağlayıcı seçimi ve fabrika.

Sağlayıcılar değiştirilebilir (gereksinim 2): groq | openai | anthropic |
ollama | mock. Seçim JARVIS_LLM_PROVIDER ile yapılır; boş bırakılırsa eldeki
anahtara göre otomatik algılanır.
"""
from __future__ import annotations

import logging
import os

from .. import config
from .anthropic_provider import AnthropicProvider
from .mock_provider import MockProvider
from .openai_compat import OpenAICompatProvider
from .provider import ChatProvider, ChatResult, ProviderError, ToolCall

logger = logging.getLogger("jarvis.llm")

_OPENAI_COMPAT_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}


def _has_key(choice: str) -> bool:
    keys = {
        "gemini": config.GEMINI_API_KEY,
        "deepseek": config.DEEPSEEK_API_KEY,
        "groq": config.GROQ_API_KEY,
        "llama": config.GROQ_API_KEY,
        "openai": config.OPENAI_API_KEY,
        "anthropic": config.ANTHROPIC_API_KEY,
        "mock": "mock",
        "ollama": config.OLLAMA_URL,
    }
    return bool(keys.get(choice))


def build_provider() -> ChatProvider:
    """Ortam değişkenlerine göre LLM sağlayıcısı oluşturur."""
    choice = (os.getenv("JARVIS_LLM_PROVIDER") or config.active_provider()).lower()

    if choice in ("groq", "openai", "anthropic") and not _has_key(choice):
        logger.warning(
            "%s sağlayıcısı seçildi fakat API anahtarı yok — mock moda düşünülüyor.",
            choice,
        )
        return MockProvider()

    model_override = config.env("JARVIS_LLM_MODEL")

    if choice == "gemini":
        from .gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=config.GEMINI_API_KEY,
            model=model_override or config.DEFAULT_MODELS["gemini"],
        )
    if choice == "deepseek":
        from .deepseek_provider import DeepSeekProvider

        return DeepSeekProvider(
            api_key=config.DEEPSEEK_API_KEY,
            model=model_override or config.DEFAULT_MODELS["deepseek"],
        )
    if choice in ("groq", "llama"):
        model = (
            model_override
            or (config.DEFAULT_MODELS["llama"] if choice == "llama" else config.GROQ_MODEL)
        )
        return OpenAICompatProvider(
            name="groq" if choice == "groq" else "llama",
            base_url=config.env(
                "JARVIS_GROQ_BASE_URL", _OPENAI_COMPAT_BASE_URLS["groq"]
            ),
            api_key=config.GROQ_API_KEY,
            model=model,
        )
    if choice == "openai":
        return OpenAICompatProvider(
            name="openai",
            base_url=config.env(
                "JARVIS_OPENAI_BASE_URL", _OPENAI_COMPAT_BASE_URLS["openai"]
            ),
            api_key=config.OPENAI_API_KEY,
            model=model_override or config.DEFAULT_MODELS["openai"],
        )
    if choice == "anthropic":
        return AnthropicProvider(
            api_key=config.ANTHROPIC_API_KEY,
            model=model_override or config.DEFAULT_MODELS["anthropic"],
        )
    if choice == "ollama":
        url = config.env("JARVIS_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        return OpenAICompatProvider(
            name="ollama",
            base_url=f"{url}/v1",
            api_key="",
            model=model_override or config.DEFAULT_MODELS["ollama"],
        )
    if choice == "mock":
        return MockProvider()

    raise ProviderError(f"Bilinmeyen LLM sağlayıcısı: {choice}")


__all__ = [
    "AnthropicProvider",
    "ChatProvider",
    "ChatResult",
    "MockProvider",
    "OpenAICompatProvider",
    "ProviderError",
    "ToolCall",
    "build_provider",
]
