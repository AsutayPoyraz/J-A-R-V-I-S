"""LLM sağlayıcı soyutlaması — ortak mesaj formatı.

Ortak format (OpenAI sözlük modeli, "lingua franca"):
- {"role": "system"|"user"|"assistant"|"tool", "content": str}
- asistan araç çağrısı: {"role": "assistant", "content": str,
  "tool_calls": [{"id", "name", "arguments": dict}]}
- araç sonucu: {"role": "tool", "tool_call_id": str, "name": str, "content": str}

Her sağlayıcı bu formatı kendi protokolüne çevirir; arayüz kodu tek biçim kalır.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """Sağlayıcıdan gelen tek bir araç çağrısı."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResult:
    """Tek bir LLM turunun sonucu."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""
    # Özellik 12: token sarfiyatı (sağlayıcı usage alanı varsa dolar).
    tokens_used: int = 0
    # Özellik 18: yönlendirici meta bilgisi.
    used_provider: str = ""
    fallback_occurred: bool = False


class ProviderError(RuntimeError):
    """LLM sağlayıcı çağrısı başarısız (ağ, anahtar, kota, protokol...)."""


class ChatProvider(ABC):
    """Tüm LLM sağlayıcılarının uyguladığı arayüz."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> ChatResult:
        """Mesaj listesini gönderir; yanıt metnini ve araç çağrılarını döner."""
        raise NotImplementedError
