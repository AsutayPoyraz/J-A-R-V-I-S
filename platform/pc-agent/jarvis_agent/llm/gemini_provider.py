"""Google Gemini sağlayıcısı (Özellik 18).

Varsayım (kod başında açık): google-generativeai SDK yerine Gemini'nin resmî
**OpenAI-uyumlu** ucunun kullanılması tercih edildi — httpx zaten projede var
ek bağımlılık gerektirmez, araç çağrısı (function calling) dahil tam
işlevseldir. API: https://generativelanguage.googleapis.com/v1beta/openai/

Env: JARVIS_GEMINI_API_KEY (veya GEMINI_API_KEY) — JARVIS_GEMINI_MODEL ile
model geçersiz kılınabilir (varsayılan: gemini-2.0-flash).
"""
from __future__ import annotations

from .openai_compat import OpenAICompatProvider

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiProvider(OpenAICompatProvider):
    """OpenAI-uyumlu protokolle konuşan Google Gemini sağlayıcısı."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 90.0,
    ) -> None:
        super().__init__(
            name="gemini",
            base_url=_BASE_URL,
            api_key=api_key,
            model=model,
            timeout=timeout,
        )
