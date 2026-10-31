"""Kullanıcı API anahtarları deposu (Özellik 5B).

- ``user_api_keys`` tablosu: (user_id, key_name) → Fernet şifreli değer.
- Ana master key: .env'deki JARVIS_MASTER_KEY; yoksa otomatik ÜRETİLİR ve
  depo kökündeki .env'e yazılır (kullanıcı konsol loguyla uyarılır).
- ``resolve_llm_key``: sağlayıcı adını anahtar adına çevirip çözer
  (llm/router.py DB > .env önceliği için).
"""
from __future__ import annotations

import base64
import datetime
import logging
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.store.user_keys")

_lock = threading.Lock()
_fernet = None
_initialized = False

# LLM sağlayıcı adı → user_api_keys.key_name eşlemesi (Özellik 18)
LLM_KEY_NAMES = {
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
    "llama": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS user_api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    key_name TEXT NOT NULL,
    key_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, key_name)
);

-- Özellik 15: kullanıcı adı bazlı giriş (mega prompt 5A).
-- Eski tabloda username yok; güvenli ALTER (idempotent) init_db'de yapılır.
"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _master_key() -> bytes:
    """JARVIS_MASTER_KEY okur; yoksa üretir ve .env'e yazar (Özellik 5 notu)."""
    from .. import config

    key = config.env("JARVIS_MASTER_KEY")
    if key:
        try:
            base64.urlsafe_b64decode(key.encode())
            return key.encode()
        except Exception:  # noqa: BLE001 — bozuk anahtar yenilenir
            logger.warning("JARVIS_MASTER_KEY geçersiz; yeni anahtar üretiliyor.")
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    env_path = Path(config.REPO_ROOT) / ".env"
    try:
        existing = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
        if "JARVIS_MASTER_KEY" not in existing:
            with open(env_path, "a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(f"\n# JARVIS v11 — otomatik üretildi (API anahtarı şifreleme)\n")
                fh.write(f"JARVIS_MASTER_KEY={key}\n")
            logger.warning(
                "JARVIS_MASTER_KEY .env dosyasına otomatik üretildi — "
                "bu anahtarı GÜVENLİ bir yedeğe alın (kaybolursa kayıtlı API "
                "anahtarları okunamaz)."
            )
    except OSError:
        logger.warning("JARVIS_MASTER_KEY .env'e yazılamadı; yalnızca oturumluk.")
    os.environ["JARVIS_MASTER_KEY"] = key
    return key.encode()


def init() -> None:
    """Fernet örneğini hazırlar (database.init_db sonrası çağrılır)."""
    global _fernet, _initialized
    with _lock:
        if _initialized:
            return
        from cryptography.fernet import Fernet

        _fernet = Fernet(_master_key())
        _initialized = True


def _encrypt(value: str) -> str:
    init()
    return _fernet.encrypt(value.encode("utf-8")).decode()  # type: ignore[union-attr]


def _decrypt(token: str) -> str:
    init()
    try:
        return _fernet.decrypt(token.encode()).decode("utf-8")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 — anahtar değişmiş olabilir
        return ""


# ── CRUD (routes_user_settings çağırır) ──────────────────────────────────────

def set_key(user_id: str, key_name: str, value: str) -> bool:
    """Anahtarı şifreleyip kaydeder/günceller (misafir kullanıcıda False)."""
    user_id = str(user_id or "").strip()
    key_name = str(key_name or "").strip().upper()
    value = str(value or "")
    if not user_id or not key_name:
        return False
    from . import database

    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO user_api_keys (user_id, key_name, key_value, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, key_name) DO UPDATE SET "
            "key_value = excluded.key_value, updated_at = excluded.updated_at",
            (user_id, key_name, _encrypt(value), _now()),
        )
    return True


def delete_key(user_id: str, key_name: str) -> bool:
    from . import database

    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM user_api_keys WHERE user_id = ? AND key_name = ?",
            (str(user_id or ""), str(key_name or "").strip().upper()),
        )
    return cur.rowcount > 0


def get_key(user_id: str, key_name: str) -> str:
    """Değerin kendisini döndürür (yalnızca sunucu içi kullanım)."""
    from . import database

    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT key_value FROM user_api_keys WHERE user_id = ? AND key_name = ?",
            (str(user_id or ""), str(key_name or "").strip().upper()),
        ).fetchone()
    return _decrypt(row["key_value"]) if row else ""


def list_keys(user_id: str) -> list[dict]:
    """Anahtar ÖZETİ — değer asla döndürülmez (has_value + updated_at)."""
    from . import database

    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT key_name, updated_at FROM user_api_keys WHERE user_id = ? "
            "ORDER BY key_name",
            (str(user_id or ""),),
        ).fetchall()
    return [
        {"key_name": r["key_name"], "has_value": True, "updated_at": r["updated_at"]}
        for r in rows
    ]


def resolve_llm_key(provider_name: str, user_id: str) -> str:
    """router için: sağlayıcı adından kullanıcı anahtarını çözer."""
    key_name = LLM_KEY_NAMES.get((provider_name or "").lower())
    if not key_name or not user_id:
        return ""
    return get_key(user_id, key_name)

