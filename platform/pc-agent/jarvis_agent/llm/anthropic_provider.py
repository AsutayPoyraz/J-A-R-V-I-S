"""Anthropic (Claude) sağlayıcısı — Messages API."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .provider import ChatProvider, ChatResult, ProviderError, ToolCall

logger = logging.getLogger("jarvis.llm.anthropic")

_API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(ChatProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 90.0,
        max_tokens: int = 2048,
    ) -> None:
        self.name = "anthropic"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    # ── Ortak format → Anthropic formatı ──
    def _split_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        out: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system_parts.append(msg.get("content") or "")
            elif role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": [
                                    {"type": "text", "text": msg.get("content") or ""}
                                ],
                            }
                        ],
                    }
                )
            elif role == "assistant" and msg.get("tool_calls"):
                blocks: list[dict[str, Any]] = []
                if msg.get("content"):
                    blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": tc.get("name", ""),
                            "input": tc.get("arguments") or {},
                        }
                    )
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append(
                    {"role": role or "user", "content": msg.get("content") or ""}
                )
        return "\n\n".join(part for part in system_parts if part), out

    @staticmethod
    def _convert_tools(tools: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        return [
            {
                "name": spec["function"]["name"],
                "description": spec["function"]["description"],
                "input_schema": spec["function"]["parameters"],
            }
            for spec in tools or []
        ]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> ChatResult:
        system_text, converted = self._split_messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted,
        }
        if system_text:
            payload["system"] = system_text
        if tools:
            payload["tools"] = self._convert_tools(tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(_API_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Anthropic'e ulaşılamadı: {exc}") from exc

        if resp.status_code != 200:
            detail = ""
            try:
                detail = str(resp.json().get("error", {}).get("message", ""))
            except (ValueError, AttributeError):
                pass
            raise ProviderError(
                f"Anthropic hatası (HTTP {resp.status_code}): {detail[:300]}"
            )

        try:
            data = resp.json()
            content_parts: list[str] = []
            tool_calls: list[ToolCall] = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=block.get("id", "call_0"),
                            name=block.get("name", ""),
                            arguments=block.get("input") or {},
                        )
                    )
            usage = data.get("usage") or {}
            tokens = int(usage.get("input_tokens") or 0) + int(
                usage.get("output_tokens") or 0
            )
            return ChatResult(
                content="\n".join(content_parts),
                tool_calls=tool_calls,
                finish_reason=data.get("stop_reason") or "end_turn",
                model=data.get("model", self.model),
                tokens_used=tokens,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"Anthropic yanıtı ayrıştırılamadı: {exc}") from exc
