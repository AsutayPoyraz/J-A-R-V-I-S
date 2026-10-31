"""DeepSeek sağlayıcısı (Özellik 18) — OpenAI-uyumlu protokol.

API: https://api.deepseek.com (OpenAI uyumlu; ``/v1/chat/completions``)
Model: deepseek-reasoner (R1, varsayılan) veya deepseek-chat.
Env: JARVIS_DEEPSEEK_API_KEY (veya DEEPSEEK_API_KEY).

Not: R1 "reasoner" yanıtlarında düşünce adımları i
yor olabilir; ``strip_think_blocks`` bunları temizler.
"""
from __future__ import annotations

import re

from .openai_compat import OpenAICompatProvider

_BASE_URL = "https://api.deepseek.com"

# Etiketler kaynakta bölünmesin diye birleştirilir (think etiketleri).
_THINK_OPEN = "<" + "think" + ">"
_THINK_CLOSE = "</" + "think" + ">"
_THINK_RE = re.compile(
    re.escape(_THINK_OPEN) + r".*?(?:" + re.escape(_THINK_CLOSE) + r"|$)",
    re.DOTALL,
)


def strip_think_blocks(text: str) -> str:
    """R1 düşünce bloklarını yanıttan çıkarır (mega prompt Ek Notlar/18)."""
    cleaned = _THINK_RE.sub("", text or "")
    # Kapanış etiketi olmayan yarım blokları da temizle.
    if _THINK_OPEN in cleaned:
        cleaned = cleaned.split(_THINK_OPEN)[0]
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class DeepSeekProvider(OpenAICompatProvider):
    """DeepSeek API — OpenAI-uyumlu protokol (R1 reasoner dahil)."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-reasoner",
        timeout: float = 120.0,
    ) -> None:
        super().__init__(
            name="deepseek",
            base_url=_BASE_URL,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )

    async def chat(self, messages, tools=None):  # type: ignore[override]
        result = await super().chat(messages, tools)
        if result.content:
            cleaned = strip_think_blocks(result.content)
            if cleaned:
                result.content = cleaned
        return result
