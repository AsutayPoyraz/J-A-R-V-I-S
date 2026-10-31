"""v11 test ortak fikstürleri — hermetik (tmp DB, gerçek ağ izole değil)."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config
from jarvis_agent.app import create_app
from jarvis_agent.store import database

SECRET = "test-secret-please-change-0123456789abcdef"


def _connect_to(path):
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@pytest.fixture()
def rig(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(database, "connect", lambda: _connect_to(db_path))
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "BCRYPT_ROUNDS", 4)
    monkeypatch.setenv("JARVIS_FACT_CHECK", "1")
    monkeypatch.setenv("JARVIS_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setenv("JARVIS_VOICE_DISABLED", "1")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "OLLAMA_URL", "")
    app = create_app()
    with TestClient(app) as client:
        yield client, db_path
