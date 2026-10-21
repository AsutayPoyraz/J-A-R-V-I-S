"""Faz 1 birim testleri — istatistik, ayarlar, sohbet, offline, dışa aktarma.

Çalıştırma (platform/pc-agent altında):
    python -m pytest tests -v

Testler ağa veya LLM anahtarına bağlı DEĞİLDİR: LLM olarak her zaman
MockProvider kullanılır, kamera testlerde devre dışıdır.
"""
from __future__ import annotations

import os
import sqlite3

import pytest

# Test sürecinde: LLM kilidi mock'a sabitlenir (gerçek .env'deki anahtarlar
# _load_dotenv ile geri yüklense bile mock öncelikli kalır), kamera kapalıdır.
# Böylece testler ağa ve anahtara %100 bağımsızdır.
for var in (
    "JARVIS_GROQ_API_KEY",
    "JARVIS_OPENAI_API_KEY",
    "JARVIS_ANTHROPIC_API_KEY",
    "JARVIS_OLLAMA_URL",
    "JARVIS_OWM_API_KEY",
    "OWM_API_KEY",  # config yedek değişkeni — kök .env'den testlere sızmaz
    "JARVIS_LLM_MODEL",
):
    os.environ.pop(var, None)
os.environ["JARVIS_LLM_PROVIDER"] = "mock"
os.environ["JARVIS_CAMERA_DISABLED"] = "1"
os.environ["JARVIS_VOICE_DISABLED"] = "1"  # testlerde gerçek mikrofon açılmaz

from fastapi.testclient import TestClient  # noqa: E402

from jarvis_agent import config  # noqa: E402
from jarvis_agent.app import create_app  # noqa: E402
from jarvis_agent.core.stats import compute_load_level  # noqa: E402
from jarvis_agent.store import database  # noqa: E402

# Gerçek .env'den sızabilecek hava durumu anahtarını test sürecinde kapat
# (config, import sırasında OWM_API_KEY'i os.environ'a geri yükleyebiliyor).
config.OWM_API_KEY = ""


def _connect_to(path):
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """Her test için temiz DB'li bir uygulama istemcisi."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(database, "connect", lambda: _connect_to(db_path))
    # Hermetik: weather çağrı anında config.env okuyabildiği için gerçek
    # .env'den sızabilecek OWM anahtarını test boyunca gizle (satır 42'deki
    # modül özniteliği sıfırlaması tek başına yeterli değildi).
    real_env = config.env

    def _hermetic_env(name: str, default: str = "") -> str:
        if name in ("JARVIS_OWM_API_KEY", "OWM_API_KEY"):
            return default
        return real_env(name, default)

    monkeypatch.setattr(config, "env", _hermetic_env)
    app = create_app()
    with TestClient(app) as test_client:  # startup/shutdown çalışır
        yield test_client


# ── 1. Sistem istatistikleri ────────────────────────────────────────────────

def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "mock"  # test sürecinde anahtar yok


def test_system_stats_shape(client):
    resp = client.get("/api/system/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "cpu" in body and "memory" in body and "disk" in body
    assert 0.0 <= body["cpu"]["percent"] <= 100.0
    assert body["memory"]["total_gb"] > 0
    assert body["load_level"] in ("low", "medium", "high")
    assert "uptime_seconds" in body


def test_load_level_thresholds():
    assert compute_load_level(10.0, 20.0) == "low"
    assert compute_load_level(50.0, 50.0) == "medium"
    assert compute_load_level(95.0, 95.0) == "high"


def test_ws_stats_stream(client):
    with client.websocket_connect("/ws/stats") as ws:
        data = ws.receive_json()
        assert "cpu" in data and "uptime_seconds" in data


# ── 2. Ayarlar ───────────────────────────────────────────────────────────────

def test_settings_defaults(client):
    body = client.get("/api/settings").json()
    assert body["background_color"] in config.ALLOWED_BG_COLORS
    assert body["allowed_background_colors"] == list(config.ALLOWED_BG_COLORS)
    for expected in ("red", "green", "blue", "maroon"):
        assert expected in body["allowed_background_colors"]
    assert body["city"]


def test_settings_update_background_color(client):
    for color in ("red", "green", "blue"):
        resp = client.put("/api/settings", json={"background_color": color})
        assert resp.status_code == 200
        assert resp.json()["background_color"] == color


def test_settings_reject_invalid_color(client):
    resp = client.put("/api/settings", json={"background_color": "purple"})
    assert resp.status_code == 422


def test_settings_update_city(client):
    resp = client.put("/api/settings", json={"city": "İstanbul,TR"})
    assert resp.status_code == 200
    assert resp.json()["city"] == "İstanbul,TR"
    # Hava durumu ucu yeni şehri kullanır (anahtar yok → çökmez)
    weather = client.get("/api/weather").json()
    assert weather["available"] is False
    assert weather["reason"] == "no_api_key"


# ── 3. Yazılı sohbet (MockProvider ile) ─────────────────────────────────────

def test_chat_roundtrip_stored(client):
    resp = client.post("/api/chat", json={"message": "Merhaba Jarvis"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is False
    assert body["provider"] == "mock"
    assert body["reply"]

    history = client.get("/api/conversation").json()
    roles = [m["role"] for m in history["messages"]]
    assert roles[-2:] == ["user", "assistant"]


def test_chat_rejects_empty_message(client):
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_increments_command_count(client):
    before = client.get("/api/system/stats").json()["command_count"]
    client.post("/api/chat", json={"message": "selam"})
    after = client.get("/api/system/stats").json()["command_count"]
    assert after == before + 1


def test_conversation_export_txt_and_md(client):
    client.post("/api/chat", json={"message": "Merhaba"})
    txt = client.get("/api/conversation/export?format=txt")
    assert txt.status_code == 200
    assert "Kullanıcı" in txt.text and "Merhaba" in txt.text
    assert txt.headers["content-disposition"].endswith('.txt"')

    md = client.get("/api/conversation/export?format=md")
    assert md.status_code == 200
    assert "# JARVIS Konuşma Dökümü" in md.text
    assert md.headers["content-disposition"].endswith('.md"')


def test_conversation_clear(client):
    client.post("/api/chat", json={"message": "Merhaba"})
    resp = client.delete("/api/conversation")
    assert resp.status_code == 200
    assert resp.json()["cleared"] >= 2  # user + assistant
    assert client.get("/api/conversation").json()["count"] == 0


def test_conversations_are_isolated_by_client_id(client):
    alice = {"X-Client-ID": "client-alice-12345678"}
    bob = {"X-Client-ID": "client-bob-12345678"}

    client.post("/api/chat", json={"message": "Alice private"}, headers=alice)
    client.post("/api/chat", json={"message": "Bob private"}, headers=bob)

    alice_messages = client.get("/api/conversation", headers=alice).json()["messages"]
    bob_messages = client.get("/api/conversation", headers=bob).json()["messages"]

    assert all("Bob private" not in message["content"] for message in alice_messages)
    assert all("Alice private" not in message["content"] for message in bob_messages)

    cleared = client.delete("/api/conversation", headers=alice).json()["cleared"]
    assert cleared >= 2
    assert client.get("/api/conversation", headers=alice).json()["count"] == 0
    assert client.get("/api/conversation", headers=bob).json()["count"] >= 2


# ── 4. Offline / hata zarifliği ─────────────────────────────────────────────

def test_weather_graceful_without_api_key(client):
    body = client.get("/api/weather").json()
    assert body["available"] is False
    assert body["reason"] == "no_api_key"


def test_camera_disabled_returns_503_not_crash(client):
    resp = client.post("/api/camera/open")
    assert resp.status_code == 503
    detail = resp.json()["detail"].lower()
    assert "devre dışı" in detail or "kurulu değil" in detail
    status = client.get("/api/camera/status").json()
    assert status["status"] == "off"


def test_unknown_route_404_json(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404


# ── 5. Sağlayıcı fabrikası ve güvenlik ──────────────────────────────────────

def test_provider_factory_falls_back_to_mock(monkeypatch):
    # Anahtarların tümü boş + sağlayıcı seçimi yok → mock
    monkeypatch.delenv("JARVIS_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "OLLAMA_URL", "")
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    import jarvis_agent.llm as llm_pkg
    provider = llm_pkg.build_provider()
    assert provider.name == "mock"


def test_provider_factory_respects_explicit_choice(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_PROVIDER", "mock")
    import jarvis_agent.llm as llm_pkg
    assert llm_pkg.build_provider().name == "mock"


def test_system_prompt_forbids_destructive_actions():
    from jarvis_agent.chat.service import SYSTEM_PROMPT
    lowered = SYSTEM_PROMPT.lower()

    assert "shell" in lowered
    assert "onay" in lowered


# ── 6. Faz 3: Sesli mod — metin eşleştirme ve ses uçları ─────────────────────

def test_normalize_turkish():
    from jarvis_agent.voice.textmatch import normalize

    assert normalize("HEY JARVİS") == "hey jarvis"
    assert normalize("Uyan Bakalım Baba E ve Geldi!") == "uyan bakalım baba e ve geldi"
    assert normalize("") == ""


def test_match_phrase_wake_words():
    from jarvis_agent.voice.textmatch import match_phrase

    assert match_phrase("hey jarvis", "hey jarvis")
    # STT hatası toleransı: "hey carvis" → jarvis fonetik düzeltmesi
    assert match_phrase("hey carvis", "hey jarvis")
    # Fazladan kelime içeren STT çıktısı (kayan pencere)
    assert match_phrase("evet hey jarvis buyrun", "hey jarvis")
    # Uzun uyandırma cümlesi
    assert match_phrase("uyan bakalım baba eve geldi", "uyan bakalım baba eve geldi")
    # Ilımlı hata tolere edilir
    assert match_phrase("uyan bakalim baba eve gildi", "uyan bakalım baba eve geldi")


def test_match_phrase_rejects_unrelated():
    from jarvis_agent.voice.textmatch import match_phrase

    assert not match_phrase("hava çok güzel today", "hey jarvis")
    assert not match_phrase("", "hey jarvis")


def test_is_enter_voice_command():
    from jarvis_agent.voice.textmatch import is_enter_voice_command

    assert is_enter_voice_command("Jarvis sesli moda geç")
    assert is_enter_voice_command("sesli moda gec lutfen")
    assert not is_enter_voice_command("hava durumu nedir")
    assert not is_enter_voice_command("")


def test_voice_status_shape(client):
    resp = client.get("/api/voice/status")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "mic", "session", "mic_available", "local_stt",
        "clap_enabled", "clap_sensitivity", "wake_phrases", "exit_phrases",
    ):
        assert key in body


def test_voice_gate_in_chat_without_mic(client):
    """'Sesli moda geç' yazınca LLM'e gitmeden yerel yakalanır.

    CI'da mikrofon olmadığından yol: kibar reddetme yanıtı ve
    voice_mode=False. (Mikrofonlu makinede 'Tamamdır.' döner.)
    """
    resp = client.post("/api/chat", json={"message": "Jarvis sesli moda geç"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "local-command"
    assert body["used_tools"] == []
    # Mikrofon var/yok ikisinde de voice-gate çalışır; yanıt kaydedilir
    assert body["reply"]


def test_voice_settings_update(client):
    resp = client.put(
        "/api/voice/settings",
        json={"clap_enabled": False, "clap_sensitivity": 12.5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["clap_enabled"] is False
    assert body["clap_sensitivity"] == 12.5

    # Geçersiz hassasiyet reddedilir (aralık 1..20)
    resp = client.put("/api/voice/settings", json={"clap_sensitivity": 99})
    assert resp.status_code == 422


def test_voice_start_without_mic_is_503(client):
    """CI'da mikrofon yoksa /api/voice/start 503 döner (çökmez)."""
    resp = client.post("/api/voice/start")
    assert resp.status_code == 503


def test_stats_stream_contains_mic_state(client):
    """Mikrofon durumu WS istatistik akışında her zaman görünür (gereklim 5.4)."""
    with client.websocket_connect("/ws/stats") as ws:
        data = ws.receive_json()
        assert "voice" in data
        assert "mic" in data["voice"]

