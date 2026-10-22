"""Bölüm D testleri — madde 1 (konuşma modları) ve madde 14 (TTS ayarları)."""
from __future__ import annotations

import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config
from jarvis_agent.app import create_app
from jarvis_agent.chat.service import build_system_prompt, run_chat
from jarvis_agent.store import database


def _connect_to(path):
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@pytest.fixture()
def rig(monkeypatch, tmp_path):
    """(app, db_path) döndürür; test kendi TestClient'ını açar."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(database, "connect", lambda: _connect_to(db_path))
    return create_app(), db_path


class _SeedProvider:
    """Araç çağırmadan tek yanıtta biten sahte LLM sağlayıcısı."""

    name = "seed"
    model = "seed-1"

    def __init__(self) -> None:
        self.last_messages: list[dict] = []

    async def chat(self, messages, tools):  # noqa: ANN001
        self.last_messages = messages

        class _Result:
            content = "tamam efendim"
            tool_calls: list = []

        return _Result()


# ── Madde 1: konuşma modları ────────────────────────────────────────────────

def test_system_prompt_modes_tr():
    formal = build_system_prompt("tr", mode="formal")
    casual = build_system_prompt("tr", mode="casual")
    adaptive = build_system_prompt("tr", mode="adaptive")
    assert "resmî" in formal
    assert "samimi" in casual
    assert "duruma göre" in adaptive
    assert len({formal, casual, adaptive}) == 3


def test_system_prompt_modes_en_and_fallback():
    assert "formal" in build_system_prompt("en", mode="formal").lower()
    # Geçersiz mod → varsayılana düşer (prompt injection'a kapalı).
    assert build_system_prompt("tr", mode="jailbreak") == build_system_prompt(
        "tr", mode=config.DEFAULT_CONVERSATION_MODE
    )


def test_run_chat_injects_mode_prompt():
    provider = _SeedProvider()
    result = asyncio.run(run_chat("selam", provider, persist=False, mode="casual"))
    assert result["error"] is False
    assert result["reply"] == "tamam efendim"
    system = provider.last_messages[0]
    assert system["role"] == "system"
    assert "samimi" in system["content"]


# ── Madde 14: TTS ayarları ──────────────────────────────────────────────────

def test_tts_defaults():
    row = database.get_user_settings("tts-default-user")
    assert row["tts_rate"] == 1.0
    assert row["tts_voice"] == "tr"


def test_tts_settings_roundtrip(rig):
    app, _ = rig
    with TestClient(app) as client:
        r = client.put("/api/settings", json={"tts_rate": 1.5, "tts_voice": "en"})
        assert r.status_code == 200
        data = client.get("/api/settings").json()
        assert data["tts_rate"] == 1.5
        assert data["tts_voice"] == "en"
        assert "tr" in data["allowed_tts_voices"]


def test_tts_settings_validation(rig):
    app, _ = rig
    with TestClient(app) as client:
        assert client.put("/api/settings", json={"tts_voice": "fr"}).status_code == 422
        assert client.put("/api/settings", json={"tts_rate": 3.0}).status_code == 422
        assert client.put("/api/settings", json={"tts_rate": 0.1}).status_code == 422
        assert client.put("/api/settings", json={"tts_rate": 0.75}).status_code == 200


def test_tts_settings_user_isolation(rig):
    """Madde 7: TTS tercihi de kullanıcıya özel izole saklanır."""
    app, _ = rig
    alice = {"X-Client-ID": "client-tts-alice-1"}
    bob = {"X-Client-ID": "client-tts-bob-1"}
    with TestClient(app) as client:
        assert client.put(
            "/api/settings", json={"tts_rate": 1.8}, headers=alice
        ).status_code == 200
        assert client.get("/api/settings", headers=bob).json()["tts_rate"] == 1.0
        assert client.get("/api/settings", headers=alice).json()["tts_rate"] == 1.8


def test_tts_service_clamps():
    from jarvis_agent.voice.tts import TTSService

    svc = TTSService(lang="fr", rate=9.9)
    assert svc._lang == "tr"  # geçersiz ses → varsayılan
    assert svc._rate == 2.0   # sınır kırpma
    svc.configure(rate=0.3)
    assert svc._rate == 0.5
    svc.configure(lang="en")
    assert svc._lang == "en"
    assert svc.settings == {"lang": "en", "rate": 0.5}