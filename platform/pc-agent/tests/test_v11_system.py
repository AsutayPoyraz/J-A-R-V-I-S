"""Özellik 3 + 4 + 11 + 13 + 17 + 19 testleri: kamera, pair, özet, trim, ATLAS."""
from __future__ import annotations

import socket
import sys


# ══ Özellik 3: kamera güvenli durum ══════════════════════════════════════════

def test_camera_status_enriched(rig):
    client, _ = rig
    data = client.get("/api/camera/status").json()
    assert set(data) >= {"opencv_installed", "camera_available", "disabled_by_env", "error"}


# ══ Özellik 4: pair debug + LAN taraması ═════════════════════════════════════

def test_pair_debug_loopback_only(rig):
    client, _ = rig
    data = client.get("/api/pair/debug").json()
    assert "server_ip" in data and "port" in data
    assert data["paired_devices_count"] == 0


def test_lan_ip_scanner_skips_loopback_and_linklocal(monkeypatch):
    from jarvis_agent import security

    class _Addr:
        family = socket.AF_INET

        def __init__(self, address):
            self.address = address

    class _FakePsutil:
        @staticmethod
        def net_if_addrs():
            return {
                "lo": [_Addr("127.0.0.1")],
                "vEthernet": [_Addr("169.254.1.2")],
                "Ethernet": [_Addr("192.168.1.50")],
            }

    def _boom(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(socket.socket, "connect", _boom)
    fake = type(sys)("psutil")
    fake.net_if_addrs = _FakePsutil.net_if_addrs
    monkeypatch.setitem(sys.modules, "psutil", fake)
    assert security.lan_ip() == "192.168.1.50"


# ══ Özellik 11: günlük özet ══════════════════════════════════════════════════

def test_daily_summary_generate_and_history(rig):
    client, _ = rig
    client.post("/api/chat", json={"message": "merhaba jarvis"})
    gen = client.post("/api/summary/generate", json={"channels": "chat"})
    assert gen.status_code == 200
    body = gen.json()
    assert body["ok"] is True and body["summary"]
    history = client.get("/api/summary/history").json()["summaries"]
    assert any(s["date"] == body["date"] for s in history)


def test_daily_summary_collect_stats(rig):
    from jarvis_agent.core import daily_summary

    client, _ = rig
    client.post("/api/chat", json={"message": "test mesajı bugün"})
    stats = daily_summary._collect_stats("local")
    assert stats["chat_count"] >= 1
    assert "tasks_done" in stats and "habits_total" in stats
    # Kural tabanlı yedek özet LLM'siz de üretir
    text = daily_summary._fallback_summary(stats)
    assert "Günlük Özet" in text


# ══ Özellik 13: ayarlar trim koruması ════════════════════════════════════════

def test_settings_trim_null_safe(rig):
    client, _ = rig
    r = client.put(
        "/api/settings",
        json={"city": None, "persona_name": "   ", "background_color": "maroon"},
    )
    assert r.status_code == 200
    data = client.get("/api/settings").json()
    assert data["background_color"] == "maroon"
    # Bozuk tip (int) string'e çevrilir
    r2 = client.put("/api/settings", json={"city": 42})
    assert r2.status_code == 200
    assert client.get("/api/settings").json()["city"] == "42"


# ══ Özellik 17: ATLAS kuyruk sınıflandırma ═══════════════════════════════════

def test_atlas_task_classification_and_queue(rig):
    client, _ = rig
    created = client.post(
        "/api/atlas/task", json={"instruction": "webde ara: Clio 4 hangi marka"}
    )
    assert created.status_code == 200
    task_id = created.json()["task_id"]
    assert created.json()["type"] == "research"
    gui = client.post("/api/atlas/task", json={"instruction": "ekranı tıkla ve fareyi oynat"})
    assert gui.status_code == 422
    assert "masaüstü" in gui.json()["detail"]
    status = client.get(f"/api/atlas/task/{task_id}")
    assert status.status_code == 200
    assert client.delete(f"/api/atlas/task/{task_id}").json()["ok"] is True


# ══ Özellik 19: konum tespiti (ağ izole) ═════════════════════════════════════

def test_location_detect_offline_graceful(monkeypatch):
    import httpx

    from jarvis_agent.api import routes_location

    def _raise(*a, **k):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(routes_location.httpx, "get", _raise)
    result = routes_location._detect_by_ip()
    assert result["source"] == "none" and not result["city"]
