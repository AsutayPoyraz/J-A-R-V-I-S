"""JARVIS v11 veri katmanı — görevler, makrolar, alışkanlıklar, özetler.

Tablolar ``database._SCHEMA`` içinde tek merkezden oluşturulur (mega prompt
genel notu); işlevler burada yaşar. Misafir sahipleri (owner 'guest:*')
kalıcı yazamaz — yazma işlevleri no-op döner (madde 6 tutarlılığı).
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Any, Optional

from . import database

PRIORITIES = ("low", "medium", "high", "urgent")
STATUSES = ("todo", "in_progress", "done")
MACRO_STEP_TYPES = ("chat", "api_call", "delay")


def _now() -> str:
    return database._now()


def _today() -> str:
    return _now()[:10]


def _is_guest(owner_id: str) -> bool:
    return database.is_guest(owner_id)


# ══ Özellik 6: projeler / görevler / alt görevler ════════════════════════════

def list_projects(owner_id: str) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_project(owner_id: str, name: str, color: str = "#22d3ee") -> Optional[dict]:
    if _is_guest(owner_id) or not (name or "").strip():
        return None
    try:
        with database._write_lock, database.closing(database.connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO projects (owner_id, name, color, created_at) "
                "VALUES (?, ?, ?, ?)",
                (owner_id, name.strip()[:80], color[:16], _now()),
            )
            pid = cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    return get_project(owner_id, int(pid))


def get_project(owner_id: str, project_id: int) -> Optional[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE owner_id = ? AND id = ?",
            (owner_id, project_id),
        ).fetchone()
    return dict(row) if row else None


def delete_project(owner_id: str, project_id: int) -> bool:
    if _is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "UPDATE tasks SET project_id = NULL WHERE owner_id = ? AND project_id = ?",
            (owner_id, project_id),
        )
        cur = conn.execute(
            "DELETE FROM projects WHERE owner_id = ? AND id = ?",
            (owner_id, project_id),
        )
    return cur.rowcount > 0


def list_tasks(
    owner_id: str,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = (
        "SELECT t.*, p.name AS project_name FROM tasks t "
        "LEFT JOIN projects p ON p.id = t.project_id "
        "WHERE t.owner_id = ?"
    )
    params: list[Any] = [owner_id]
    if project_id is not None:
        query += " AND t.project_id = ?"
        params.append(project_id)
    if status in STATUSES:
        query += " AND t.status = ?"
        params.append(status)
    query += " ORDER BY t.id DESC LIMIT ?"
    params.append(int(limit))
    with database.closing(database.connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    tasks = [dict(r) for r in rows]
    if tasks:
        ids = [t["id"] for t in tasks]
        marks = ",".join("?" for _ in ids)
        with database.closing(database.connect()) as conn:
            subrows = conn.execute(
                f"SELECT * FROM subtasks WHERE task_id IN ({marks}) ORDER BY id",
                ids,
            ).fetchall()
        for t in tasks:
            t["subtasks"] = [dict(s) for s in subrows if s["task_id"] == t["id"]]
    return tasks


def create_task(
    owner_id: str,
    title: str,
    project: str = "",
    priority: str = "medium",
    due_date: str = "",
    description: str = "",
) -> Optional[dict[str, Any]]:
    """Yeni görev; ``project`` proje ADIYSA otomatik oluşturulur (LLM aracı)."""
    if _is_guest(owner_id) or not (title or "").strip():
        return None
    priority = priority if priority in PRIORITIES else "medium"
    project_id: Optional[int] = None
    if (project or "").strip():
        with database.closing(database.connect()) as conn:
            existing = conn.execute(
                "SELECT id FROM projects WHERE owner_id = ? AND name = ?",
                (owner_id, project.strip()[:80]),
            ).fetchone()
        project_id = (existing["id"] if existing else None) or (
            create_project(owner_id, project) or {}
        ).get("id")
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO tasks (owner_id, project_id, title, description, priority, "
            "status, due_date, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                project_id,
                title.strip()[:200],
                (description or "").strip()[:2000],
                priority,
                "todo",
                due_date.strip() or None,
                _now(),
                _now(),
            ),
        )
        task_id = cur.lastrowid
    for row in list_tasks(owner_id, limit=50):
        if row["id"] == task_id:
            return row
    return {"id": task_id, "title": title, "status": "todo", "priority": priority}


def update_task(owner_id: str, task_id: int, patch: dict[str, Any]) -> Optional[dict]:
    if _is_guest(owner_id):
        return None
    sets: list[str] = []
    params: list[Any] = []
    if "title" in patch and str(patch["title"]).strip():
        sets.append("title = ?")
        params.append(str(patch["title"]).strip()[:200])
    if "description" in patch:
        sets.append("description = ?")
        params.append(str(patch["description"] or "")[:2000])
    if "priority" in patch and patch["priority"] in PRIORITIES:
        sets.append("priority = ?")
        params.append(patch["priority"])
    if "status" in patch and patch["status"] in STATUSES:
        sets.append("status = ?")
        params.append(patch["status"])
    if "due_date" in patch:
        sets.append("due_date = ?")
        params.append(str(patch["due_date"] or "").strip() or None)
    if "project_id" in patch:
        sets.append("project_id = ?")
        params.append(patch["project_id"])
    if not sets:
        return None
    sets.append("updated_at = ?")
    params.append(_now())
    params.extend([owner_id, task_id])
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE owner_id = ? AND id = ?",
            params,
        )
    if cur.rowcount == 0:
        return None
    for row in list_tasks(owner_id):
        if row["id"] == task_id:
            return row
    return None


def complete_task(owner_id: str, task_id: int) -> Optional[dict[str, Any]]:
    return update_task(owner_id, task_id, {"status": "done"})


def delete_task(owner_id: str, task_id: int) -> bool:
    if _is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE owner_id = ? AND id = ?", (owner_id, task_id)
        )
    return cur.rowcount > 0


def add_subtask(owner_id: str, task_id: int, title: str) -> Optional[dict]:
    if _is_guest(owner_id) or not (title or "").strip():
        return None
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        owner = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        if not owner:
            return None
        cur = conn.execute(
            "INSERT INTO subtasks (task_id, title, done) VALUES (?, ?, 0)",
            (task_id, title.strip()[:200]),
        )
        sid = cur.lastrowid
    return {"id": sid, "task_id": task_id, "title": title.strip()[:200], "done": 0}


def update_subtask(
    owner_id: str, subtask_id: int, done: Optional[bool] = None,
    title: Optional[str] = None,
) -> bool:
    if _is_guest(owner_id):
        return False
    sets: list[str] = []
    params: list[Any] = []
    if done is not None:
        sets.append("done = ?")
        params.append(1 if done else 0)
    if title and title.strip():
        sets.append("title = ?")
        params.append(title.strip()[:200])
    if not sets:
        return False
    params.append(subtask_id)
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(f"UPDATE subtasks SET {', '.join(sets)} WHERE id = ?", params)
    return cur.rowcount > 0


def delete_subtask(owner_id: str, subtask_id: int) -> bool:
    if _is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute("DELETE FROM subtasks WHERE id = ?", (subtask_id,))
    return cur.rowcount > 0


def tasks_done_today(owner_id: str) -> int:
    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE owner_id = ? AND "
            "status = 'done' AND updated_at >= ?",
            (owner_id, _today()),
        ).fetchone()
    return int(row["n"]) if row else 0


# ══ Özellik 9: makrolar ══════════════════════════════════════════════════════

def _parse_steps(raw: str) -> list[dict]:
    try:
        steps = json.loads(raw or "[]")
    except ValueError:
        return []
    return [s for s in steps if isinstance(s, dict)]


def list_macros(owner_id: str) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM command_macros WHERE owner_id = ? ORDER BY id DESC", (owner_id,)
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["steps"] = _parse_steps(item.get("steps") or "")
        out.append(item)
    return out


def get_macro(owner_id: str, macro_id: int) -> Optional[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT * FROM command_macros WHERE owner_id = ? AND id = ?", (owner_id, macro_id)
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["steps"] = _parse_steps(item.get("steps") or "")
    return item


def create_macro(
    owner_id: str, name: str, trigger_phrase: str, steps: list
) -> Optional[dict]:
    if _is_guest(owner_id) or not (name or "").strip() or not (trigger_phrase or "").strip():
        return None
    clean_steps = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        stype = str(step.get("type") or "").strip().lower()
        if stype not in MACRO_STEP_TYPES:
            continue
        clean_steps.append({"type": stype, "params": dict(step.get("params") or {})})
    if not clean_steps:
        return None
    try:
        with database._write_lock, database.closing(database.connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO command_macros (owner_id, name, trigger_phrase, steps, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    owner_id,
                    name.strip()[:80],
                    (trigger_phrase or "").strip().lower()[:120],
                    json.dumps(clean_steps[:20], ensure_ascii=False),
                    _now(),
                ),
            )
            mid = cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    return get_macro(owner_id, int(mid))


def find_macro_by_trigger(owner_id: str, text: str) -> Optional[dict[str, Any]]:
    """Tetikleyici ifadeyi bulanık eşleştirir (voice/textmatch kullanır)."""
    from ..voice.textmatch import match_phrase

    for macro in list_macros(owner_id):
        phrase = str(macro.get("trigger_phrase") or "")
        if phrase and match_phrase(text, phrase, threshold=0.86):
            return macro
    return None


def delete_macro(owner_id: str, macro_id: int) -> bool:
    if _is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "DELETE FROM command_macros WHERE owner_id = ? AND id = ?", (owner_id, macro_id)
        )
    return cur.rowcount > 0


# ══ Özellik 10: alışkanlıklar + üretkenlik ═══════════════════════════════════

def list_habits(owner_id: str) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM habits WHERE owner_id = ? ORDER BY id", (owner_id,)
        ).fetchall()
    habits = []
    today = _today()
    since = (datetime.date.today() - datetime.timedelta(days=59)).isoformat()
    for row in rows:
        item = dict(row)
        with database.closing(database.connect()) as conn:
            logs = conn.execute(
                "SELECT date, completed FROM habit_logs WHERE habit_id = ? "
                "AND date >= ? ORDER BY date DESC LIMIT 60",
                (item["id"], since),
            ).fetchall()
        log_map = {l["date"]: bool(l["completed"]) for l in logs}
        item["today_done"] = log_map.get(today, False)
        # Streak: bugün dahil geriye doğru kesintisiz tamamlanma sayısı.
        streak = 0
        cursor = datetime.date.today()
        if not log_map.get(cursor.isoformat()):
            cursor -= datetime.timedelta(days=1)  # bugün henüz işaretlenmemiş olabilir
        while log_map.get(cursor.isoformat()):
            streak += 1
            cursor -= datetime.timedelta(days=1)
        item["streak"] = streak
        item["logs"] = [
            {"date": l["date"], "completed": bool(l["completed"])} for l in logs
        ]
        habits.append(item)
    return habits


def create_habit(
    owner_id: str, name: str, frequency: str = "daily",
    color: str = "#a78bfa", icon: str = "check",
) -> Optional[dict]:
    if _is_guest(owner_id) or not (name or "").strip():
        return None
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO habits (owner_id, name, frequency, color, icon, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                name.strip()[:80],
                frequency if frequency in ("daily", "weekly") else "daily",
                (color or "#a78bfa")[:16],
                (icon or "check")[:16],
                _now(),
            ),
        )
        hid = cur.lastrowid
    with database.closing(database.connect()) as conn:
        row = conn.execute("SELECT * FROM habits WHERE id = ?", (hid,)).fetchone()
    return dict(row) if row else None


def delete_habit(owner_id: str, habit_id: int) -> bool:
    if _is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "DELETE FROM habit_logs WHERE habit_id IN "
            "(SELECT id FROM habits WHERE owner_id = ? AND id = ?)",
            (owner_id, habit_id),
        )
        cur = conn.execute(
            "DELETE FROM habits WHERE owner_id = ? AND id = ?", (owner_id, habit_id)
        )
    return cur.rowcount > 0


def log_habit(owner_id: str, habit_id: int, completed: bool = True, note: str = "") -> bool:
    if _is_guest(owner_id):
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        owner = conn.execute(
            "SELECT 1 FROM habits WHERE id = ? AND owner_id = ?",
            (habit_id, owner_id),
        ).fetchone()
        if not owner:
            return False
        conn.execute(
            "INSERT INTO habit_logs (habit_id, owner_id, date, completed, note) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(habit_id, date) DO UPDATE SET "
            "completed = excluded.completed, note = excluded.note",
            (habit_id, owner_id, _today(), 1 if completed else 0, note[:200]),
        )
    return True


def habit_stats(owner_id: str) -> dict[str, Any]:
    """Streak / tamamlama oranı / haftalık trend (Özellik 10.5)."""
    habits = list_habits(owner_id)
    if not habits:
        return {"total": 0, "best_streak": 0, "completion_rate": 0.0, "week": []}
    best = max((h["streak"] for h in habits), default=0)
    week = []
    total_slots, done_slots = 0, 0
    for offset in range(6, -1, -1):
        day = (datetime.date.today() - datetime.timedelta(days=offset)).isoformat()
        day_done = sum(
            1 for h in habits
            if any(l["date"] == day and l["completed"] for l in h["logs"])
        )
        week.append({"date": day, "done": day_done, "of": len(habits)})
        total_slots += len(habits)
        done_slots += day_done
    rate = round(done_slots / total_slots * 100, 1) if total_slots else 0.0
    return {
        "total": len(habits),
        "best_streak": best,
        "completion_rate": rate,
        "week": week,
    }


def add_productivity_session(
    owner_id: str, focus_minutes: int, mood: int = 3, notes: str = ""
) -> Optional[dict]:
    if _is_guest(owner_id):
        return None
    mood = max(1, min(5, int(mood or 3)))
    focus = max(0, min(1440, int(focus_minutes or 0)))
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO productivity_sessions (owner_id, date, focus_minutes, mood, "
            "notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (owner_id, _today(), focus, mood, (notes or "")[:500], _now()),
        )
        sid = cur.lastrowid
    return {"id": sid, "date": _today(), "focus_minutes": focus, "mood": mood}


def productivity_insights_data(owner_id: str, days: int = 7) -> list[dict]:
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT date, SUM(focus_minutes) AS focus, AVG(mood) AS mood "
            "FROM productivity_sessions WHERE owner_id = ? AND date >= ? "
            "GROUP BY date ORDER BY date",
            (owner_id, since),
        ).fetchall()
    return [
        {
            "date": r["date"],
            "focus_minutes": int(r["focus"] or 0),
            "mood": round(float(r["mood"] or 3), 1),
        }
        for r in rows
    ]


# ══ Özellik 11: günlük özetler ═══════════════════════════════════════════════

def save_summary(owner_id: str, date: str, content: str, channels: str) -> bool:
    if _is_guest(owner_id) or not (content or "").strip():
        return False
    with database._write_lock, database.closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO daily_summaries (owner_id, date, content, channels, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(owner_id, date) DO UPDATE SET "
            "content = excluded.content, channels = excluded.channels, "
            "created_at = excluded.created_at",
            (owner_id, date, content[:8000], channels[:120], _now()),
        )
    return True


def list_summaries(owner_id: str, limit: int = 30) -> list[dict[str, Any]]:
    with database.closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM daily_summaries WHERE owner_id = ? "
            "ORDER BY date DESC LIMIT ?",
            (owner_id, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]



