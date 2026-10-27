"""FAZ 2 — 32 madde test matrisi için ek doğrulamalar.

Kapsam (mevcut test dosyalarında bulunmayan kritik akışlar):
- Madde 2: 6 haneli PIN eşleştirme kodunun formatı, TTL'i, tek kullanımlılığı
  ve 5 hatalı denemede blok davranışı.
- Madde 30: dosya yüklemede tehlikeli uzantı engeli (.exe → 400), boyut
  sınırı (413) ve izin verilen uzantının kabulü.
- Madde 21: XP'nin istemci tarafından yazılamaması (sunucu tarafı XP).
"""
from __future__ import annotations

import re
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config, security
from jarvis_agent.app import create_app
from jarvis_agent.integrations import files as files_module
from jarvis_agent.api import routes_files

ALICE = {"X-Client-ID": "client-alice-12345678"}


def _connect_to(path):
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@pytest.fixture()
def rig(monkeypatch, tmp_path):
    """(app, db_path) döndürür; mevcut test dosyalarıyla aynı desen."""
    db_path = tmp_path / "matrix.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(database, "connect", lambda: _connect_to(db_path))
    return create_app(), db_path, monkeypatch, tmp_path


from jarvis_agent.store import database  # noqa: E402  (rig docstring'iyle aynı)


# ── Madde 2: QR + 6 haneli PIN eşleştirme ────────────────────────────────────

def test_pair_code_is_6_digits_with_5min_ttl(rig):
    app, _, _, _ = rig
    with TestClient(app) as client:
        info = client.post("/api/pair/start").json()
        assert re.fullmatch(r"\d{6}", info["code"]), "kod 6 haneli olmalı"
        assert info["expires_in"] == 300, "kod 5 dakika geçerli olmalı"


def test_pair_claim_success_then_single_use(rig):
    app, _, _, _ = rig
    with TestClient(app) as client:
        code = client.post("/api/pair/start").json()["code"]
        ok = client.post("/api/pair/claim", json={"code": code, "device_name": "Pixel"})
        assert ok.status_code == 200
        body = ok.json()
        assert body["device_token"] and body["device_id"]
        # Aynı kod ikinci kez kullanılamaz (tek kullanımlık).
        assert client.post("/api/pair/claim", json={"code": code}).status_code == 400


def test_pair_claim_expired_code_rejected(rig):
    app, _, _, _ = rig
    with TestClient(app) as client:
        code = client.post("/api/pair/start").json()["code"]
        # Kodun süresini geçmişe çek (TTL sonrası davranış).
        security._pending_code["expires_at"] = time.time() - 1
        assert client.post("/api/pair/claim", json={"code": code}).status_code == 400


def test_pair_five_wrong_attempts_block_correct_code_too(rig):
    app, _, _, _ = rig
    with TestClient(app) as client:
        code = client.post("/api/pair/start").json()["code"]
        for _ in range(5):
            assert client.post("/api/pair/claim", json={"code": "000000"}).status_code == 400
        # 5 hatalı deneme sonrası DOĞRU kod da geçici olarak reddedilir.
        assert client.post("/api/pair/claim", json={"code": code}).status_code == 400


# ── Madde 30: dosya yükleme limitleri ────────────────────────────────────────

def test_upload_rejects_dangerous_extension(rig):
    app, _, monkeypatch, tmp_path = rig
    monkeypatch.setattr(files_module, "uploads_dir", lambda: tmp_path)
    monkeypatch.setattr(routes_files, "_notify_pc", lambda result: None)
    with TestClient(app) as client:
        resp = client.post(
            "/api/files/upload",
            files={"file": ("kotu.exe", b"MZ...", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "uzant" in resp.json()["detail"].lower()


def test_upload_rejects_oversize(rig):
    app, _, monkeypatch, tmp_path = rig
    monkeypatch.setattr(files_module, "uploads_dir", lambda: tmp_path)
    monkeypatch.setattr(files_module, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(routes_files, "_notify_pc", lambda result: None)
    with TestClient(app) as client:
        resp = client.post(
            "/api/files/upload",
            files={"file": ("buyuk.png", b"x" * 2048, "image/png")},
        )
        assert resp.status_code == 413


def test_upload_accepts_allowed_extension(rig):
    app, _, monkeypatch, tmp_path = rig
    monkeypatch.setattr(files_module, "uploads_dir", lambda: tmp_path)
    monkeypatch.setattr(routes_files, "_notify_pc", lambda result: None)
    with TestClient(app) as client:
        resp = client.post(
            "/api/files/upload",
            files={"file": ("not.png", b"\x89PNG\r\n", "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["name"].endswith(".png")


# ── Madde 21: XP sunucu tarafında — istemci yazamaz ──────────────────────────

def test_xp_cannot_be_written_by_client(rig):
    app, _, _, _ = rig
    with TestClient(app) as client:
        before = client.get("/api/gamify", headers=ALICE).json()
        # XP yazma ucu yok: POST → 405 (manipülasyon engeli).
        resp = client.post("/api/gamify", json={"xp": 999999}, headers=ALICE)
        assert resp.status_code == 405
        after = client.get("/api/gamify", headers=ALICE).json()
        assert after["xp_total"] == before["xp_total"]


# ── Madde 12: cihaz algılama ─────────────────────────────────────────────────

def test_parse_user_agent_types(rig):
    from jarvis_agent.api.routes_system import parse_user_agent

    iphone = parse_user_agent(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1"
    )
    assert iphone["device_type"] == "mobile"
    assert iphone["os"] == "iOS"
    assert iphone["browser"] == "Safari"

    desktop = parse_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    assert desktop["device_type"] == "desktop"
    assert desktop["os"] == "Windows 10/11"
    assert desktop["browser"] == "Chrome"

    tablet = parse_user_agent(
        "Mozilla/5.0 (iPad; CPU OS 16_3 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
    )
    assert tablet["device_type"] == "tablet"


def test_device_endpoint_uses_request_ua(rig):
    app, _, _, _ = rig
    with TestClient(app) as client:
        resp = client.get(
            "/api/system/device",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) Mobile Safari/604.1"},
        )
        assert resp.status_code == 200
        assert resp.json()["device_type"] == "mobile"

