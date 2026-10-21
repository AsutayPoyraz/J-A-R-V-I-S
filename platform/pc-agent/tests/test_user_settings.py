"""Bölüm A testleri — kullanıcıya özel ayarlar, bordo tema, panel konumu,
dil ve misafir kısıtları (Madde 3, 4, 6, 7, 32)."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config, security
from jarvis_agent.app import create_app
from jarvis_agent.store import database

ALICE = {"X-Client-ID": "client-alice-12345678"}
BOB = {"X-Client-ID": "client-bob-12345678"}


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


def _local_client(app):
    # Varsayılan TestClient host'u "testclient" → loopback sayılır (yerel PC).
    return TestClient(app)


def _guest_client(app, monkeypatch):
    # Bu Starlette sürümü TestClient'ta client scope override etmediğinden
    # misafir senaryosu is_loopback test-seam'ı ile simüle edilir: tüm hostlar
    # loopback dışı sayılır → kimliksiz istek = misafir.
    monkeypatch.setattr(security, "is_loopback", lambda host: False)
    return TestClient(app)


# ── Madde 4: bordo tema ──────────────────────────────────────────────────────

def test_maroon_theme_accepted(rig):
    app, _ = rig
    with _local_client(app) as client:
        resp = client.put("/api/settings", json={"background_color": "maroon"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["background_color"] == "maroon"
        assert "maroon" in body["allowed_background_colors"]


def test_maroon_theme_persists(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.put("/api/settings", json={"background_color": "maroon"})
        assert client.get("/api/settings").json()["background_color"] == "maroon"


# ── Madde 7 + 32: ayarlar owner bazında izole ────────────────────────────────

def test_user_settings_isolated_by_client_id(rig):
    app, _ = rig
    with _local_client(app) as client:
        r1 = client.put(
            "/api/settings",
            json={"background_color": "maroon", "chat_position": "center"},
            headers=ALICE,
        )
        assert r1.status_code == 200
        r2 = client.put(
            "/api/settings",
            json={"background_color": "blue", "language": "en"},
            headers=BOB,
        )
        assert r2.status_code == 200

        alice = client.get("/api/settings", headers=ALICE).json()
        bob = client.get("/api/settings", headers=BOB).json()
        assert alice["background_color"] == "maroon"
        assert alice["chat_position"] == "center"
        assert bob["background_color"] == "blue"
        assert bob["language"] == "en"
        # Bob'un ayarları Alice'i etkilememeli (varsayılan right kalır)
        assert bob["chat_position"] == "right"


# ── Madde 3 + 32: dil ve sohbet paneli konumu ────────────────────────────────

def test_language_and_chat_position_update(rig):
    app, _ = rig
    with _local_client(app) as client:
        resp = client.put(
            "/api/settings", json={"language": "en", "chat_position": "center"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["language"] == "en"
        assert body["chat_position"] == "center"


def test_invalid_language_and_position_rejected(rig):
    app, _ = rig
    with _local_client(app) as client:
        assert client.put("/api/settings", json={"language": "fr"}).status_code == 422
        assert (
            client.put("/api/settings", json={"chat_position": "left"}).status_code
            == 422
        )


# ── Madde 6: misafir kısıtları ───────────────────────────────────────────────

def test_guest_reads_defaults_without_registration(rig, monkeypatch):
    app, db_path = rig
    with _guest_client(app, monkeypatch) as guest:
        # Prompt 2: misafire açık okuma ucu /api/session; ayarlar 403 (allow-list).
        body = guest.get("/api/session").json()
        assert body["mode"] == "guest"
        assert body["capabilities"]["settings_write"] is False
        defaults = database.get_user_settings("guest:anon")
        assert defaults["chat_position"] == "right"
        assert defaults["language"] == "tr"
        assert guest.get("/api/settings").status_code == 403
    # Misafir için user_settings satırı OLUŞTURULMAMALI ('local' sahibinin
    # migration satırı meşrudur; yalnızca misafir kaydı aranır — Madde 6).
    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM user_settings WHERE owner_id LIKE 'guest:%'"
        ).fetchone()[0]
    assert count == 0


def test_guest_cannot_write_settings(rig, monkeypatch):
    app, _ = rig
    with _guest_client(app, monkeypatch) as guest:
        resp = guest.put("/api/settings", json={"background_color": "maroon"})
        assert resp.status_code == 403


def test_guest_chat_not_persisted(rig, monkeypatch):
    app, db_path = rig
    with _guest_client(app, monkeypatch) as guest:
        resp = guest.post("/api/chat", json={"message": "misafir sohbeti"})
        assert resp.status_code == 200
        # Prompt 2: konuşma geçmişi misafire kapalı (allow-list dışı) → 403.
        assert guest.get("/api/conversation").status_code == 403
    # DB'ye hiç mesaj yazılmamalı (Madde 6: misafirde kayıt yok)
    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert count == 0
