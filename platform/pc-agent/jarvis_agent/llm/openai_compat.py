"""OpenAI-uyumlu sağlayıcı — OpenAI, Groq ve Ollama aynı protokolü konuşur."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from .provider import ChatProvider, ChatResult, ProviderError, ToolCall

logger = logging.getLogger("jarvis.llm.openai_compat")


class OpenAICompatProvider(ChatProvider):
    """OpenAI Chat Completions protokolünü konuşan sağlayıcı."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 90.0,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    # ── Mesaj dönüştürme (ortak format → OpenAI formatı) ──
    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role == "assistant" and msg.get("tool_calls"):
                out.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content") or None,
                        "tool_calls": [
                            {
                                "id": tc.get("id") or f"call_{i}",
                                "type": "function",
                                "function": {
                                    "name": tc.get("name", ""),
                                    "arguments": json.dumps(
                                        tc.get("arguments") or {}, ensure_ascii=False
                                    ),
                                },
                            }
                            for i, tc in enumerate(msg["tool_calls"])
                        ],
                    }
                )
            elif role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content") or "",
                    }
                )
            else:
                out.append({"role": role, "content": msg.get("content") or ""})
        return out

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(messages),
        }
        if tools:
            payload["tools"] = tools

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name} sağlayıcısına ulaşılamadı: {exc}") from exc

        if resp.status_code != 200:
            detail = ""
            try:
                detail = str(resp.json().get("error", {}).get("message", ""))
            except (ValueError, AttributeError):
                pass
            raise ProviderError(
                f"{self.name} hatası (HTTP {resp.status_code}): {detail[:300]}"
            )

        try:
            data = resp.json()
            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            tool_calls: list[ToolCall] = []
            for i, tc in enumerate(message.get("tool_calls") or []):
                fn = tc.get("function", {})
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = (
                        json.loads(raw_args)
                        if isinstance(raw_args, str)
                        else dict(raw_args)
                    )
                except ValueError:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id") or f"call_{i}",
                        name=fn.get("name", ""),
                        arguments=args,
                    )
                )
            return ChatResult(
                content=content,
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason", "stop"),
                model=data.get("model", self.model),
                tokens_used=int((data.get("usage") or {}).get("total_tokens") or 0),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"{self.name} yanıtı ayrıştırılamadı: {exc}") from exc
