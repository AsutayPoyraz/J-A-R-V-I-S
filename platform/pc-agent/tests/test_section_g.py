"""Bölüm G testleri — madde 25 (gizlilik/izinler/denetim), madde 26 (widget sırası,
kişilik), madde 27 (mood, günlük limit) ve madde 31 (Sentry scrub).

Her test hermetiktir: DB geçici dosyada (database.connect monkeypatch).
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config, security
from jarvis_agent.app import create_app
from jarvis_agent.store import database, section_g

ALICE = {"X-Client-ID": "client-alice-g1g2g3g4"}
BOB = {"X-Client-ID": "client-bob-b1b2c3d4"}
ALICE_OWNER = "client:client-alice-g1g2g3g4"


def _connect_to(path):
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@pytest.fixture()
def rig(monkeypatch, tmp_path):
    db_path = tmp_path / "test_g.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(database, "connect", lambda: _connect_to(db_path))
    return create_app(), db_path


def _local_client(app):
    return TestClient(app)


def _guest_client(app, monkeypatch):
    monkeypatch.setattr(security, "is_loopback", lambda host: False)
    return TestClient(app)


# ── Madde 25: gizli notlar (istemci şifreli, sunucu opak) ────────────────────

def test_secure_notes_crud_and_isolation(rig):
    app, _ = rig
    with _local_client(app) as client:
        nid = client.post(
            "/api/privacy/notes",
            json={"title_cipher": "aGVsbG8=", "body_cipher": "dGluaXI="},
            headers=ALICE,
        ).json()["id"]
        notes = client.get("/api/privacy/notes", headers=ALICE).json()["notes"]
        assert len(notes) == 1 and notes[0]["id"] == nid
        # Bob kendi listesinde Alice'in notunu GÖREMEZ (owner izolasyonu)
        assert client.get("/api/privacy/notes", headers=BOB).json()["notes"] == []
        assert client.delete(f"/api/privacy/notes/{nid}", headers=ALICE).json()["deleted"] is True
        assert client.get("/api/privacy/notes", headers=ALICE).json()["notes"] == []
        # Olmayan not → 404
        assert client.delete("/api/privacy/notes/9999", headers=ALICE).status_code == 404


def test_secure_notes_guest_forbidden(rig, monkeypatch):
    app, _ = rig
    with _guest_client(app, monkeypatch) as client:
        assert client.get("/api/privacy/notes").status_code == 403


# ── Madde 25: izin yönetimi + require_permission zorlaması ───────────────────

def test_permissions_get_set_and_enforcement(rig):
    app, _ = rig
    with _local_client(app) as client:
        perms = client.get("/api/privacy/permissions", headers=ALICE).json()
        assert "shutdown" in perms["known"]
        assert perms["permissions"]["shutdown"] is True  # varsayılan açık
        # Kapat → shutdown ucu 403 (code=permission_denied)
        assert client.put(
            "/api/privacy/permissions/shutdown", json={"allowed": False}, headers=ALICE
        ).json()["allowed"] is False
        denied = client.post("/api/system/shutdown", headers=ALICE)
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "permission_denied"
        # files.read kapat → liste ucu 403
        client.put("/api/privacy/permissions/files.read", json={"allowed": False}, headers=ALICE)
        assert client.get("/api/files", headers=ALICE).status_code == 403
        # Bilinmeyen izin anahtarı → 422
        assert client.put(
            "/api/privacy/permissions/root", json={"allowed": True}, headers=ALICE
        ).status_code == 422


# ── Madde 25: güvenlik denetim kaydı + CSV dışa aktarma ──────────────────────

def test_audit_log_and_csv_export(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.put("/api/privacy/permissions/camera", json={"allowed": False}, headers=ALICE)
        entries = client.get("/api/privacy/audit", headers=ALICE).json()["entries"]
        assert any(e["event_type"] == "privacy.permission_changed" for e in entries)
        # İzolasyon: Bob'un denetimi boş
        assert client.get("/api/privacy/audit", headers=BOB).json()["entries"] == []
        # CSV indirme
        csv_resp = client.get("/api/privacy/audit/export.csv", headers=ALICE)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert csv_resp.text.startswith("created_at,event_type,detail,ip")
        assert "privacy.permission_changed" in csv_resp.text


# ── Madde 26: sürükle-bırak widget sırası + kişilik + erişilebilirlik ────────

def test_dashboard_layout_and_persona_and_a11y(rig):
    app, _ = rig
    with _local_client(app) as client:
        # Widget sırası: bilinmeyen widget atılır, tekrarlar tekilleşir.
        r = client.put(
            "/api/settings",
            json={"dashboard_layout": ["weather", "bilinmeyen", "social", "weather"]},
            headers=ALICE,
        )
        assert r.status_code == 200
        s = client.get("/api/settings", headers=ALICE).json()
        layout = s["dashboard_layout"]
        # Sıra korunur, bilinmeyen atılır, tekrar tekilleşir; eksikler sona eklenir.
        assert layout[:2] == ["weather", "social"]
        assert "bilinmeyen" not in layout
        assert len(layout) == len(set(layout))
        assert set(config.ALLOWED_WIDGETS) <= set(layout)
        # Kişilik: geçerli stil kaydedilir, geçersiz stil 422.
        assert client.put(
            "/api/settings",
            json={"persona_style": "friendly", "persona_name": "Bay Jarvis"},
            headers=ALICE,
        ).status_code == 200
        s = client.get("/api/settings", headers=ALICE).json()
        assert s["persona_style"] == "friendly" and s["persona_name"] == "Bay Jarvis"
        assert client.put(
            "/api/settings", json={"persona_style": "sarcastic"}, headers=ALICE
        ).status_code == 422
        # Erişilebilirlik: font ölçeği 0.8-1.5 aralığında; disleksi/kontrast bool.
        assert client.put(
            "/api/settings", json={"font_scale": 2.0}, headers=ALICE
        ).status_code == 422
        assert client.put(
            "/api/settings",
            json={"font_scale": 1.25, "dyslexic_font": True, "high_contrast": True},
            headers=ALICE,
        ).status_code == 200
        s = client.get("/api/settings", headers=ALICE).json()
        assert s["font_scale"] == 1.25 and s["dyslexic_font"] and s["high_contrast"]


# ── Madde 27: mood, mola, odak, günlük limit (chat 429) ──────────────────────

def test_mood_and_wellbeing(rig, monkeypatch):
    app, _ = rig
    with _local_client(app) as client:
        wb = client.get("/api/health/wellbeing", headers=ALICE).json()
        assert wb["mood"] == "neutral" and "focused" in wb["moods"]
        assert wb["used_seconds"] == 0 and wb["used_minutes"] == 0
        # Geçerli mood → user_settings'e de yazılır (chat prompt'u oradan okur).
        assert client.put(
            "/api/health/mood", json={"mood": "focused"}, headers=ALICE
        ).json()["mood"] == "focused"
        assert client.get("/api/settings", headers=ALICE).json()["mood"] == "focused"
        # Geçersiz mood → 422; misafir → 403.
        assert client.put(
            "/api/health/mood", json={"mood": "angry"}, headers=ALICE
        ).status_code == 422
        with _guest_client(app, monkeypatch) as gclient:
            assert gclient.get("/api/health/wellbeing").status_code == 403


def test_daily_usage_limit_blocks_chat(rig):
    app, _ = rig
    with _local_client(app) as client:
        # Limit 1 dk; 120 sn kullanım simüle et → limit_reached.
        assert client.put(
            "/api/settings", json={"daily_limit_minutes": 1}, headers=ALICE
        ).status_code == 200
        section_g.touch_usage(ALICE_OWNER, delta_seconds=120)
        wb = client.get("/api/health/wellbeing", headers=ALICE).json()
        assert wb["used_minutes"] == 2 and wb["used_seconds"] == 120
        blocked = client.post("/api/chat", json={"message": "merhaba"}, headers=ALICE)
        assert blocked.status_code == 429
        # Misafir limit dışıdır (kayıt üretilmez) — şifreli not ucuna benzer.


def test_wellness_settings_validation(rig):
    app, _ = rig
    with _local_client(app) as client:
        assert client.put(
            "/api/settings", json={"break_reminder_minutes": 300}, headers=ALICE
        ).status_code == 422
        assert client.put(
            "/api/settings",
            json={"break_reminder_minutes": 45, "focus_mode": True,
                  "privacy_mode": True, "auto_lock_minutes": 5},
            headers=ALICE,
        ).status_code == 200
        s = client.get("/api/settings", headers=ALICE).json()
        assert s["break_reminder_minutes"] == 45
        assert s["focus_mode"] and s["privacy_mode"] and s["auto_lock_minutes"] == 5


# ── Madde 31: Sentry before_send scrub (hassas alan filtresi) ────────────────

def test_sentry_scrub_filters_secrets():
    from jarvis_agent.observability import scrub_event

    event = {
        "request": {
            "headers": {"Authorization": "Bearer abc", "X-Ok": "keep-me"},
            "password": "s3cret",
            "user": {"token": "t", "name": "ali"},
        },
        "extra": {"body_cipher": "gizli-not", "note": "serbest"},
    }
    out = scrub_event(event)
    assert out["request"]["headers"]["Authorization"] == "[filtered]"
    assert out["request"]["headers"]["X-Ok"] == "keep-me"
    assert out["request"]["password"] == "[filtered]"
    assert out["request"]["user"]["token"] == "[filtered]"
    assert out["request"]["user"]["name"] == "ali"
    assert out["extra"]["body_cipher"] == "[filtered]"
    assert out["extra"]["note"] == "serbest"
    # 2000+ karakterlik string kırpılır (paket şişmesin).
    assert scrub_event({"s": "x" * 3000})["s"].endswith("…[truncated]")
