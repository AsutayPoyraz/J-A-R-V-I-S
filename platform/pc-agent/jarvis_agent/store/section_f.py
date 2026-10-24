"""Bölüm F depo yardımcıları (madde 19/20/21/24).

Tablolar database.py içinde (_ensure_section_f_tables) oluşturulur; işlevler
burada yaşar. Erişimler ``database.connect`` / ``database._write_lock`` /
``database._now`` üzerinden DİNAMİK yapılır ki testlerin monkeypatch'lediği
geçici DB her yerde aynı olsun.
"""
from __future__ import annotations

import datetime as _dt
import json
import secrets
import sqlite3
from typing import Any, Optional

from . import database

# XP günlük olay tavanı: puan çiftçiliğini engeller (madde 21 güvenliği).
XP_DAILY_EVENT_CAP = 20
XP_POINTS = {"chat": 2, "file": 5, "voice_note": 4, "macro": 3, "note": 2}
LEVEL_DIVISOR = 50  # level = int(sqrt(xp / 50)) + 1

_SHARE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # karışan karakterler dışlandı


def _now() -> str:
    return database._now()


def _today() -> str:
    return _now()[:10]


def _days_ago_iso(days: int) -> str:
    return (_dt.datetime.now() - _dt.timedelta(days=days)).isoformat(timespec="seconds")


# ── Madde 20: etkinlik akışı ─────────────────────────────────────────────────

def log_activity(owner_id: str, kind: str, detail: str = "") -> None:
    """Etkinlik akışına kayıt; misafirlerde kalıcı tutulmaz (madde 6)."""
    if database.is_guest(owner_id):
        return
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO activity_log (owner_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
            (owner_id, kind, detail[:200], _now()),
        )


def recent_activity(owner_id: str, days: int = 7, limit: int = 100) -> list[dict[str, Any]]:
    since = _days_ago_iso(days)
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, kind, detail, created_at FROM activity_log "
            "WHERE owner_id = ? AND created_at >= ? ORDER BY id DESC LIMIT ?",
            (owner_id, since, limit),
        ).fetchall()
    return [dict(r) for r in rows]

# ── Madde 21: XP / seviye / streak / rozet ───────────────────────────────────

def award_xp(owner_id: str, kind: str) -> int:
    """XP yalnızca sunucu içinde yazılır; istemciye XP yazma ucu YOKTUR.

    Misafirlere XP yazılmaz (madde 6: kalıcı kayıt yok) — manipülasyon ve
    kayıt kirliliği birlikte engellenir.
    """
    if database.is_guest(owner_id):
        return 0
    points = XP_POINTS.get(kind, 1)
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        used = conn.execute(
            "SELECT COUNT(*) AS n FROM xp_events WHERE owner_id = ? AND kind = ? "
            "AND substr(created_at, 1, 10) = ?",
            (owner_id, kind, _today()),
        ).fetchone()["n"]
        if used >= XP_DAILY_EVENT_CAP:
            return 0
        conn.execute(
            "INSERT INTO xp_events (owner_id, kind, points, created_at) VALUES (?, ?, ?, ?)",
            (owner_id, kind, points, _now()),
        )
    _sync_badges(owner_id)
    return points


def _xp_state(conn: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    counts = {
        r["kind"]: r["n"]
        for r in conn.execute(
            "SELECT kind, COUNT(*) AS n FROM xp_events WHERE owner_id = ? GROUP BY kind",
            (owner_id,),
        ).fetchall()
    }
    total = int(
        conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS xp FROM xp_events WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()["xp"]
    )
    level = int((total / LEVEL_DIVISOR) ** 0.5) + 1
    dates = {
        r["d"]
        for r in conn.execute(
            "SELECT DISTINCT substr(created_at, 1, 10) AS d FROM xp_events WHERE owner_id = ?",
            (owner_id,),
        ).fetchall()
    }
    streak = 0
    day = _dt.datetime.now().date()
    if day.isoformat() not in dates:
        day -= _dt.timedelta(days=1)  # bugün XP yoksa seriyi dünden devam ettir
    while day.isoformat() in dates:
        streak += 1
        day -= _dt.timedelta(days=1)
    return {"xp_total": total, "level": level, "streak_days": streak, "counts": counts}


def _badge_rules(state: dict[str, Any]) -> dict[str, bool]:
    c = state["counts"]
    return {
        "first_chat": c.get("chat", 0) >= 1,
        "first_file": c.get("file", 0) >= 1,
        "first_macro": c.get("macro", 0) >= 1,
        "voice_10": c.get("voice_note", 0) >= 10,
        "streak_3": state["streak_days"] >= 3,
        "level_5": state["level"] >= 5,
    }


def _sync_badges(owner_id: str) -> None:
    with database.closing(database.connect()) as conn:
        state = _xp_state(conn, owner_id)
        owned = {
            r["code"]
            for r in conn.execute(
                "SELECT code FROM badges WHERE owner_id = ?", (owner_id,)
            ).fetchall()
        }
        earned = [code for code, ok in _badge_rules(state).items() if ok and code not in owned]
    if not earned:
        return
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        for code in earned:
            conn.execute(
                "INSERT OR IGNORE INTO badges (owner_id, code, earned_at) VALUES (?, ?, ?)",
                (owner_id, code, _now()),
            )
        conn.execute(
            "INSERT INTO activity_log (owner_id, kind, detail, created_at) "
            "VALUES (?, 'badge', ?, ?)",
            (owner_id, ",".join(earned), _now()),
        )

def gamify_status(owner_id: str) -> dict[str, Any]:
    """Seviye, streak, rozetler, günlük görevler ve bugünün XP'si."""
    with database.closing(database.connect()) as conn:
        state = _xp_state(conn, owner_id)
        badges = [
            {"code": r["code"], "earned_at": r["earned_at"]}
            for r in conn.execute(
                "SELECT code, earned_at FROM badges WHERE owner_id = ? ORDER BY earned_at",
                (owner_id,),
            ).fetchall()
        ]
        today_done = {
            r["k"]: r["n"]
            for r in conn.execute(
                "SELECT kind AS k, COUNT(*) AS n FROM xp_events "
                "WHERE owner_id = ? AND substr(created_at, 1, 10) = ? GROUP BY kind",
                (owner_id, _today()),
            ).fetchall()
        }
        today_xp = int(
            conn.execute(
                "SELECT COALESCE(SUM(points), 0) AS xp FROM xp_events "
                "WHERE owner_id = ? AND substr(created_at, 1, 10) = ?",
                (owner_id, _today()),
            ).fetchone()["xp"]
        )
    level = state["level"]
    cur_floor = ((level - 1) ** 2) * LEVEL_DIVISOR
    next_floor = (level**2) * LEVEL_DIVISOR
    progress = (
        int(100 * (state["xp_total"] - cur_floor) / (next_floor - cur_floor))
        if next_floor > cur_floor
        else 0
    )
    tasks = [
        {"code": "chat3", "goal": 3, "done": min(today_done.get("chat", 0), 3)},
        {"code": "voice1", "goal": 1, "done": min(today_done.get("voice_note", 0), 1)},
        {"code": "macro1", "goal": 1, "done": min(today_done.get("macro", 0), 1)},
    ]
    return {
        **state,
        "level_progress": max(0, min(100, progress)),
        "today_xp": today_xp,
        "badges": badges,
        "daily_tasks": tasks,
    }


def leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    """Opsiyonel sıralama: kayıtlı kullanıcılar (owner='user:<id>') XP toplamı."""
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT TRIM(u.first_name || ' ' || u.last_name) AS name, "
            "COALESCE((SELECT SUM(points) FROM xp_events x "
            "WHERE x.owner_id = 'user:' || u.id), 0) AS xp "
            "FROM users u ORDER BY xp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"name": r["name"] or "Anonim", "xp": int(r["xp"])} for r in rows if r["xp"] > 0]

# ── Madde 19: dosya etiketleri ───────────────────────────────────────────────

def norm_tag(tag: str) -> str:
    """Etiket normalizasyonu: küçük harf + Türkçe İ kaynaklı birleşen noktayı sil.

    Python'da "İş".lower() → "i\\u0307ş" (i + U+0307) olur; aramada "iş" ile
    eşleşmesi için birleşen nokta (U+0307) kaldırılır.
    """
    return tag.strip().lower().replace("\u0307", "")


def set_file_tags(owner_id: str, file_name: str, tags: list[str]) -> None:
    clean = ",".join(norm_tag(t)[:30] for t in tags if t.strip())[:300]
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO file_tags (owner_id, file_name, tags, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(owner_id, file_name) DO UPDATE SET "
            "tags=excluded.tags, updated_at=excluded.updated_at",
            (owner_id, file_name[:200], clean, _now()),
        )


def file_tags_map(owner_id: str) -> dict[str, list[str]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT file_name, tags FROM file_tags WHERE owner_id = ?", (owner_id,)
        ).fetchall()
    return {r["file_name"]: [t for t in r["tags"].split(",") if t] for r in rows}


# ── Madde 19: sesli notlar ───────────────────────────────────────────────────

def add_voice_note(owner_id: str, text: str) -> int:
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO voice_notes (owner_id, text, created_at) VALUES (?, ?, ?)",
            (owner_id, text[:4000], _now()),
        )
    mid = int(cur.lastrowid or 0)
    log_activity(owner_id, "voice_note.add", text[:60])
    award_xp(owner_id, "voice_note")
    return mid


def list_voice_notes(owner_id: str, q: str = "", limit: int = 50) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, text, created_at FROM voice_notes WHERE owner_id = ? "
            "AND text LIKE ? ORDER BY id DESC LIMIT ?",
            (owner_id, f"%{q}%", limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_voice_note(owner_id: str, note_id: int) -> bool:
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM voice_notes WHERE owner_id = ? AND id = ?", (owner_id, note_id)
        )
    return cur.rowcount > 0

# ── Madde 20: makrolar / kısayollar ──────────────────────────────────────────

def add_macro(owner_id: str, name: str, steps: list[dict[str, Any]]) -> int | None:
    try:
        payload = json.dumps(steps, ensure_ascii=False)[:2000]
    except (TypeError, ValueError):
        return None
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        try:
            cur = conn.execute(
                "INSERT INTO macros (owner_id, name, steps, created_at) VALUES (?, ?, ?, ?)",
                (owner_id, name[:60], payload, _now()),
            )
        except sqlite3.IntegrityError:
            return None  # yinelenen makro adı
    mid = int(cur.lastrowid or 0)
    log_activity(owner_id, "macro.create", name)
    # XP kilidi yeniden alınmadan (with bloğu kapandıktan sonra) verilir.
    award_xp(owner_id, "macro")
    return mid


def list_macros(owner_id: str) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, name, steps, created_at FROM macros WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            steps = json.loads(r["steps"])
        except ValueError:
            steps = []
        out.append(
            {"id": r["id"], "name": r["name"], "steps": steps, "created_at": r["created_at"]}
        )
    return out


def delete_macro(owner_id: str, macro_id: int) -> bool:
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM macros WHERE owner_id = ? AND id = ?", (owner_id, macro_id)
        )
    return cur.rowcount > 0

# ── Madde 20: paylaşılan oturumlar (Shared Jarvis Sessions) ──────────────────

def create_shared_session(owner_id: str, title: str = "") -> str:
    code = "".join(secrets.choice(_SHARE_ALPHABET) for _ in range(6))
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO shared_sessions (code, owner_id, title, created_at) VALUES (?, ?, ?, ?)",
            (code, owner_id, title[:80], _now()),
        )
        conn.execute(
            "INSERT INTO shared_members (code, owner_id, display_name, joined_at) "
            "VALUES (?, ?, 'host', ?)",
            (code, owner_id, _now()),
        )
    log_activity(owner_id, "shared.create", code)
    return code


def shared_session_info(code: str) -> Optional[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT code, owner_id, title, created_at FROM shared_sessions WHERE code = ?",
            (code.upper(),),
        ).fetchone()
        if row is None:
            return None
        members = [
            dict(m)
            for m in conn.execute(
                "SELECT owner_id, display_name, joined_at FROM shared_members "
                "WHERE code = ? ORDER BY joined_at",
                (code.upper(),),
            ).fetchall()
        ]
    info = dict(row)
    info["members"] = members
    return info


def join_shared_session(code: str, owner_id: str, display_name: str) -> bool:
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        exists = conn.execute(
            "SELECT 1 FROM shared_sessions WHERE code = ?", (code.upper(),)
        ).fetchone()
        if exists is None:
            return False
        conn.execute(
            "INSERT INTO shared_members (code, owner_id, display_name, joined_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(code, owner_id) DO UPDATE SET "
            "display_name=excluded.display_name",
            (code.upper(), owner_id, display_name[:40], _now()),
        )
    return True


def add_shared_message(
    code: str, owner_id: str, display_name: str, role: str, content: str
) -> int:
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO shared_messages (code, owner_id, display_name, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (code.upper(), owner_id, display_name[:40], role, content[:4000], _now()),
        )
    return int(cur.lastrowid or 0)


def list_shared_messages(code: str, since_id: int = 0, limit: int = 200) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT id, owner_id, display_name, role, content, created_at FROM shared_messages "
            "WHERE code = ? AND id > ? ORDER BY id ASC LIMIT ?",
            (code.upper(), since_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_shared_session(code: str, owner_id: str) -> bool:
    """Yalnızca oturumu açan owner silebilir (üyeler değil)."""
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        row = conn.execute(
            "SELECT owner_id FROM shared_sessions WHERE code = ?", (code.upper(),)
        ).fetchone()
        if row is None or row["owner_id"] != owner_id:
            return False
        conn.execute("DELETE FROM shared_sessions WHERE code = ?", (code.upper(),))
        conn.execute("DELETE FROM shared_members WHERE code = ?", (code.upper(),))
        conn.execute("DELETE FROM shared_messages WHERE code = ?", (code.upper(),))
    return True

# ── Madde 24: analitik — özet ve birleşik arama ──────────────────────────────

def analytics_summary(owner_id: str, days: int = 14) -> dict[str, Any]:
    since = _days_ago_iso(days)
    per_day: dict[str, dict[str, int]] = {}
    with database.closing(database.connect()) as conn:
        for label, table in (
            ("chat", "messages"),
            ("voice_note", "voice_notes"),
            ("note", "notes"),
        ):
            for r in conn.execute(
                f"SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM {table} "
                f"WHERE owner_id = ? AND created_at >= ? GROUP BY d",
                (owner_id, since),
            ).fetchall():
                per_day.setdefault(r["d"], {})[label] = r["n"]
        for r in conn.execute(
            "SELECT substr(created_at, 1, 10) AS d, kind, COUNT(*) AS n FROM activity_log "
            "WHERE owner_id = ? AND created_at >= ? GROUP BY d, kind",
            (owner_id, since),
        ).fetchall():
            # "macro.create" gibi alt eylemler üst kategoriye katlanır (madde 24)
            label = r["kind"].split(".", 1)[0]
            bucket = per_day.setdefault(r["d"], {})
            bucket[label] = bucket.get(label, 0) + r["n"]
    days_list = [{"date": d, **counts} for d, counts in sorted(per_day.items())]
    totals: dict[str, int] = {}
    for entry in days_list:
        for k, v in entry.items():
            if k != "date":
                totals[k] = totals.get(k, 0) + int(v)
    return {"days": days_list, "totals": totals, "period_days": days}


def history_search(
    owner_id: str,
    q: str = "",
    tag: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Etiketli + tarih aralıklı birleşik arama: sohbet/not/sesli not/dosya."""
    like = f"%{q}%"
    results: list[dict[str, Any]] = []

    def _in_range(created: str) -> bool:
        if date_from and created[:10] < date_from:
            return False
        if date_to and created[:10] > date_to:
            return False
        return True

    with database.closing(database.connect()) as conn:
        for r in conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE owner_id = ? "
            "AND content LIKE ? ORDER BY id DESC",
            (owner_id, like),
        ).fetchall():
            if _in_range(r["created_at"]):
                results.append(
                    {"source": "chat", "id": r["id"], "text": r["content"][:200],
                     "created_at": r["created_at"]}
                )
        for r in conn.execute(
            "SELECT id, title, content, created_at FROM notes WHERE owner_id = ? "
            "AND (title LIKE ? OR content LIKE ?) ORDER BY id DESC",
            (owner_id, like, like),
        ).fetchall():
            if _in_range(r["created_at"]):
                results.append(
                    {"source": "note", "id": r["id"], "text": r["title"][:120],
                     "detail": r["content"][:120], "created_at": r["created_at"]}
                )
        for r in conn.execute(
            "SELECT id, text, created_at FROM voice_notes WHERE owner_id = ? "
            "AND text LIKE ? ORDER BY id DESC",
            (owner_id, like),
        ).fetchall():
            if _in_range(r["created_at"]):
                results.append(
                    {"source": "voice_note", "id": r["id"], "text": r["text"][:200],
                     "created_at": r["created_at"]}
                )
        tag_norm = norm_tag(tag)
        for r in conn.execute(
            "SELECT file_name, tags, updated_at FROM file_tags WHERE owner_id = ?",
            (owner_id,),
        ).fetchall():
            # Python tarafında `in` denetimi; % jokeri YOK (LIKE değil)
            if tag_norm and tag_norm not in r["tags"].lower():
                continue
            if q and q.lower() not in r["file_name"].lower():
                continue
            if not _in_range(r["updated_at"]):
                continue
            results.append(
                {"source": "file", "id": r["file_name"], "text": r["file_name"][:200],
                 "tags": r["tags"], "created_at": r["updated_at"]}
            )
    results.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return results[:limit]


# ── Madde 19/24: Cloud Backup MVP — dışa/içe aktarma ─────────────────────────

def export_owner_data(owner_id: str) -> dict[str, Any]:
    """Owner verisinin tam JSON dökümü (zip'e gömülür)."""
    with database.closing(database.connect()) as conn:
        data: dict[str, Any] = {"version": 1, "exported_at": _now(), "owner": owner_id}
        row = conn.execute(
            "SELECT * FROM user_settings WHERE owner_id = ?", (owner_id,)
        ).fetchone()
        data["settings"] = dict(row) if row else None
        for key, sql in (
            ("messages", "SELECT role, content, created_at FROM messages WHERE owner_id = ?"),
            ("notes", "SELECT title, content, created_at FROM notes WHERE owner_id = ?"),
            ("todos", "SELECT title, done, created_at FROM todos WHERE owner_id = ?"),
            ("memories", "SELECT content, created_at FROM memories WHERE owner_id = ?"),
            ("voice_notes", "SELECT text, created_at FROM voice_notes WHERE owner_id = ?"),
            ("macros", "SELECT name, steps, created_at FROM macros WHERE owner_id = ?"),
            ("file_tags", "SELECT file_name, tags FROM file_tags WHERE owner_id = ?"),
        ):
            data[key] = [dict(r) for r in conn.execute(sql, (owner_id,)).fetchall()]
    return data


def import_owner_data(owner_id: str, data: dict[str, Any]) -> dict[str, int]:
    """Yedek JSON'unu mevcut owner'a ekler; bozuk/yinelenen kayıtlar atlanır."""
    counts: dict[str, int] = {}
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        n = 0
        for item in data.get("messages") or []:
            conn.execute(
                "INSERT INTO messages (owner_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (owner_id, str(item.get("role", "user"))[:10],
                 str(item.get("content", ""))[:4000], str(item.get("created_at") or _now())),
            )
            n += 1
        counts["messages"] = n
        n = 0
        for item in data.get("notes") or []:
            conn.execute(
                "INSERT INTO notes (owner_id, title, content, created_at) VALUES (?, ?, ?, ?)",
                (owner_id, str(item.get("title", ""))[:120],
                 str(item.get("content", ""))[:4000], str(item.get("created_at") or _now())),
            )
            n += 1
        counts["notes"] = n
        n = 0
        for item in data.get("voice_notes") or []:
            conn.execute(
                "INSERT INTO voice_notes (owner_id, text, created_at) VALUES (?, ?, ?)",
                (owner_id, str(item.get("text", ""))[:4000], str(item.get("created_at") or _now())),
            )
            n += 1
        counts["voice_notes"] = n
        n = 0
        for item in data.get("macros") or []:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO macros (owner_id, name, steps, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (owner_id, str(item.get("name", ""))[:60],
                     str(item.get("steps", "[]"))[:2000], str(item.get("created_at") or _now())),
                )
                n += 1
            except sqlite3.IntegrityError:
                continue
        counts["macros"] = n
        n = 0
        for item in data.get("file_tags") or []:
            conn.execute(
                "INSERT OR IGNORE INTO file_tags (owner_id, file_name, tags, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (owner_id, str(item.get("file_name", ""))[:200],
                 str(item.get("tags", ""))[:300], _now()),
            )
            n += 1
        counts["file_tags"] = n
    return counts


# ── Madde 20: shared session yetkilendirme yardımcıları ──────────────────────

def shared_member_codes(owner_id: str) -> set[str]:
    """Kullanıcının üyesi olduğu oturum kodları (WS yetkilendirmesi için)."""
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT code FROM shared_members WHERE owner_id = ?", (owner_id,)
        ).fetchall()
    return {r["code"] for r in rows}