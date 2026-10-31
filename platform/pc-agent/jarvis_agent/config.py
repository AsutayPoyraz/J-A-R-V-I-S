"""JARVIS Platform — PC Agent yapılandırması.

Ortam değişkenleri aşağıdaki sırayla yüklenen .env dosyalarından okunur
(aynı anahtar için ilk bulunan değer kazanır; gerçek ortam değişkenleri
her zaman .env dosyalarından önceliklidir):

1. platform/pc-agent/.env
2. platform/.env
3. <depo kökü>/.env          ← JARVIS v10.x (eski masaüstü) anahtarları
                                v11'de de aynı biçimde devralınır
"""
from __future__ import annotations

import os
from pathlib import Path

APP_VERSION = "1.1.0"      # package sürümü (semver)
JARVIS_VERSION = "v11"     # ürün sürümü — UI/docs tek kaynak (Özellik 15)

AGENT_ROOT = Path(__file__).resolve().parent.parent      # platform/pc-agent
PLATFORM_ROOT = AGENT_ROOT.parent                       # platform/
REPO_ROOT = PLATFORM_ROOT.parent                        # depo kökü
WEB_DIST_DIR = PLATFORM_ROOT / "web" / "dist"

APP_DATA_DIR = Path.home() / ".jarvis-platform"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DATA_DIR / "agent.db"
SESSIONS_FILE = APP_DATA_DIR / "sessions.count"
LOG_DIR = APP_DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "agent.log"

ALLOWED_BG_COLORS = ("maroon", "light", "dark", "custom", "red", "green", "blue")
# Özel palet anahtarları (Prompt 0/4): yalnız bu anahtarlar DB'ye yazılır.
ALLOWED_PALETTE_KEYS = ("accent", "accent_soft", "bg_page")
# Prompt 3: konuşma modları
ALLOWED_CONVERSATION_MODES = ("formal", "casual", "adaptive")
# Bölüm G (madde 26): kişilik stilleri + sürükle-bırak panel düzenindeki
# geçerli widget kimlikleri (dashboard_layout JSON'u bunlarla sınırlıdır).
ALLOWED_PERSONA_STYLES = ("classic", "friendly", "concise", "funny")
ALLOWED_WIDGETS = (
    "social", "agent", "files", "weather", "system", "reminders",
    "smart_home", "camera", "uptime", "privacy", "wellbeing",
    # JARVIS v11 (mega prompt) widget'ları
    "tasks", "habits", "knowledge", "macros",
)

# Kullanıcı ayarları için izinli değerler (kullanıcıya özel ayarlar DB'de tutulur).
ALLOWED_LANGUAGES = ("tr", "en")
ALLOWED_CHAT_POSITIONS = ("right", "center")

# Madde 14: TTS ses dilleri (gTTS desteğiyle sınırlı); hız 0.5-2.0x.
ALLOWED_TTS_VOICES = ("tr", "en")
TTS_MIN_RATE = 0.5
TTS_MAX_RATE = 2.0
# Not: GUI otomasyonu/vision ayarları env() tanımından sonra okunur (bkz. altta).

# Şablon dosyalarındaki sahte anahtar değerleri geçersiz sayılır.
_PLACEHOLDER_PREFIXES = ("your_", "xxx", "changeme")


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(lowered.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def _load_dotenv() -> None:
    candidates = [
        AGENT_ROOT / ".env",
        PLATFORM_ROOT / ".env",
        REPO_ROOT / ".env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        try:
            raw = env_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


def env(name: str, default: str = "") -> str:
    """Ortam değişkeni okur; boş veya placeholder değerler default'a düşer."""
    value = os.getenv(name, "").strip()
    if not value or _looks_like_placeholder(value):
        return default
    return value


# ── Bölüm E: otomasyon & ekran analizi (madde 9) ────────────────────────────
# Klavye/fare otomasyonu varsayılan KAPALI; bilinçli olarak açılmalıdır.
GUI_AUTOMATION = env("JARVIS_GUI_AUTOMATION", "0").lower() in ("1", "true", "yes")
# Vision modeli: boşsa sağlayıcının aktif modeli kullanılır (vision desteklemesi gerekir).
VISION_MODEL = env("JARVIS_VISION_MODEL")

# ── Sunucu bağlantısı ────────────────────────────────────────────────────────
# Varsayılan 127.0.0.1: yalnızca bu makine. Yerel ağdan (telefon) erişmek için
# .env dosyasında JARVIS_BIND=0.0.0.0 yapın.
# GÜVENLİK NOTU: Faz 1'de kimlik doğrulama yoktur; güvenli olmayan ağlarda
# localhost'ta kalın. Kimlik doğrulama Faz 2'de (QR eşleştirme) eklenir.
BIND_HOST = env("JARVIS_BIND", "127.0.0.1")
BIND_PORT = int(env("JARVIS_PORT", "8000"))

# ── Kimlik doğrulama (Bölüm B — madde 5, 16) ────────────────────────────────
# JWT secret yalnızca .env'den okunur; koda ASLA gömülmez ve güvensiz bir
# varsayılan ÜRETİLMEZ. Boşsa auth uçları 503 döner (bkz. auth.auth_available).
AUTH_SECRET = env("JARVIS_JWT_SECRET")
ACCESS_TOKEN_TTL_SECONDS = 15 * 60            # madde 16: access 15 dk
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 3600     # madde 16: refresh 7 gün
RESET_TOKEN_TTL_SECONDS = 10 * 60             # şifre sıfırlama token'ı 10 dk
ELEVATION_TTL_SECONDS = 2 * 60                # 2FA elevation token'ı 2 dk (madde 15)
# PC'yi kapatma komutu varsayılan KAPALIdır; açmak için .env: JARVIS_ALLOW_SHUTDOWN=1
ALLOW_SHUTDOWN = env("JARVIS_ALLOW_SHUTDOWN") == "1"
BCRYPT_ROUNDS = 12                            # madde 16: bcrypt 12 round
LOGIN_MAX_FAILURES = 5                        # madde 16: 5 hatalı girişte
LOGIN_BLOCK_SECONDS = 15 * 60                 # 15 dakika engelleme
DEFAULT_LANGUAGE = env("JARVIS_DEFAULT_LANGUAGE", "tr")
DEFAULT_CONVERSATION_MODE = env("JARVIS_DEFAULT_CONVERSATION_MODE", "adaptive")
if DEFAULT_CONVERSATION_MODE not in ALLOWED_CONVERSATION_MODES:
    DEFAULT_CONVERSATION_MODE = "adaptive"

# Madde 14: TTS ses (tr/en) ve hız (0.5-2.0x) varsayılanları.
DEFAULT_TTS_VOICE = env("JARVIS_TTS_VOICE", "tr")
if DEFAULT_TTS_VOICE not in ALLOWED_TTS_VOICES:
    DEFAULT_TTS_VOICE = "tr"
try:
    DEFAULT_TTS_RATE = min(2.0, max(0.5, float(env("JARVIS_TTS_RATE", 1.0))))
except (TypeError, ValueError):
    DEFAULT_TTS_RATE = 1.0


# ── LLM sağlayıcısı ──────────────────────────────────────────────────────────
LLM_PROVIDER = env("JARVIS_LLM_PROVIDER").lower()    # boş → otomatik algılama
LLM_MODEL = env("JARVIS_LLM_MODEL")                  # boş → sağlayıcı varsayılanı

GROQ_API_KEY = env("JARVIS_GROQ_API_KEY") or env("GROQ_API_KEY")
GROQ_MODEL = env("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b")
# Özellik 18: Groq üzerinden Llama 3.3 70B seçeneği.
GROQ_LLAMA_MODEL = "llama-3.3-70b-versatile"
OPENAI_API_KEY = env("JARVIS_OPENAI_API_KEY") or env("OPENAI_API_KEY")
ANTHROPIC_API_KEY = env("JARVIS_ANTHROPIC_API_KEY") or env("ANTHROPIC_API_KEY")
OLLAMA_URL = env("JARVIS_OLLAMA_URL")                # boş → devre dışı
# Özellik 18: yeni sağlayıcılar.
GEMINI_API_KEY = env("JARVIS_GEMINI_API_KEY") or env("GEMINI_API_KEY")
GEMINI_MODEL = env("JARVIS_GEMINI_MODEL", "gemini-2.0-flash")
DEEPSEEK_API_KEY = env("JARVIS_DEEPSEEK_API_KEY") or env("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = env("JARVIS_DEEPSEEK_MODEL", "deepseek-reasoner")

DEFAULT_MODELS = {
    "gemini": GEMINI_MODEL,
    "deepseek": DEEPSEEK_MODEL,
    "groq": GROQ_MODEL,
    "llama": GROQ_LLAMA_MODEL,   # Groq üzerinden Llama 3.3 70B
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.1",
    "mock": "mock-1",
}


def detect_provider() -> str:
    """Hangi sağlayıcının anahtarı varsa onu seçer (Özellik 18 önceliği)."""
    if GEMINI_API_KEY:
        return "gemini"
    if DEEPSEEK_API_KEY:
        return "deepseek"
    if GROQ_API_KEY:
        return "groq"
    if OPENAI_API_KEY:
        return "openai"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OLLAMA_URL:
        return "ollama"
    return "mock"


def active_provider() -> str:
    return LLM_PROVIDER or detect_provider()


def active_model() -> str:
    return LLM_MODEL or DEFAULT_MODELS.get(active_provider(), "mock-1")


# ── Hava durumu ──────────────────────────────────────────────────────────────
OWM_API_KEY = env("JARVIS_OWM_API_KEY") or env("OWM_API_KEY")
# Kişisel konum kodda gömülü DEĞİLDİR — .env'den okunur; boşsa 'no_city' döner.
DEFAULT_CITY = env("JARVIS_CITY")

# Google Home Device Access (SDM) OAuth configuration. These values are
# intentionally absent by default; the integration stays disabled until all
# required credentials are configured.
GOOGLE_HOME_CLIENT_ID = env("GOOGLE_HOME_CLIENT_ID")
GOOGLE_HOME_CLIENT_SECRET = env("GOOGLE_HOME_CLIENT_SECRET")
GOOGLE_HOME_PROJECT_ID = env("GOOGLE_HOME_PROJECT_ID")
GOOGLE_HOME_REDIRECT_URI = env(
    "GOOGLE_HOME_REDIRECT_URI",
    "http://127.0.0.1:8000/api/smart-home/oauth/callback",
)
GOOGLE_HOME_TOKEN_KEY = env("GOOGLE_HOME_TOKEN_KEY")

# ── Relay (Faz 4: hatırlatıcılar relay'de yaşar) ─────────────────────────────
# Boş bırakılırsa hatırlatıcı modülü devre dışı kalır (yerel test kolaylığı).
RELAY_URL = env("JARVIS_RELAY_URL")                     # ör. ws://192.168.1.10:8100
RELAY_TOKEN = env("JARVIS_RELAY_TOKEN")
RELAY_HTTP_URL = env("JARVIS_RELAY_HTTP_URL")           # ör. http://192.168.1.10:8100
# Alarm kullanıcı hareketiyle susma koşulu: son X saniyede giriş varsa "duyuldu" say.
ALARM_IDLE_ACK_SECONDS = float(env("JARVIS_ALARM_IDLE_ACK_SECONDS", "5"))

# ── Arayüz varsayılanları ────────────────────────────────────────────────────
# Madde 4: bordo tema varsayılandır (kullanıcı daha önce farklı seçmediyse).
DEFAULT_BG_COLOR = env("JARVIS_DEFAULT_BG_COLOR", "maroon")
if DEFAULT_BG_COLOR not in ALLOWED_BG_COLORS:
    DEFAULT_BG_COLOR = "maroon"  # madde 4: bordo varsayılan tema
# Varsayılan tercihler (madde 3, 32): dil TR, sohbet paneli sağda.
DEFAULT_LANGUAGE = env("JARVIS_DEFAULT_LANGUAGE", "tr")
if DEFAULT_LANGUAGE not in ALLOWED_LANGUAGES:
    DEFAULT_LANGUAGE = "tr"
DEFAULT_CHAT_POSITION = env("JARVIS_DEFAULT_CHAT_POSITION", "right")
if DEFAULT_CHAT_POSITION not in ALLOWED_CHAT_POSITIONS:
    DEFAULT_CHAT_POSITION = "right"
