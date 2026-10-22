"""Bölüm E testleri — Memory Bank (18), özel komutlar (22), ekran analizi/otomasyon (9),
üretkenlik: notlar/yapılacaklar (23) ve misafir kısıtları.

Her test hermetiktir: DB geçici dosyada, süreç başlatma ``_popen`` mock'u ile
yakalanır, vision çağrısı ağa çıkmaz.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config, security
from jarvis_agent.app import create_app
from jarvis_agent.core import screen
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
    # Tüm hostlar loopback dışı sayılır → kimliksiz istek = misafir.
    monkeypatch.setattr(security, "is_loopback", lambda host: False)
    return TestClient(app)


# ── Madde 18: Memory Bank ────────────────────────────────────────────────────

def test_memory_add_list_delete(rig):
    app, _ = rig
    with _local_client(app) as client:
        resp = client.post("/api/memory", json={"content": "Doğum günüm 3 Nisan"}, headers=ALICE)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

        body = client.get("/api/memory", headers=ALICE).json()
        assert any("3 Nisan" in m["content"] for m in body["memories"])

        mid = body["memories"][0]["id"]
        assert client.delete(f"/api/memory/{mid}", headers=ALICE).json()["deleted"] is True
        assert client.get("/api/memory", headers=ALICE).json()["memories"] == []


def test_memory_isolated_by_owner(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/memory", json={"content": "alice sır"}, headers=ALICE)
        body = client.get("/api/memory", headers=BOB).json()
        assert body["memories"] == []


def test_memory_guest_cannot_write(rig, monkeypatch):
    app, _ = rig
    with _guest_client(app, monkeypatch) as client:
        resp = client.post("/api/memory", json={"content": "misafir notu"})
        assert resp.status_code == 403
        # Okuma misafire açıktır ama boş döner (misafir kalıcı veri görmez).
        assert client.get("/api/memory").json()["memories"] == []


# ── Madde 22: özel komutlar ──────────────────────────────────────────────────

def test_custom_command_reply_text_and_chat_shortcut(rig):
    app, _ = rig
    with _local_client(app) as client:
        resp = client.post(
            "/api/commands",
            json={"phrase": "Kahve Zamanı", "action_type": "reply_text",
                  "action_payload": "Kahvenizi getirdim efendim."},
            headers=ALICE,
        )
        assert resp.status_code == 200

        # Aynı ifade ikinci kez → 422 (yinelenen)
        assert client.post(
            "/api/commands",
            json={"phrase": "kahve zamanı", "action_type": "reply_text"},
            headers=ALICE,
        ).status_code == 422

        # Sohbet ucu: ifade LLM'e gitmeden yürütülür
        chat = client.post("/api/chat", json={"message": "kahve zamanı"}, headers=ALICE).json()
        assert chat["provider"] == "custom-command"
        assert "Kahvenizi" in chat["reply"]


def test_custom_command_open_app_validation(rig, monkeypatch):
    app, _ = rig
    with _local_client(app) as client:
        # Beyaz liste dışı uygulama → 422
        bad = client.post(
            "/api/commands",
            json={"phrase": "oyun aç", "action_type": "open_app", "action_payload": "steam"},
            headers=ALICE,
        )
        assert bad.status_code == 422

        # Beyaz listeli uygulama kaydedilir; açma _popen mock'u ile yakalanır.
        launched: list[str] = []
        monkeypatch.setattr(screen, "_popen", lambda cmd: launched.append(cmd))
        ok = client.post(
            "/api/commands",
            json={"phrase": "notepad aç", "action_type": "open_app", "action_payload": "notepad"},
            headers=ALICE,
        )
        assert ok.status_code == 200
        chat = client.post("/api/chat", json={"message": "notepad aç"}, headers=ALICE).json()
        assert chat["provider"] == "custom-command"
        assert launched and "notepad" in launched[0]


# ── Madde 23: notlar ve yapılacaklar ─────────────────────────────────────────

def test_notes_todos_crud_and_isolation(rig):
    app, _ = rig
    with _local_client(app) as client:
        nid = client.post(
            "/api/notes", json={"title": "Alışveriş", "content": "süt, ekmek"}, headers=ALICE
        ).json()["id"]
        notes = client.get("/api/notes", headers=ALICE).json()["notes"]
        assert any(n["title"] == "Alışveriş" for n in notes)
        # Bob aynı başlığı koyabilir; Alice'in notunu göremez/silemez (owner izolasyonu).
        assert client.post("/api/notes", json={"title": "Alışveriş"}, headers=BOB).status_code == 200
        assert client.delete(f"/api/notes/{nid}", headers=BOB).status_code == 404
        assert client.delete(f"/api/notes/{nid}", headers=ALICE).json()["deleted"] is True

        tid = client.post("/api/todos", json={"title": "Rapor gönder"}, headers=ALICE).json()["id"]
        todos = client.get("/api/todos", headers=ALICE).json()["todos"]
        assert any(t["title"] == "Rapor gönder" for t in todos)
        assert client.put(f"/api/todos/{tid}", json={"done": True}, headers=ALICE).json()["updated"] is True
        done_row = next(t for t in todos if t["id"] == tid)
        assert client.delete(f"/api/todos/{tid}", headers=ALICE).json()["deleted"] is True


def test_notes_todos_guest_blocked(rig, monkeypatch):
    app, _ = rig
    with _guest_client(app, monkeypatch) as client:
        assert client.post("/api/notes", json={"title": "misafir"}).status_code == 403
        assert client.post("/api/todos", json={"title": "misafir"}).status_code == 403
        # Okuma da misafire kapalıdır (veri sızıntısı yüzeyi sıfırlanır).
        assert client.get("/api/notes").status_code == 403
