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

def delete_secure_note(owner_id: str, note_id: int) -> bool:
    """Şifreli notu siler; yalnız sahibi silebilir. Misafir silmez."""
    if database.is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM secure_notes WHERE owner_id = ? AND id = ?", (owner_id, note_id)
        )
    deleted = cur.rowcount > 0
    if deleted:
        audit(owner_id, "vault.note_deleted")
    return deleted


# ── Madde 25: hassas işlem izinleri ──────────────────────────────────────────

def get_permissions(owner_id: str) -> dict[str, bool]:
    """Varsayılan (tümü açık) + owner'ın kalıcı kapatmalarını birleştirir."""
    perms: dict[str, bool] = {key: True for key in PERMISSIONS}
    if database.is_guest(owner_id):
        return perms
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT permission, allowed FROM permission_overrides WHERE owner_id = ?",
            (owner_id,),
        ).fetchall()
    for row in rows:
        if row["permission"] in perms:
            perms[row["permission"]] = bool(row["allowed"])
    return perms


def set_permission(owner_id: str, permission: str, allowed: bool) -> None:
    """Tek izni kalıcı açar/kapatır (misafir no-op; bilinmeyen anahtar yok sayılır)."""
    if database.is_guest(owner_id) or permission not in PERMISSIONS:
        return
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO permission_overrides (owner_id, permission, allowed, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(owner_id, permission) DO UPDATE SET "
            "allowed = excluded.allowed, updated_at = excluded.updated_at",
            (owner_id, permission, 1 if allowed else 0, _now()),
        )
    audit(owner_id, "permissions.change", detail=f"{permission}={allowed}")


def has_permission(owner_id: str, permission: str) -> bool:
    """Hassas uçların kapı fonksiyonu; bilinmeyen anahtar daima reddedilir."""
    if permission not in PERMISSIONS:
        return False
    return get_permissions(owner_id).get(permission, False)


# ── Madde 27: ruh hâli + günlük kullanım ─────────────────────────────────────

def set_mood(owner_id: str, mood: str) -> bool:
    """Günlük ruh hâlini user_settings'e yazar (sohbet üslubuna girdi)."""
    if mood not in MOODS or database.is_guest(owner_id):
        return False
    database.update_user_settings(owner_id, {"mood": mood, "mood_updated_at": _now()})
    return True


def get_mood(owner_id: str) -> str:
    mood = str(database.get_user_settings(owner_id).get("mood") or "neutral")
    return mood if mood in MOODS else "neutral"


def touch_usage(owner_id: str, delta_seconds: int | None = None) -> None:
    """Günlük kullanım dakikalarını biriktirir (madde 27 limit kontrolü).

    delta_seconds verilmezse son dokunuştan bu yana geçen süre kullanılır
    (boşta bekleyen sekme süresini sınırlamak için 60 sn tavan). Misafir
    hiç kayıt üretmez (madde 6).
    """
    if not owner_id or database.is_guest(owner_id):
        return
    now = _dt.datetime.now()
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        delta = 0
        if delta_seconds is None:
            row = conn.execute(
                "SELECT updated_at FROM usage_days WHERE owner_id = ? AND day = ?",
                (owner_id, _today()),
            ).fetchone()
            if row and row["updated_at"]:
                try:
                    last = _dt.datetime.fromisoformat(str(row["updated_at"]))
                    delta = int((now - last).total_seconds())
                except ValueError:
                    delta = 0
            delta = max(0, min(delta, 60))
        else:
            delta = max(0, min(int(delta_seconds), 3600))
        conn.execute(
            "INSERT INTO usage_days (owner_id, day, minutes, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(owner_id, day) DO UPDATE SET "
            "updated_at = excluded.updated_at",
            (owner_id, _today(), 0, now.isoformat(timespec="seconds")),
        )
        add_minutes = delta // 60
        if add_minutes:
            conn.execute(
                "UPDATE usage_days SET minutes = minutes + ? "
                "WHERE owner_id = ? AND day = ?",
                (add_minutes, owner_id, _today()),
            )


def usage_today(owner_id: str) -> dict[str, Any]:
    """Bugünün kullanım dakikaları + günlük limit durumu."""
    limit = int(database.get_user_settings(owner_id).get("daily_limit_minutes") or 0)
    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT minutes FROM usage_days WHERE owner_id = ? AND day = ?",
            (owner_id, _today()),
        ).fetchone()
    minutes = int(row["minutes"]) if row else 0
    return {
        "minutes": minutes,
        "limit": limit,
        "limit_reached": bool(limit and minutes >= limit),
    }
