import json
import os
import sys
import threading
from pathlib import Path

logger = __import__('logging').getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
APP_DATA_DIR = Path.home() / ".jarvis"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(APP_DATA_DIR, 0o700)
except OSError:
    pass

LOG_DIR = APP_DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(LOG_DIR, 0o700)
except OSError:
    pass

# Tek sürüm kaynağı: JARVIS_VERSION ortam değişkeni tanımsızsa güncelleme
# denetimi (services.update_check) bu değeri 'mevcut sürüm' olarak kullanır.
APP_VERSION = "11.0.0"
# UI metinlerinde kısa biçim (ör. "v11 Apex"): ürün markası "v11" — README ve
# pc-agent'ın JARVIS_VERSION ("v11") değeriyle hizalı; semver APP_VERSION'da.
APP_DISPLAY_VERSION = APP_VERSION.split(".")[0]


def _load_dotenv_file() -> None:
    """Load environment variables from a .env file in the project root or current working directory."""
    env_paths = [APP_DIR / ".env"]
    if getattr(sys, "frozen", False):
        # PyInstaller paketli mod: .env EXE'nin yanına konur (bundle içine gömülmez).
        env_paths.insert(0, Path(sys.executable).resolve().parent / ".env")
    seen = set()
    for env_path in env_paths:
        if not env_path.exists() or env_path.resolve() in seen:
            continue
        seen.add(env_path.resolve())
        try:
            with open(env_path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[len("export "):]
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if value.startswith("#"):
                        value = ""
                    os.environ.setdefault(key, value)
        except OSError:
            continue


_load_dotenv_file()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def ensure_private_file(path: str) -> None:
    """Dosyanın ve onun klasörünün güvenli izinlerle (600/700) ayarlanması.
    
    Windows'ta çalışmama izin hataları nedeniyle bu işlem isteğe bağlıdır.
    """
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(p.parent, 0o700)
        except (PermissionError, OSError) as e:
            logger.debug(f"[Config] Klasör izinleri ayarlanamadı: {e}")
        if p.exists():
            try:
                os.chmod(p, 0o600)
            except (PermissionError, OSError) as e:
                logger.debug(f"[Config] Dosya izinleri ayarlanamadı: {e}")
    except OSError as e:
        logger.warning(f"[Config] Dosya güvenliği ayarı başarısız: {e}")


def safe_read_json(path: str, default=None):
    """JSON dosyasını güvenli bir şekilde oku. Hata durumunda default döner."""
    resolved = Path(path)
    if not resolved.exists():
        return default
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as e:
        logger.debug(f"[Config] JSON parse hatası: {e}")
        return default
    except (OSError, ValueError) as e:
        logger.debug(f"[Config] JSON okuma hatası: {e}")
        return default


_JSON_WRITE_LOCK = threading.Lock()


def safe_write_json(path: str, payload):
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved.with_suffix(f"{resolved.suffix}.tmp")
    with _JSON_WRITE_LOCK:
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp_path, resolved)
            try:
                os.chmod(resolved, 0o600)
            except OSError:
                pass
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass


GROQ_API_KEY = _env("JARVIS_GROQ_API_KEY") or _env("GROQ_API_KEY")
GROQ_MODEL = _env("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b")
GEMINI_API_KEY = _env("JARVIS_GEMINI_API_KEY") or _env("GEMINI_API_KEY")
GEMINI_MODEL = "-".join(
    _env("JARVIS_GEMINI_MODEL", "gemini-3.8-flash").lower().split()
)
OWM_API_KEY = _env("JARVIS_OWM_API_KEY") or _env("OWM_API_KEY")
SMTP_USER = _env("JARVIS_SMTP_USER")
SMTP_PASS = _env("JARVIS_SMTP_PASS")
# SMTP sunucusu: varsayılan Gmail'in herkese açık adresidir; .env ile override edilebilir.
SMTP_HOST = _env("JARVIS_SMTP_HOST", "smtp.gmail.com")
try:
    SMTP_PORT = int(_env("JARVIS_SMTP_PORT", "465"))
except ValueError:
    SMTP_PORT = 465
# Kişisel bilgiler (yazıcı e-postası, konum) YALNIZCA .env'den okunur;
# kod içinde varsayılan değer gömülü DEĞİLDİR (bkz. .env.example).
EPSON_EMAIL = _env("JARVIS_EPSON_EMAIL")
CITY = _env("JARVIS_CITY")

DB_PATH = str(APP_DATA_DIR / "jarvis_memory.db")
STYLE_PATH = str(APP_DATA_DIR / "user_style.json")
CONTACTS_FILE = str(APP_DATA_DIR / "jarvis_contacts.json")
PDF_STORE = str(APP_DATA_DIR / "jarvis_pdfs")
SETTINGS_FILE = str(APP_DATA_DIR / "jarvis_settings.json")
PROFILE_FILE = str(APP_DATA_DIR / "jarvis_profile.json")
LOG_FILE = str(LOG_DIR / "jarvis.log")

ensure_private_file(DB_PATH)
ensure_private_file(SETTINGS_FILE)
ensure_private_file(PROFILE_FILE)
ensure_private_file(STYLE_PATH)
ensure_private_file(CONTACTS_FILE)
Path(PDF_STORE).mkdir(parents=True, exist_ok=True)
try:
    os.chmod(PDF_STORE, 0o700)
except OSError:
    pass
