"""Misafir modu testleri (Prompt 2) — guard'lar, /api/session, kalıcılık yok."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config, security
from jarvis_agent.app import create_app
from jarvis_agent.store import database


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
    # Misafir senaryosu: tüm hostlar loopback dışı → kimliksiz istek = misafir.
    monkeypatch.setattr(security, "is_loopback", lambda host: False)
    app = create_app()
    with TestClient(app) as client:
        yield client, db_path


def test_session_is_guest_with_capabilities(rig):
    client, _ = rig
    body = client.get("/api/session").json()
    assert body["mode"] == "guest"
    assert body["capabilities"] == {
        "chat": True,
        "files": False,
        "device_control": False,
        "history": False,
        "settings_write": False,
    }


def test_guest_chat_works_but_is_not_persisted(rig):
    client, db_path = rig
    resp = client.post("/api/chat", json={"message": "merhaba jarvis"})
    assert resp.status_code == 200 and resp.json()["reply"]
    with sqlite3.connect(str(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    # Misafir geçmişi çağıramaz (kalıcılık yok + allow-list dışı).
    assert client.get("/api/conversation").status_code == 403


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/files"),
        ("post", "/api/files/upload"),
        ("post", "/api/camera/open"),
        ("get", "/api/camera/status"),
        ("get", "/api/system/stats"),
        ("get", "/api/system/wol"),
        ("post", "/api/system/wol/wake"),
        ("get", "/api/integrations"),
        ("get", "/api/smart-home/status"),
        ("post", "/api/smart-home/command"),
        ("get", "/api/reminders"),
        ("post", "/api/reminders"),
        ("get", "/api/voice/status"),
        ("post", "/api/voice/start"),
        ("get", "/api/audit"),
    ],
)
def test_guest_is_blocked_on_privileged_routes(rig, method, path):
    client, _ = rig
    if method == "get":
        resp = client.get(path)
    elif path == "/api/files/upload":
        resp = client.post(path, files={"file": ("a.txt", b"hello", "text/plain")})
    else:
        resp = client.post(path, json={})
    assert resp.status_code == 403, (path, resp.status_code)
    assert "Misafir" in resp.json()["detail"]


def test_guest_cannot_write_settings(rig):
    client, _ = rig
    resp = client.put("/api/settings", json={"background_color": "dark"})
    assert resp.status_code in (401, 403)


def test_public_routes_remain_open(rig):
    client, _ = rig
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/session").status_code == 200
    assert client.get("/api/weather").status_code == 200


def test_guest_websocket_gets_no_stats(rig):
    """Misafire yalnızca sohbet olayları; istatistik akışı verilmez."""
    client, _ = rig
    with client.websocket_connect("/ws/stats?client_id=guest-client-1234") as ws:
        frame = ws.receive_json()
    assert frame.get("type") == "guest"
    assert "cpu" not in frame
