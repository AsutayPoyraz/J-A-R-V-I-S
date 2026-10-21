"""SQLite veri katmanı — sohbet geçmişi, ayarlar ve audit log.

Bölüm A: kullanıcıya özel ayarlar (owner bazlı) bu katmanda tutulur;
misafirler (owner='guest:*') kalıcı ayar yazamaz. Tablolar `init_db`
içinde bildirilir; şema değişiklikleri idempotenttir.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from contextlib import closing
from typing import Any, Optional

from .. import config

_write_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL DEFAULT 'local',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS google_home_tokens (
    owner_id TEXT PRIMARY KEY,
    encrypted_token TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Bölüm A: kullanıcıya özel ayarlar (sahibine göre izole; misafir yazamaz)
CREATE TABLE IF NOT EXISTS user_settings (
    owner_id TEXT PRIMARY KEY,
    theme TEXT NOT NULL DEFAULT 'maroon',
    chat_position TEXT NOT NULL DEFAULT 'right',
    language TEXT NOT NULL DEFAULT 'tr',
    city TEXT,
    updated_at TEXT NOT NULL
);

-- Bölüm B: hesaplar (madde 5/16) — şifre ve güvenlik cevabı bcrypt hash saklanır
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    first_name_lower TEXT NOT NULL,
    last_name_lower TEXT NOT NULL,
    birth_date TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    security_question TEXT NOT NULL,
    security_answer_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_name ON users (first_name_lower, last_name_lower);

-- Bölüm B: başarısız giriş/kurtarma denemeleri (yeniden başlatmada sıfırlanmaz).
CREATE TABLE IF NOT EXISTS login_attempts (
    lock_key TEXT PRIMARY KEY,
    fails INTEGER NOT NULL DEFAULT 0,
    blocked_until REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at REAL NOT NULL
);
"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """Taze bir SQLite bağlantısı döndürür (WAL modu, satır sözlüğü)."""
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Tabloları oluşturur ve varsayılan ayarları ekler (idempotent)."""
    with _write_lock, closing(connect()) as conn, conn:
        conn.executescript(_SCHEMA)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "owner_id" not in columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_owner_id_id "
            "ON messages (owner_id, id)"
        )
        _migrate_user_settings_columns(conn)
        for key, value in _default_settings().items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        # Eski global ayarları (renk/şehir) bir kez 'local' sahibine taşı.
        _migrate_legacy_settings(conn)


def _migrate_user_settings_columns(conn: sqlite3.Connection) -> None:
    """Eksik sütunları ekler (idempotent).

    - conversation_mode: Prompt 3 — konuşma modu (varsayılan 'adaptive')
    - custom_palette: Prompt 0/4 — özel tema paleti (JSON metni)
    - twofa_enabled: Prompt 6 — kritik komutlarda 2FA tercihi
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(user_settings)")}
    additions = (
        ("conversation_mode", "TEXT NOT NULL DEFAULT 'adaptive'"),
        ("custom_palette", "TEXT"),
        ("twofa_enabled", "INTEGER NOT NULL DEFAULT 1"),
    )
    for name, ddl in additions:
        if name not in columns:
            conn.execute(f"ALTER TABLE user_settings ADD COLUMN {name} {ddl}")



def _default_settings() -> dict[str, str]:
    return {
        "background_color": config.DEFAULT_BG_COLOR,
        "city": config.DEFAULT_CITY,
        "command_count": "0",
    }


# ── Ayarlar (genel/geriye dönük) ─────────────────────────────────────────────

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_all_settings() -> dict[str, str]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def increment_setting_int(key: str, by: int = 1) -> int:
    """Bir sayaç ayarını artırır (upsert) ve yeni değeri döndürür."""
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = "
            "CAST(CAST(value AS INTEGER) + ? AS TEXT)",
            (key, str(by), by),
        )
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return int(row["value"])


# ── Bölüm A: kullanıcıya özel ayarlar (owner bazlı) ──────────────────────────

_USER_SETTINGS_COLS = (
    "theme",
    "chat_position",
    "language",
    "city",
    "conversation_mode",
    "custom_palette",
    "twofa_enabled",
)


def _settings_defaults(owner_id: str) -> dict[str, Any]:
    return {
        "owner_id": owner_id,
        "theme": config.DEFAULT_BG_COLOR,
        "chat_position": config.DEFAULT_CHAT_POSITION,
        "language": config.DEFAULT_LANGUAGE,
        "city": config.DEFAULT_CITY or None,
        "conversation_mode": config.DEFAULT_CONVERSATION_MODE,
        "custom_palette": None,
        "twofa_enabled": 1,
        "updated_at": None,
    }


def _owner_row(owner_id: str) -> dict[str, Any]:
    """owner satırını getirir; yoksa varsayılanlarla döndürür (yazmaz)."""
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT owner_id, theme, chat_position, language, city, "
            "conversation_mode, custom_palette, twofa_enabled, updated_at "
            "FROM user_settings WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
    if row:
        return dict(row)
    return _settings_defaults(owner_id)


def is_guest(owner_id: str) -> bool:
    """Misafir oturumlar kalıcı ayar yazamaz (madde 6/16 kuralı)."""
    return str(owner_id or "").startswith("guest:")


def get_user_settings(owner_id: str) -> dict[str, Any]:
    """Sahibinin ayarlarını döndürür; misafirler her zaman varsayılanı görür."""
    row = _owner_row(owner_id)
    if is_guest(owner_id):
        return _settings_defaults(owner_id)
    return row


def update_user_settings(owner_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Sahibinin ayarlarını günceller (misafirler için no-op + mevcut döner)."""
    if is_guest(owner_id):
        return get_user_settings(owner_id)
    allowed = {k: v for k, v in patch.items() if k in _USER_SETTINGS_COLS and v is not None}
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (owner_id, updated_at) VALUES (?, ?)",
            (owner_id, _now()),
        )
        sets = ", ".join(f"{col} = ?" for col in allowed)
        params = list(allowed.values()) + [_now(), owner_id]
        if sets:
            conn.execute(
                f"UPDATE user_settings SET {sets}, updated_at = ? WHERE owner_id = ?",
                params,
            )
    return _owner_row(owner_id)


# ── Sohbet geçmişi ───────────────────────────────────────────────────────────

def add_message(role: str, content: str, owner_id: str = "local") -> int:
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO messages (owner_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (owner_id, role, content, _now()),
        )
    return int(cur.lastrowid or 0)


def get_messages(limit: int = 200, owner_id: str = "local") -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
            (owner_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_messages(owner_id: str = "local") -> int:
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute("DELETE FROM messages WHERE owner_id = ?", (owner_id,))
    return int(cur.rowcount or 0)


# ── Audit log (Faz 2'de cihaz kimlikleriyle birlikte) ─────────────────────────

def audit(event: str, actor: str = "local", detail: str = "") -> None:
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO audit_log (ts, actor, event, detail) VALUES (?, ?, ?, ?)",
            (_now(), actor, event, detail[:500]),
        )


def get_audit(limit: int = 100) -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, event, detail FROM audit_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


# ── Google Home token deposu (entegrasyon, Faz 5-7) ──────────────────────────

def save_google_home_token(owner_id: str, encrypted_token: str) -> None:
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO google_home_tokens (owner_id, encrypted_token, updated_at) "
            "VALUES (?, ?, ?) ON CONFLICT(owner_id) DO UPDATE SET "
            "encrypted_token=excluded.encrypted_token, updated_at=excluded.updated_at",
            (owner_id, encrypted_token, _now()),
        )


def get_google_home_token(owner_id: str) -> Optional[str]:
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT encrypted_token FROM google_home_tokens WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
    return str(row["encrypted_token"]) if row else None


def delete_google_home_token(owner_id: str) -> None:
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute("DELETE FROM google_home_tokens WHERE owner_id = ?", (owner_id,))


# ── Eski global ayarlardan tek seferlik taşıma ───────────────────────────────

def _migrate_legacy_settings(conn: sqlite3.Connection) -> None:
    """Global 'settings' (renk/şehir) değerlerini owner='local' altına kopyalar.

    Idempotenttir: işaret 'settings' tablosundaki 'user_settings_migrated'
    anahtarıyla tutulur. Yalnızca kendisine verilen bağlantıyı kullanır
    (init_db'nin yaz kilidi içinde çağrılır — kilit yeniden edinilemez!).
    """
    marker = conn.execute(
        "SELECT value FROM settings WHERE key = 'user_settings_migrated'"
    ).fetchone()
    if marker and marker["value"] == "1":
        return
    existing = conn.execute(
        "SELECT 1 FROM user_settings WHERE owner_id = 'local'"
    ).fetchone()
    if not existing:
        theme = conn.execute(
            "SELECT value FROM settings WHERE key = 'background_color'"
        ).fetchone()
        city = conn.execute(
            "SELECT value FROM settings WHERE key = 'city'"
        ).fetchone()
        theme_val = theme["value"] if theme else None
        city_val = city["value"] if city else None
        conn.execute(
            "INSERT INTO user_settings (owner_id, theme, city, updated_at) "
            "VALUES (?, COALESCE(?, ?), COALESCE(?, ?), ?)",
            (
                "local",
                theme_val if theme_val in config.ALLOWED_BG_COLORS else None,
                config.DEFAULT_BG_COLOR,
                city_val,
                config.DEFAULT_CITY or None,
                _now(),
            ),
        )
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('user_settings_migrated', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )


# ── Kullanıcılar (Bölüm B — madde 5/16) ──────────────────────────────────────

def create_user(
    first_name: str,
    last_name: str,
    birth_date: str,
    password_hash: str,
    security_question: str,
    security_answer_hash: str,
) -> dict[str, Any]:
    """Yeni hesap oluşturur; aynı isim+soyisim varsa ValueError fırlatır."""
    import uuid

    user_id = uuid.uuid4().hex[:16]
    try:
        with _write_lock, closing(connect()) as conn, conn:
            conn.execute(
                "INSERT INTO users (id, first_name, last_name, first_name_lower, "
                "last_name_lower, birth_date, password_hash, security_question, "
                "security_answer_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    first_name,
                    last_name,
                    first_name.lower(),
                    last_name.lower(),
                    birth_date,
                    password_hash,
                    security_question[:200],
                    security_answer_hash,
                    _now(),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Bu isim ve soyisimle bir hesap zaten var.") from exc
    return get_user_by_id(user_id) or {}


def _user_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def get_user_by_name(first_name: str, last_name: str) -> Optional[dict[str, Any]]:
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE first_name_lower = ? AND last_name_lower = ?",
            (first_name.strip().lower(), last_name.strip().lower()),
        ).fetchone()
    return _user_row_to_dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_row_to_dict(row) if row else None


def update_user_password(user_id: str, password_hash: str) -> bool:
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )
    return cur.rowcount > 0

