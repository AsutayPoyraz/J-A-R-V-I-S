"""Kritik komut testleri (Bölüm C — madde 15: 2FA elevation).

Kapsam: OTP prepare/confirm akışı, hatalı OTP denemeleri (3 hak),
elevation token doğrulaması, dosya silme ucu (loopback serbest), shutdown
ucunun daima elevation istemesi + ALLOW_SHUTDOWN kilidi, uzak istemci için
elevation guard davranışı (birim düzeyi, sahte request ile).
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from jarvis_agent import auth, config, twofa
from jarvis_agent.api.routes_critical import require_elevation
from jarvis_agent.app import create_app
from jarvis_agent.store import database

SECRET = "test-secret-please-change-0123456789abcdef"


@pytest.fixture(autouse=True)
def _patch_secret(monkeypatch):
    """Modüldeki tüm testler için JWT secret'ı garanti eder (birim testler dahil)."""
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)


def _connect_to(path):
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(database, "connect", lambda: _connect_to(db_path))
    monkeypatch.setattr(config, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(config, "ALLOW_SHUTDOWN", False)
    # Dosya aktarımı hermetik: gerçek Downloads/JarvisFiles'a dokunma.
    monkeypatch.setenv("JARVIS_FILES_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("JARVIS_UPLOADS_DIR", str(tmp_path / "files"))
    app = create_app()
    with TestClient(app) as c:
        yield c


def _elevate(client) -> str:
    """Prepare → confirm akışıyla geçerli bir elevation token'ı alır."""
    prep = client.post("/api/2fa/prepare")
    assert prep.status_code == 200
    body = prep.json()
    assert body["otp"] and len(body["otp"]) == 6
    conf = client.post(
        "/api/2fa/confirm",
        json={"challenge_id": body["challenge_id"], "otp": body["otp"]},
    )
    assert conf.status_code == 200
    token = conf.json()["elevated_token"]
    assert token and conf.json()["expires_in"] > 0
    return token


# ── 2FA akışı ────────────────────────────────────────────────────────────────

def test_prepare_confirm_returns_elevation(client):
    assert _elevate(client)


def test_wrong_otp_returns_400(client):
    body = client.post("/api/2fa/prepare").json()
    wrong = f"{(int(body['otp']) + 1) % 1_000_000:06d}"  # garanti yanlış
    resp = client.post(
        "/api/2fa/confirm", json={"challenge_id": body["challenge_id"], "otp": wrong}
    )
    assert resp.status_code == 400


def test_unknown_challenge_returns_400(client):
    resp = client.post(
        "/api/2fa/confirm", json={"challenge_id": "yok-bole-bir-id-0000", "otp": "123456"}
    )
    assert resp.status_code == 400


def test_three_wrong_attempts_burns_challenge(client):
    body = client.post("/api/2fa/prepare").json()
    wrong = f"{(int(body['otp']) + 1) % 1_000_000:06d}"
    for _ in range(3):
        client.post("/api/2fa/confirm", json={"challenge_id": body["challenge_id"], "otp": wrong})
    # Doğru OTP bile yakılmış challenge ile kabul edilmez.
    resp = client.post(
        "/api/2fa/confirm", json={"challenge_id": body["challenge_id"], "otp": body["otp"]}
    )
    assert resp.status_code == 429


def test_elevation_token_binds_to_user():
    token = auth.make_token("u1", "elevation", 120)
    assert twofa.verify_elevation(token, "u1")
    assert not twofa.verify_elevation(token, "u2")
    assert not twofa.verify_elevation("", "u1")


# ── Dosya silme (kritik uç) ──────────────────────────────────────────────────

def test_delete_file_from_loopback_works(client):
    up = client.post(
        "/api/files/upload",
        files={"file": ("notlar.txt", b"selam", "text/plain")},
    )
    assert up.status_code == 200
    deleted = client.delete("/api/files/notlar.txt")
    assert deleted.status_code == 200 and deleted.json()["deleted"] == "notlar.txt"
    again = client.delete("/api/files/notlar.txt")
    assert again.status_code == 404


# ── Shutdown (en kritik uç) ──────────────────────────────────────────────────

def test_shutdown_without_elevation_is_403(client):
    resp = client.post("/api/system/shutdown")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "2fa_elevation_required"


def test_shutdown_with_elevation_but_disabled_is_503(client):
    token = _elevate(client)
    resp = client.post("/api/system/shutdown", headers={"X-Elevation-Token": token})
    assert resp.status_code == 503


def test_shutdown_enabled_calls_popen(client, monkeypatch):
    token = _elevate(client)
    monkeypatch.setattr(config, "ALLOW_SHUTDOWN", True)
    called = {}

    class _FakePopen:
        def __init__(self, *args, **kwargs):
            called["args"] = args

    import subprocess as subprocess_module

    monkeypatch.setattr(subprocess_module, "Popen", _FakePopen)
    resp = client.post("/api/system/shutdown", headers={"X-Elevation-Token": token})
    assert resp.status_code == 200
    assert called["args"]


# ── Uzak istemci guard'ı (birim düzeyi, sahte request) ──────────────────────

class _Client:
    def __init__(self, host: str):
        self.host = host


class _State:
    def __init__(self, user=None, device=None):
        self.user = user
        self.device = device
        self.owner = ""


class _Req:
    def __init__(self, host, user=None, device=None, headers=None):
        self.client = _Client(host)
        self.state = _State(user, device)
        # Gerçek Starlette Headers gibi case-insensitive olmalı.
        self.headers = Headers(headers or {})
        self.query_params = {}


def test_remote_user_without_elevation_is_403():
    req = _Req("192.168.1.9", user={"id": "u1"})
    with pytest.raises(HTTPException) as ei:
        require_elevation(req)
    assert ei.value.status_code == 403


def test_remote_device_without_login_is_403():
    req = _Req("192.168.1.9", device={"device_id": "d1"})
    with pytest.raises(HTTPException) as ei:
        require_elevation(req)
    assert ei.value.status_code == 403


def test_remote_user_with_valid_elevation_passes():
    token = auth.make_token("u1", "elevation", 120)
    req = _Req("192.168.1.9", user={"id": "u1"}, headers={"X-Elevation-Token": token})
    require_elevation(req)  # raise etmemeli