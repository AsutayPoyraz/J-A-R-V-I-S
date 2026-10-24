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

-- Bölüm E (madde 18): Memory Bank — kullanıcıya özel kalıcı bilgiler
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_owner ON memories (owner_id, id);

-- Bölüm E (madde 22): özel komutlar — "kahve zamanı" gibi kısayollar
CREATE TABLE IF NOT EXISTS custom_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    phrase TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('reply_text', 'open_app')),
    action_payload TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (owner_id, phrase)
);

-- Bölüm E (madde 23): üretkenlik — notlar ve yapılacaklar
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
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
        _ensure_section_f_tables(conn)
        _ensure_section_g_tables(conn)
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
        ("tts_rate", "REAL NOT NULL DEFAULT 1.0"),
        ("tts_voice", "TEXT NOT NULL DEFAULT 'tr'"),
        # Bölüm G (madde 25/26/27)
        ("privacy_mode", "INTEGER NOT NULL DEFAULT 0"),
        ("auto_lock_minutes", "INTEGER NOT NULL DEFAULT 0"),
        ("persona_name", "TEXT"),
        ("persona_style", "TEXT"),
        ("dashboard_layout", "TEXT"),
        ("font_scale", "REAL NOT NULL DEFAULT 1.0"),
        ("dyslexic_font", "INTEGER NOT NULL DEFAULT 0"),
        ("high_contrast", "INTEGER NOT NULL DEFAULT 0"),
        ("break_reminder_minutes", "INTEGER NOT NULL DEFAULT 0"),
        ("daily_limit_minutes", "INTEGER NOT NULL DEFAULT 0"),
        ("focus_mode", "INTEGER NOT NULL DEFAULT 0"),
        ("mood", "TEXT NOT NULL DEFAULT 'neutral'"),
        ("mood_updated_at", "TEXT"),
    )
    for name, ddl in additions:
        if name not in columns:
            conn.execute(f"ALTER TABLE user_settings ADD COLUMN {name} {ddl}")


def _ensure_section_f_tables(conn: sqlite3.Connection) -> None:
    """Bölüm F tabloları (madde 19/20/21/24) — idempotent."""
    conn.executescript(
        """
        -- Madde 19: dosya etiketleri (owner bazlı metadata; dosya paylaşılan klasörde)
        CREATE TABLE IF NOT EXISTS file_tags (
            owner_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (owner_id, file_name)
        );

        -- Madde 19: sesli notlar (metin; Web Speech / yerel STT ile)
        CREATE TABLE IF NOT EXISTS voice_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_voice_notes_owner ON voice_notes (owner_id, id);

        -- Madde 20: makrolar / shortcut'lar
        CREATE TABLE IF NOT EXISTS macros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            name TEXT NOT NULL,
            steps TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            UNIQUE (owner_id, name)
        );

        -- Madde 20: etkinlik akışı (son 7 gün)
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_activity_owner ON activity_log (owner_id, created_at);

        -- Madde 21: XP olayları — puanlar yalnızca sunucu tarafında yazılır
        CREATE TABLE IF NOT EXISTS xp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_xp_owner_created ON xp_events (owner_id, created_at);

        -- Madde 21: rozetler
        CREATE TABLE IF NOT EXISTS badges (
            owner_id TEXT NOT NULL,
            code TEXT NOT NULL,
            earned_at TEXT NOT NULL,
            PRIMARY KEY (owner_id, code)
        );

        -- Madde 20: paylaşılan oturumlar (Shared Jarvis Sessions)
        CREATE TABLE IF NOT EXISTS shared_sessions (
            code TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shared_members (
            code TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            joined_at TEXT NOT NULL,
            PRIMARY KEY (code, owner_id)
        );
        CREATE TABLE IF NOT EXISTS shared_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'user',
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_shared_msgs ON shared_messages (code, id);
        """
    )


def _ensure_section_g_tables(conn: sqlite3.Connection) -> None:
    """Bölüm G tabloları (madde 25/27) — idempotent."""
    conn.executescript(
        """
        -- Madde 25: güvenlik denetim kaydı (oturum, dosya, eşleştirme, kritik işlem)
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            ip TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sec_events_owner
            ON security_events (owner_id, id);

        -- Madde 25: istemci tarafı şifreli notlar (sunucu yalnız şifreli metin görür)
        CREATE TABLE IF NOT EXISTS secure_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            title_cipher TEXT NOT NULL,
            body_cipher TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_secure_notes_owner
            ON secure_notes (owner_id, id);

        -- Madde 25: hassas işlem izinleri (varsayılan açık; owner kapatabilir)
        CREATE TABLE IF NOT EXISTS permission_overrides (
            owner_id TEXT NOT NULL,
            permission TEXT NOT NULL,
            allowed INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (owner_id, permission)
        );

        -- Madde 27: mood tracker günlüğü (owner+gün başına tek kayıt)
        CREATE TABLE IF NOT EXISTS mood_log (
            owner_id TEXT NOT NULL,
            day TEXT NOT NULL,
            mood TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (owner_id, day)
        );

        -- Madde 27: günlük kullanım dakikaları (limit kontrolü için)
        CREATE TABLE IF NOT EXISTS usage_days (
            owner_id TEXT NOT NULL,
            day TEXT NOT NULL,
            minutes INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (owner_id, day)
        );
        """
    )


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
    "tts_rate",
    "tts_voice",
    # Bölüm G (madde 25/26/27): gizlilik, arayüz, iyi oluş
    "privacy_mode",
    "auto_lock_minutes",
    "persona_name",
    "persona_style",
    "dashboard_layout",
    "font_scale",
    "dyslexic_font",
    "high_contrast",
    "break_reminder_minutes",
    "daily_limit_minutes",
    "focus_mode",
    "mood",
    "mood_updated_at",
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
        "tts_rate": config.DEFAULT_TTS_RATE,
        "tts_voice": config.DEFAULT_TTS_VOICE,
        # Bölüm G varsayılanları
        "privacy_mode": 0,
        "auto_lock_minutes": 0,
        "persona_name": "JARVIS",
        "persona_style": None,
        "dashboard_layout": None,
        "font_scale": 1.0,
        "dyslexic_font": 0,
        "high_contrast": 0,
        "break_reminder_minutes": 0,
        "daily_limit_minutes": 0,
        "focus_mode": 0,
        "mood": "neutral",
        "mood_updated_at": None,
        "updated_at": None,
    }


def _owner_row(owner_id: str) -> dict[str, Any]:
    """owner satırını getirir; yoksa varsayılanlarla döndürür (yazmaz)."""
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT owner_id, theme, chat_position, language, city, "
            "conversation_mode, custom_palette, twofa_enabled, tts_rate, tts_voice, "
            "privacy_mode, auto_lock_minutes, persona_name, persona_style, "
            "dashboard_layout, font_scale, dyslexic_font, high_contrast, "
            "break_reminder_minutes, daily_limit_minutes, focus_mode, "
            "mood, mood_updated_at, updated_at "
            "FROM user_settings WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
    if row:
        return dict(row)
    return _settings_defaults(owner_id)


def is_guest(owner_id: str) -> bool:
    """Misafir oturumlar kalıcı ayar yazamaz (madde 6/16 kuralı)."""
    return str(owner_id or "").startswith("guest:")


def primary_owner_id() -> str:
    """PC tarafı (sesli mod) için birincil sahip etiketi.

    Kayıtlı en yeni hesabın 'user:<id>' etiketi döner; hesap yoksa 'local'.
    Sesli modun konuşma modu/TTS tercihleri bu sahibinden okunur.
    """
    try:
        with closing(connect()) as conn:
            row = conn.execute(
                "SELECT id FROM users ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return "local"
    if row and row["id"]:
        return f"user:{row['id']}"
    return "local"


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


# ── Bölüm E: Memory Bank ve özel komutlar (madde 18, 22) ─────────────────────

def add_memory(owner_id: str, content: str) -> int | None:
    """Madde 18: kalıcı bilgi yazar; misafirse yazmaz (None döner)."""
    content = (content or "").strip()[:500]
    if is_guest(owner_id) or not content:
        return None
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO memories (owner_id, content, created_at) VALUES (?, ?, ?)",
            (owner_id, content, _now()),
        )
    return int(cur.lastrowid or 0)


def list_memories(owner_id: str, limit: int = 20, query: str = "") -> list[dict[str, Any]]:
    """Sahibinin hatırlamalarını (en yeni önce) döndürür; misafirde boş."""
    if is_guest(owner_id):
        return []
    limit = max(1, min(int(limit), 100))
    sql = "SELECT id, content, created_at FROM memories WHERE owner_id = ?"
    params: list[Any] = [owner_id]
    if query.strip():
        sql += " AND content LIKE ?"
        params.append(f"%{query.strip()[:100]}%")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with closing(connect()) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def delete_memory(owner_id: str, memory_id: int) -> bool:
    if is_guest(owner_id):
        return False
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM memories WHERE id = ? AND owner_id = ?",
            (int(memory_id), owner_id),
        )
    return cur.rowcount > 0


def add_custom_command(
    owner_id: str, phrase: str, action_type: str, action_payload: str = ""
) -> int | None:
    """Madde 22: özel komut kaydeder; misafir/kısa ifade/hatalı tür → None."""
    phrase = (phrase or "").strip().lower()[:60]
    if is_guest(owner_id) or len(phrase) < 2:
        return None
    if action_type not in ("reply_text", "open_app"):
        return None
    with _write_lock, closing(connect()) as conn, conn:
        try:
            cur = conn.execute(
                "INSERT INTO custom_commands (owner_id, phrase, action_type, "
                "action_payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (owner_id, phrase, action_type, (action_payload or "").strip()[:500], _now()),
            )
        except sqlite3.IntegrityError:  # aynı ifade iki kez
            return None
    return int(cur.lastrowid or 0)


def list_custom_commands(owner_id: str) -> list[dict[str, Any]]:
    if is_guest(owner_id):
        return []
    with closing(connect()) as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, phrase, action_type, action_payload, created_at "
                "FROM custom_commands WHERE owner_id = ? ORDER BY id",
                (owner_id,),
            ).fetchall()
        ]


def match_custom_command(owner_id: str, message: str) -> dict[str, Any] | None:
    """İletiyi özel komut ifadeleriyle (büyük/küçük duyarsız) eşleştirir."""
    if is_guest(owner_id):
        return None
    text = (message or "").strip().lower()
    if not text:
        return None
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT id, phrase, action_type, action_payload FROM custom_commands "
            "WHERE owner_id = ? AND phrase = ?",
            (owner_id, text[:60]),
        ).fetchone()
    return dict(row) if row else None


def delete_custom_command(owner_id: str, command_id: int) -> bool:
    if is_guest(owner_id):
        return False
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM custom_commands WHERE id = ? AND owner_id = ?",
            (int(command_id), owner_id),
        )
    return cur.rowcount > 0

# ── Bölüm E: üretkenlik — notlar ve yapılacaklar (madde 23) ──────────────────

def add_note(owner_id: str, title: str, content: str = "") -> int | None:
    """Madde 23: not yazar; misafirse yazmaz (None döner)."""
    title = (title or "").strip()[:120]
    content = (content or "").strip()[:4000]
    if is_guest(owner_id) or not title:
        return None
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO notes (owner_id, title, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (owner_id, title, content, _now()),
        )
    return int(cur.lastrowid or 0)


def list_notes(owner_id: str, limit: int = 50, query: str = "") -> list[dict[str, Any]]:
    """Sahibinin notlarını (en yeni önce) döndürür; misafirde boş."""
    if is_guest(owner_id):
        return []
    limit = max(1, min(int(limit), 200))
    sql = "SELECT id, title, content, created_at FROM notes WHERE owner_id = ?"
    params: list[Any] = [owner_id]
    if query.strip():
        sql += " AND (title LIKE ? OR content LIKE ?)"
        like = f"%{query.strip()[:100]}%"
        params.extend([like, like])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with closing(connect()) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def delete_note(owner_id: str, note_id: int) -> bool:
    """Sahibine ait değilse False döner (owner izolasyonu)."""
    if is_guest(owner_id):
        return False
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM notes WHERE id = ? AND owner_id = ?",
            (int(note_id), owner_id),
        )
    return cur.rowcount > 0


def add_todo(owner_id: str, title: str) -> int | None:
    """Madde 23: yapılacak ekler; misafirse yazmaz (None döner)."""
    title = (title or "").strip()[:200]
    if is_guest(owner_id) or not title:
        return None
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO todos (owner_id, title, done, created_at) "
            "VALUES (?, ?, 0, ?)",
            (owner_id, title, _now()),
        )
    return int(cur.lastrowid or 0)


def list_todos(owner_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Yapılacakları (açılanlar önce, sonra en yeni) döndürür; misafirde boş."""
    if is_guest(owner_id):
        return []
    limit = max(1, min(int(limit), 500))
    with closing(connect()) as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, title, done, created_at FROM todos "
                "WHERE owner_id = ? ORDER BY done ASC, id DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        ]


def set_todo_done(owner_id: str, todo_id: int, done: bool) -> bool:
    """Yapılacak durumunu değiştirir; sahibine ait değilse False."""
    if is_guest(owner_id):
        return False
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE todos SET done = ? WHERE id = ? AND owner_id = ?",
            (1 if done else 0, int(todo_id), owner_id),
        )
    return cur.rowcount > 0


def delete_todo(owner_id: str, todo_id: int) -> bool:
    if is_guest(owner_id):
        return False
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM todos WHERE id = ? AND owner_id = ?",
            (int(todo_id), owner_id),
        )
    return cur.rowcount > 0


# ── Sohbet geçmişi ───────────────────────────────────────────────────────────

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

