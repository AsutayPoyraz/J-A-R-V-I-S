"""Bölüm G store katmanı (madde 25/27).

- security_events: güvenlik denetim kaydı (indirilebilir CSV)
- secure_notes: istemci tarafı şifreli notlar — sunucu yalnız base64 şifreli
  metin saklar; anahtar istemcide kalır (E2EE MVP, sınırlar raporda)
- permission_overrides: hassas işlemler için ayrıntılı izin yönetimi
- mood_log: günlük ruh hâli (sohbet üslubuna girdi)
"""
from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from typing import Any

from . import database

log = logging.getLogger("jarvis.store.section_g")

# Madde 25: izin verilecek hassas işlem anahtarları (varsayılan: tümü açık)
PERMISSIONS: tuple[str, ...] = (
    "shutdown",
    "files.read",
    "files.write",
    "camera",
    "screen_capture",
    "smart_home",
)

# Madde 27: ruh hâli seçenekleri (sohbet üslubuna girdi)
MOODS: tuple[str, ...] = ("neutral", "focused", "tired", "stressed", "cheerful")

_AUDIT_KEEP = 500  # owner başına tutulan maksimum olay sayısı


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return _dt.datetime.now().date().isoformat()


# ── Madde 25: güvenlik denetim kaydı ─────────────────────────────────────────

def audit(owner_id: str, event_type: str, detail: str = "", ip: str = "") -> None:
    """Denetim olayı yazar; HİÇBİR KOŞULDA isteği bozmaz.

    Misafirler kalıcı kayıt üretmez (madde 6) — audit yalnız gerçek sahiplere.
    """
    try:
        if not owner_id or database.is_guest(owner_id):
            return
        with database._write_lock, database.closing(database.connect()) as conn, conn:
            conn.execute(
                "INSERT INTO security_events (owner_id, event_type, detail, ip, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (owner_id, event_type[:40], (detail or "")[:200], (ip or "")[:64], _now()),
            )
            # Kayıt büyümesini sınırla: en yeni _AUDIT_KEEP olayı kalır.
            conn.execute(
                "DELETE FROM security_events WHERE owner_id = ? AND id NOT IN "
                "(SELECT id FROM security_events WHERE owner_id = ? "
                "ORDER BY id DESC LIMIT ?)",
                (owner_id, owner_id, _AUDIT_KEEP),
            )
    except sqlite3.Error:
        log.exception("audit yazılamadı (event=%s)", event_type)


def list_audit(owner_id: str, days: int = 30, limit: int = 500) -> list[dict[str, Any]]:
    """Son `days` günün denetim olayları (en yeni önce)."""
    limit = max(1, min(int(limit), 1000))
    since = (_dt.datetime.now() - _dt.timedelta(days=max(1, min(days, 365)))).isoformat()
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, event_type, detail, ip, created_at FROM security_events "
            "WHERE owner_id = ? AND created_at >= ? ORDER BY id DESC LIMIT ?",
            (owner_id, since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Madde 25: istemci tarafı şifreli notlar (E2EE MVP) ───────────────────────

def add_secure_note(owner_id: str, title_cipher: str, body_cipher: str) -> int | None:
    """Şifreli not yazar; plaintext backend'e hiç ulaşmaz. Misafir yazamaz."""
    if database.is_guest(owner_id):
        return None
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO secure_notes (owner_id, title_cipher, body_cipher, created_at) "
            "VALUES (?, ?, ?, ?)",
            (owner_id, title_cipher[:4000], body_cipher[:20000], _now()),
        )
    audit(owner_id, "vault.note_added")
    return int(cur.lastrowid or 0)


def list_secure_notes(owner_id: str) -> list[dict[str, Any]]:
    if database.is_guest(owner_id):
        return []
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, title_cipher, body_cipher, created_at FROM secure_notes "
            "WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(r) for r in rows]

# __PART2__
