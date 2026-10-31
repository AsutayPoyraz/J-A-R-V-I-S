"""Özellik 5 testleri: kullanıcı adı auth + API anahtarları (Fernet)."""
from __future__ import annotations

import sqlite3

from jarvis_agent.llm import router as llm_router
from jarvis_agent.store import user_keys


def _register_username(client, username="testuser"):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "first_name": "Test",
            "last_name": "Kullanıcı",
            "password": "Sifre12345",
            "password_repeat": "Sifre12345",
        },
    )


# ══ Özellik 5A: kullanıcı adı akışı ══════════════════════════════════════════

def test_username_register_login_flow(rig):
    client, _ = rig
    resp = _register_username(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"] and body["username"] == "testuser"
    login = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "Sifre12345"}
    )
    assert login.status_code == 200 and login.json()["access_token"]
    bad = client.post(
        "/api/auth/register",
        json={"username": "ab", "first_name": "A", "last_name": "B",
              "password": "Sifre12345"},
    )
    assert bad.status_code == 422
    invalid = client.post(
        "/api/auth/register",
        json={"username": "kullanıcı adı!", "first_name": "A", "last_name": "B",
              "password": "Sifre12345"},
    )
    assert invalid.status_code == 422
    assert _register_username(client).status_code == 409
    mismatch = client.post(
        "/api/auth/register",
        json={"username": "xuser1", "first_name": "A", "last_name": "B",
              "password": "Sifre12345", "password_repeat": "Farkli12345"},
    )
    assert mismatch.status_code == 422
    wrong = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "YanlisSifre1"}
    )
    assert wrong.status_code == 401


# ══ Özellik 5B: API anahtarları (Fernet şifreli) ═════════════════════════════

def test_user_api_keys_crud_and_encryption(rig):
    client, db_path = rig
    resp = _register_username(client, "keyuser")
    token = resp.json()["access_token"]
    user_id = resp.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    put = client.put(
        "/api/user/api-keys/GROQ_API_KEY",
        json={"value": "gsk_test_123456"},
        headers=headers,
    )
    assert put.status_code == 200
    listing = client.get("/api/user/api-keys", headers=headers).json()
    item = next(k for k in listing["keys"] if k["key_name"] == "GROQ_API_KEY")
    assert item["has_value"] is True
    assert all(not k.get("value") for k in listing["keys"])  # değer sızmaz
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT key_value FROM user_api_keys WHERE key_name = 'GROQ_API_KEY'"
    ).fetchone()
    conn.close()
    assert row and row[0].startswith("gAAAA")     # Fernet formatı
    assert "gsk_test_123456" not in row[0]        # düz metin DEĞİL
    assert user_keys.get_key(user_id, "GROQ_API_KEY") == "gsk_test_123456"
    assert client.delete(
        "/api/user/api-keys/GROQ_API_KEY", headers=headers
    ).status_code == 200
    assert client.put(
        "/api/user/api-keys/UNKNOWN_KEY", json={"value": "x"}, headers=headers
    ).status_code == 422


def test_user_api_keys_require_login(rig):
    client, _ = rig
    resp = client.get("/api/user/api-keys")
    assert resp.status_code == 401
    assert "giriş" in resp.json()["detail"].lower()


def test_user_keys_resolve_llm_priority(rig):
    """Öncelik: user_api_keys (DB) > .env (Özellik 5B.15)."""
    client, _ = rig
    resp = _register_username(client, "priouser")
    token = resp.json()["access_token"]
    user_id = resp.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/api/user/api-keys/GEMINI_API_KEY",
        json={"value": "user_gemini_key"},
        headers=headers,
    )
    assert llm_router.is_configured("gemini", user_id) is True
    provider = llm_router.build_provider_for("gemini", user_id)
    assert provider.api_key == "user_gemini_key"
    import pytest as _pytest
    from jarvis_agent.llm.provider import ProviderError

    with _pytest.raises(ProviderError):
        llm_router.build_provider_for("deepseek", user_id)
