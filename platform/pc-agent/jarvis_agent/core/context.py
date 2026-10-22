"""Bölüm E (madde 18): aktif sohbet sahibinin araçlara taşınması.

LLM araç yürütücüsü (execute_tool) owner parametresi almaz; Memory Bank gibi
kullanıcıya özel araçların doğru sahibe yazması için ``run_chat`` her çağrının
başında buradaki bağlamı günceller (contextvar → async/thread güvenli).
"""
from __future__ import annotations

from contextvars import ContextVar

_current_owner: ContextVar[str] = ContextVar("jarvis_chat_owner", default="local")


def set_owner(owner_id: str) -> None:
    """Aktif sohbet sahibini ayarlar (boş değer → 'local')."""
    _current_owner.set(str(owner_id or "local"))


def get_owner() -> str:
    """Aktif sohbet sahibini döndürür."""
    return _current_owner.get()
