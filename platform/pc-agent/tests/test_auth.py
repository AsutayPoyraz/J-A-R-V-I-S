"""Kimlik doğrulama testleri (Prompt 1) — hermetik: tmp DB, gerçek ağ yok.

Kapsam: kayıt, çift kayıt 409, yanlış şifre, 5 hata → 429 + Retry-After,
süre bitince açılma, token süresi, refresh rotation, reset-password,
secret boşken 503 ve owner önceliği (user > device > client).
"""
from __future__ import annotations

import sqlite3
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from jarvis_agent import auth, config, security
from jarvis_agent.app import create_app
from jarvis_agent.store import database

SECRET = "test-secret-please-change-0123456789abcdef"
USER = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "birth_date": "1990-05-01",
    "password": "Sifre12345",
    "security_question": "İlk evcil hayvanınız?",
    "security_answer": "Pamuk",
}


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
    monkeypatch.setattr(config, "BCRYPT_ROUNDS", 4)  # test hızı
    app = create_app()
    with TestClient(app) as client:
        yield client, db_path


def _register(client, **overrides):
    payload = {**USER, **overrides}
    return client.post("/api/auth/register", json=payload)


# ── Kayıt ────────────────────────────────────────────────────────────────────

def test_register_returns_tokens_without_hashes(rig):
    client, _ = rig
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user_id"] and body["first_name"] == "Ada"
    raw = resp.text
    assert "hash" not in raw.lower() and "Pamuk" not in raw


def test_register_duplicate_is_409(rig):
    client, _ = rig
    assert _register(client).status_code == 201
    dup = _register(client, first_name="ada", last_name="LOVELACE")
    assert dup.status_code == 409


def test_register_rejects_short_password(rig):
    client, _ = rig
    assert _register(client, password="kisa").status_code == 422


# ── Giriş ve kilitleme ──────────────────────────────────────────────────────

def test_login_success_and_wrong_password(rig):
    client, _ = rig
    _register(client)
    ok = client.post(
        "/api/auth/login",
        json={"first_name": "Ada", "last_name": "Lovelace", "password": USER["password"]},
    )
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post(
        "/api/auth/login",
        json={"first_name": "Ada", "last_name": "Lovelace", "password": "yanlis123"},
    )
    assert bad.status_code == 401
    # Kullanıcı varlığı sızmaz: aynı mesaj var olmayan kullanıcı için de döner.
    missing = client.post(
        "/api/auth/login",
        json={"first_name": "Yok", "last_name": "Boyle", "password": "yanlis123"},
    )
    assert missing.status_code == 401
    assert missing.json()["detail"] == bad.json()["detail"]


def test_five_failures_lock_with_retry_after(rig):
    client, db_path = rig
    _register(client)
    payload = {"first_name": "Ada", "last_name": "Lovelace", "password": "yanlis123"}
    for _ in range(config.LOGIN_MAX_FAILURES):
        assert client.post("/api/auth/login", json=payload).status_code == 401
    locked = client.post("/api/auth/login", json=payload)
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0
    # Doğru şifre bile kilitliyken reddedilir.
    correct = client.post(
        "/api/auth/login",
        json={**payload, "password": USER["password"]},
    )
    assert correct.status_code == 429
    # Kilit SQLite'ta kalıcı: yeniden başlatma simülasyonu (yeni app) kilidi korur.
    app2 = create_app()
    with TestClient(app2) as fresh:
        again = fresh.post("/api/auth/login", json=payload)
    assert again.status_code == 429
    # Süre dolduğunda açılır.
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("UPDATE login_attempts SET blocked_until = ?", (time.time() - 1,))
    opened = client.post(
        "/api/auth/login",
        json={**payload, "password": USER["password"]},
    )
    assert opened.status_code == 200


def test_successful_login_resets_failure_counter(rig):
    client, _ = rig
    _register(client)
    bad = {"first_name": "Ada", "last_name": "Lovelace", "password": "yanlis123"}
    for _ in range(config.LOGIN_MAX_FAILURES - 1):
        client.post("/api/auth/login", json=bad)
    ok = client.post(
        "/api/auth/login", json={**bad, "password": USER["password"]}
    )
    assert ok.status_code == 200
    for _ in range(config.LOGIN_MAX_FAILURES - 1):
        assert client.post("/api/auth/login", json=bad).status_code == 401


# ── Token'lar ───────────────────────────────────────────────────────────────

def test_expired_access_token_rejected_remote(rig):
    client, _ = rig
    user_id = _register(client).json()["user_id"]
    expired = jwt.encode(
        {
            "sub": user_id,
            "typ": "access",
            "iat": time.time() - 100,
            "exp": time.time() - 10,
            "jti": "test-expired",
        },
        SECRET,
        algorithm="HS256",
    )
    # Uzak istemci: süresi dolmuş token → 401, kimliksiz devam edemez.
    assert security.is_user_token_valid(expired) is False
    # Uzak istemcide korumalı uç giriş ister.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(security, "is_loopback", lambda host: False)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_refresh_rotates_and_old_token_is_dead(rig):
    client, _ = rig
    tokens = _register(client).json()
    first = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new_access = first.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200 and me.json()["first_name"] == "Ada"
    # Aynı refresh tekrar kullanılamaz
    again = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


def test_access_token_cannot_be_used_as_refresh(rig):
    client, _ = rig
    tokens = _register(client).json()
    resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_logout_revokes_refresh(rig):
    client, _ = rig
    tokens = _register(client).json()
    assert client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


# ── Şifre sıfırlama ─────────────────────────────────────────────────────────

def test_reset_password_with_security_answer(rig):
    client, _ = rig
    _register(client)
    body = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "birth_date": "1990-05-01",
        "security_answer": "  PAMUK ",
        "new_password": "YeniSifre9876",
    }
    assert client.post("/api/auth/reset-password", json=body).status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"first_name": "Ada", "last_name": "Lovelace", "password": "YeniSifre9876"},
    )
    assert login.status_code == 200


def test_reset_password_wrong_answer_is_generic(rig):
    client, _ = rig
    _register(client)
    body = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "birth_date": "1990-05-01",
        "security_answer": "yanlis",
        "new_password": "YeniSifre9876",
    }
    wrong = client.post("/api/auth/reset-password", json=body)
    missing = client.post(
        "/api/auth/reset-password",
        json={**body, "first_name": "Yok", "last_name": "Boyle"},
    )
    assert wrong.status_code == 400 and missing.status_code == 400
    assert wrong.json()["detail"] == missing.json()["detail"]


# ── Secret yokluğu ──────────────────────────────────────────────────────────

def test_auth_endpoints_503_without_secret(rig, monkeypatch):
    client, _ = rig
    monkeypatch.setattr(config, "AUTH_SECRET", "")
    _register(client)  # kayıt için secret gerekiyor → 503
    resp = _register(client, first_name="Bob", last_name="Builder")
    assert resp.status_code == 503
    login = client.post(
        "/api/auth/login",
        json={"first_name": "Ada", "last_name": "Lovelace", "password": USER["password"]},
    )
    assert login.status_code == 503


def test_auth_available_reflects_secret(monkeypatch):
    monkeypatch.setattr(config, "AUTH_SECRET", "   ")
    assert auth.auth_available() is False
    with pytest.raises(auth.AuthUnavailable):
        auth.make_token("u1", "access", 60)


# ── Owner önceliği ──────────────────────────────────────────────────────────

class _Req:
    def __init__(self, user=None, device=None, headers=None, host="203.0.113.5"):
        from types import SimpleNamespace

        self.state = SimpleNamespace(owner=None, user=user, device=device)
        self.headers = headers or {}
        self.query_params = {}
        self.client = SimpleNamespace(host=host)


def test_owner_priority_user_first():
    user = {"id": "abc123"}
    device = {"device_id": "dev-1"}
    headers = {"x-client-id": "client-abcdefgh"}
    assert security.request_owner(_Req(user=user, device=device, headers=headers)) == "user:abc123"
    assert security.request_owner(_Req(device=device, headers=headers)) == "device:dev-1"
    assert security.request_owner(_Req(headers=headers)) == "client:client-abcdefgh"
    assert security.request_owner(_Req()) == "guest:anon"
    assert security.request_owner(_Req(host="127.0.0.1")) == "local"


def test_authenticated_remote_user_is_not_guest():
    req = _Req(user={"id": "abc123"}, host="203.0.113.5")
    assert security.is_guest(req) is False


# ── Entegrasyon: JWT sahibi kendi partisyonunda çalışır ─────────────────────

def test_chat_persists_under_user_partition(rig):
    client, db_path = rig
    tokens = _register(client).json()
    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-Client-ID": "client-somebody-1234",
    }
    assert client.post("/api/chat", json={"message": "merhaba"}, headers=headers).status_code == 200
    with sqlite3.connect(str(db_path)) as conn:
        owners = {
            row[0] for row in conn.execute("SELECT DISTINCT owner_id FROM messages").fetchall()
        }
    assert owners == {f"user:{tokens['user_id']}"}


def test_local_flow_stays_unauthenticated(rig):
    """Yerel masaüstü (loopback) davranışı bozulmaz: giriş olmadan owner='local'."""
    client, _ = rig
    assert client.get("/api/auth/me").status_code == 200  # loopback istisnası
    assert client.get("/api/settings").json()["background_color"]
