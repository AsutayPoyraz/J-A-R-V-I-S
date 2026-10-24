"""Bölüm F testleri — Smart File Manager/sesli not (19), paylaşılan oturum + makro (20),
XP/seviye/rozet (21), analitik ve dışa aktarma (24).

Her test hermetiktir: DB geçici dosyada (database.connect monkeypatch).
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

from jarvis_agent import config, security
from jarvis_agent.app import create_app
from jarvis_agent.store import database, section_f

ALICE = {"X-Client-ID": "client-alice-f1f2f3f4"}
BOB = {"X-Client-ID": "client-bob-a1b2c3d4"}
ALICE_OWNER = "client:client-alice-f1f2f3f4"


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
    return create_app(), db_path


def _local_client(app):
    return TestClient(app)


def _guest_client(app, monkeypatch):
    monkeypatch.setattr(security, "is_loopback", lambda host: False)
    return TestClient(app)

# ── Madde 19: sesli notlar ───────────────────────────────────────────────────

def test_voice_notes_crud_and_search(rig):
    app, _ = rig
    with _local_client(app) as client:
        assert client.post("/api/voice-notes", json={"text": "Yarın doktor randevusu"}, headers=ALICE).json()["id"] > 0
        client.post("/api/voice-notes", json={"text": "Proje fikri: QR kiosk"}, headers=ALICE)
        found = client.get("/api/voice-notes", params={"q": "doktor"}, headers=ALICE).json()["notes"]
        assert len(found) == 1 and "doktor" in found[0]["text"]
        nid = found[0]["id"]
        assert client.delete(f"/api/voice-notes/{nid}", headers=ALICE).json()["deleted"] is True
        remaining = client.get("/api/voice-notes", headers=ALICE).json()["notes"]
        assert len(remaining) == 1 and remaining[0]["text"] == "Proje fikri: QR kiosk"


def test_voice_notes_owner_isolation(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/voice-notes", json={"text": "alice notu"}, headers=ALICE)
        assert client.get("/api/voice-notes", headers=BOB).json()["notes"] == []
        # Boş metin 422
        assert client.post("/api/voice-notes", json={"text": "  "}, headers=ALICE).status_code == 422


# ── Madde 19: dosya etiketleri ───────────────────────────────────────────────

def test_file_tags_set_and_get(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.put("/api/files/tags/rapor.pdf", json={"tags": ["İş", " 2026 "]}, headers=ALICE)
        client.put("/api/files/tags/ozet.txt", json={"tags": ["kişisel"]}, headers=ALICE)
        tags = client.get("/api/files/tags", headers=ALICE).json()["tags"]
        assert tags["rapor.pdf"] == ["iş", "2026"]
        assert "ozet.txt" in tags
        # Bob'un etiketleri boş (izolasyon)
        assert client.get("/api/files/tags", headers=BOB).json()["tags"] == {}


# ── Madde 19: Cloud Backup MVP (zip dışa/içe) ────────────────────────────────

def test_backup_export_and_import_roundtrip(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/voice-notes", json={"text": "yedeklenecek not"}, headers=ALICE)
        client.put("/api/files/tags/a.pdf", json={"tags": ["x"]}, headers=ALICE)
        resp = client.get("/api/backup/export", headers=ALICE)
        assert resp.status_code == 200 and resp.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            payload = json.loads(zf.read("backup.json").decode("utf-8"))
        assert payload["owner"] == ALICE_OWNER
        assert any("yedeklenecek not" in n["text"] for n in payload["voice_notes"])

        # Yedeği başka owner'a (Bob) geri yükle
        imp = client.post("/api/backup/import", json={"data": payload}, headers=BOB)
        assert imp.status_code == 200 and imp.json()["imported"]["voice_notes"] == 1
        bob_notes = client.get("/api/voice-notes", headers=BOB).json()["notes"]
        assert any("yedeklenecek not" in n["text"] for n in bob_notes)
# ── Madde 20: makrolar ───────────────────────────────────────────────────────

def test_macros_crud_and_duplicate(rig):
    app, _ = rig
    with _local_client(app) as client:
        mid = client.post(
            "/api/macros", json={"name": "Sabah rutini", "steps": [{"action": "open", "target": "chrome"}]},
            headers=ALICE,
        ).json()["id"]
        assert mid > 0
        # Aynı isim → 409
        assert client.post("/api/macros", json={"name": "Sabah rutini", "steps": []}, headers=ALICE).status_code == 409
        macros = client.get("/api/macros", headers=ALICE).json()["macros"]
        assert len(macros) == 1 and macros[0]["steps"][0]["action"] == "open"
        assert client.delete(f"/api/macros/{mid}", headers=ALICE).json()["deleted"] is True
        assert client.get("/api/macros", headers=ALICE).json()["macros"] == []


# ── Madde 20: paylaşılan oturumlar ───────────────────────────────────────────

def test_shared_session_flow_and_permissions(rig):
    app, _ = rig
    with _local_client(app) as client:
        code = client.post("/api/shared/sessions", json={"title": "toplantı"}, headers=ALICE).json()["code"]
        assert len(code) == 6

        # Host kendi oturumunu görebilir
        info = client.get(f"/api/shared/sessions/{code}", headers=ALICE).json()
        assert info["title"] == "toplantı"

        # Yabancı (Bob, üye değil) oturumu göremez → 403
        assert client.get(f"/api/shared/sessions/{code}", headers=BOB).status_code == 403

        # Bob katılır
        assert client.post(f"/api/shared/members/{code}", json={"display_name": "Bob"}, headers=BOB).json()["joined"] is True

        # İki üye mesaj yazıp okuyabilir
        assert client.post(
            f"/api/shared/sessions/{code}/messages",
            json={"content": "merhaba ekip", "display_name": "Alice"}, headers=ALICE,
        ).json()["id"] > 0
        assert client.post(
            f"/api/shared/sessions/{code}/messages",
            json={"content": "selam!", "display_name": "Bob"}, headers=BOB,
        ).json()["id"] > 0
        msgs = client.get(f"/api/shared/sessions/{code}/messages", headers=BOB).json()["messages"]
        assert [m["content"] for m in msgs] == ["merhaba ekip", "selam!"]

        # since_id ile artımlı okuma
        msgs2 = client.get(
            f"/api/shared/sessions/{code}/messages", params={"since_id": msgs[0]["id"]}, headers=ALICE
        ).json()["messages"]
        assert [m["content"] for m in msgs2] == ["selam!"]

        # Var olmayan oturum → 404
        assert client.get("/api/shared/sessions/ZZZZZZ", headers=ALICE).status_code == 404

        # Silme: üye (Bob) silemez, host silebilir
        assert client.delete(f"/api/shared/sessions/{code}", headers=BOB).status_code == 403
        assert client.delete(f"/api/shared/sessions/{code}", headers=ALICE).json()["deleted"] is True
# ── Madde 21: XP / seviye / rozet / leaderboard ──────────────────────────────

def test_xp_awarded_by_actions_and_gamify_status(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/voice-notes", json={"text": "xp notu 1"}, headers=ALICE)
        client.post("/api/macros", json={"name": "m1", "steps": []}, headers=ALICE)
        status = client.get("/api/gamify", headers=ALICE).json()
        # voice_note=4 + macro=3 → 7 XP, seviye 1
        assert status["xp_total"] == 7 and status["level"] == 1
        assert status["today_xp"] == 7
        assert status["counts"]["voice_note"] == 1
        # Rozetler: ilk makro + ilk sesli not etkisi (voice_10 henüz yok)
        codes = {b["code"] for b in status["badges"]}
        assert "first_macro" in codes and "voice_10" not in codes
        # Günlük görevler doldu mu
        tasks = {t["code"]: t["done"] for t in status["daily_tasks"]}
        assert tasks["voice1"] == 1 and tasks["macro1"] == 1


def test_xp_daily_cap_and_leaderboard(rig):
    app, _ = rig
    with _local_client(app) as client:
        # 25 sesli not → günlük tavan (20 olay) sonrası XP artmaz
        for i in range(25):
            client.post("/api/voice-notes", json={"text": f"not {i}"}, headers=ALICE)
        status = client.get("/api/gamify", headers=ALICE).json()
        assert status["counts"]["voice_note"] == 20  # tavan sonrası kayıt bile yazılmaz
        assert status["xp_total"] == 20 * section_f.XP_POINTS["voice_note"]

        # Leaderboard: kayıtlı kullanıcı yoksa boş; XP bununla manipüle EDİLEMEZ
        leaders = client.get("/api/gamify/leaderboard").json()["leaders"]
        assert isinstance(leaders, list)
        # İstemciye XP yazma ucu yok: POST /api/gamify → 405
        assert client.post("/api/gamify", json={"xp": 99999}, headers=ALICE).status_code == 405
        assert client.get("/api/gamify", headers=ALICE).json()["xp_total"] == 80


# ── Misafir kısıtları (Bölüm B kuralı: misafir kalıcı kayıt bırakamaz) ───────

def test_guest_cannot_use_section_f_features(rig, monkeypatch):
    app, _ = rig
    with _guest_client(app, monkeypatch) as client:
        # Tüm kalıcı kayıt gerektiren uçlar misafire kapalı (403)
        assert client.post("/api/voice-notes", json={"text": "misafir notu"}).status_code == 403
        assert client.post("/api/macros", json={"name": "g", "steps": []}).status_code == 403
        assert client.post("/api/shared/sessions", json={"title": "g"}).status_code == 403
        assert client.get("/api/gamify").status_code == 403
        assert client.get("/api/analytics/summary").status_code == 403
        assert client.get("/api/backup/export").status_code == 403


# ── Madde 20: etkinlik akışı (Activity Feed, son 7 gün) ──────────────────────

def test_activity_feed_records_events(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/macros", json={"name": "feed-m", "steps": []}, headers=ALICE)
        client.post("/api/voice-notes", json={"text": "feed n"}, headers=ALICE)
        with database.closing(database.connect()) as conn:
            rows = conn.execute(
                "SELECT kind FROM activity_log WHERE owner_id = ? ORDER BY id DESC",
                (ALICE_OWNER,),
            ).fetchall()
        kinds = {r["kind"] for r in rows}
        assert "macro.create" in kinds and "voice_note.add" in kinds


# ── Madde 24: analitik, geçmiş arama, dışa aktarma ───────────────────────────

def test_analytics_summary_and_history_search(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/voice-notes", json={"text": "toplantı notu"}, headers=ALICE)
        client.post("/api/macros", json={"name": "m2", "steps": []}, headers=ALICE)
        client.put("/api/files/tags/rapor.pdf", json={"tags": ["iş"]}, headers=ALICE)

        summary = client.get("/api/analytics/summary", params={"days": 7}, headers=ALICE).json()
        assert summary["totals"]["voice_note"] >= 1
        assert summary["totals"]["macro"] >= 1
        assert all("date" in d for d in summary["days"])

        # Birleşik arama: metin + etiket
        hits = client.get("/api/history/search", params={"q": "toplantı"}, headers=ALICE).json()["results"]
        assert any(h["source"] == "voice_note" for h in hits)
        tagged = client.get("/api/history/search", params={"tag": "iş"}, headers=ALICE).json()["results"]
        assert any(h["source"] == "file" and "rapor.pdf" in h["text"] for h in tagged)

        # Tarih aralığı: gelecek tarih filtresi sonuçları boşaltır
        none = client.get(
            "/api/history/search",
            params={"q": "toplantı", "date_from": "2099-01-01"}, headers=ALICE,
        ).json()["results"]
        assert none == []


def test_export_json_and_csv(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/voice-notes", json={"text": "csv satırı"}, headers=ALICE)
        js = client.get("/api/analytics/export", params={"format": "json"}, headers=ALICE)
        assert js.status_code == 200 and "jarvis-analytics.json" in js.headers["content-disposition"]
        payload = json.loads(js.content.decode("utf-8"))
        assert "totals" in payload and "days" in payload

        csv = client.get("/api/analytics/export", params={"format": "csv"}, headers=ALICE)
        assert "date," in csv.text and "voice_note" in csv.text
# ── Madde 19: dosya arama (isim + etiket) ────────────────────────────────────

def test_file_search_by_name_and_tag(rig, monkeypatch, tmp_path):
    app, _ = rig
    fdir = tmp_path / "files"
    fdir.mkdir()
    (fdir / "rapor.pdf").write_bytes(b"%PDF-1.4 fake")
    (fdir / "foto.png").write_bytes(b"\x89PNG fake")
    # files.shared_dir() çağrı anında env'den okur → hermetik klasör
    monkeypatch.setenv("JARVIS_FILES_DIR", str(fdir))
    with _local_client(app) as client:
        client.put("/api/files/tags/rapor.pdf", json={"tags": ["iş"]}, headers=ALICE)
        res = client.get("/api/files/search", params={"q": "rapor"}, headers=ALICE).json()
        assert [r["name"] for r in res["results"]] == ["rapor.pdf"]
        assert res["results"][0]["tags"] == ["iş"]
        tagged = client.get("/api/files/search", params={"tag": "iş"}, headers=ALICE).json()
        assert len(tagged["results"]) == 1
        # Bob aynı dosyaları göremez (etiketleri yok → sonuç boş)
        assert client.get("/api/files/search", headers=BOB).json()["results"] == []


# ── Madde 20: Collaborative Notes MVP — Markdown dışa aktarma ────────────────
# Notion/OneNote API'leri bu ortamda kimlik doğrulamasız kullanılamaz; MVP
# olarak notlar Markdown'a aktarılır (rapor: KISMEN).

def test_collaborative_notes_export_markdown(rig):
    app, _ = rig
    with _local_client(app) as client:
        client.post("/api/notes", json={"title": "Toplantı", "content": "sprint planı"}, headers=ALICE)
        res = client.get("/api/notes/export", headers=ALICE)
        assert res.status_code == 200
        assert "text/markdown" in res.headers["content-type"]
        assert "Toplantı" in res.text and "sprint planı" in res.text