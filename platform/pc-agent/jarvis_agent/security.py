"""Cihaz eşleştirme ve güvenlik katmanı (Faz 2).

Model (kişisel kullanım, makul güvenlik):
- PC'deki yerel arayüz (loopback) daima güvenilir: token istemez.
- Telefon/LAN cihazları: PC ekranında gösterilen 6 haneli kodla eşleşir,
  karşılığında uzun ömürlü ``device_token`` alır (SQLite'ta SHA-256 özeti).
- ``JARVIS_PAIRING_REQUIRED=1`` (veya bind=0.0.0.0) ise /api/* uçları
  loopback olmayan isteklerden geçerli token ister; /api/pair/* ve
  /api/health daima açıktır.
"""
from __future__ import annotations

import hashlib
import secrets
import socket
import sqlite3
import threading
import time
import re
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

from . import config

_CODE_TTL_SECONDS = 300          # eşleştirme kodu 5 dk geçerli
_DB_LOCK = threading.Lock()
_PAIR_LOCK = threading.Lock()
_DB_PATH: Optional[Path] = None

_pending_code: dict[str, Any] = {}  # {"code": ..., "expires_at": float}
_pair_failures = 0
_pair_blocked_until = 0.0
_PAIR_MAX_FAILURES = 5
_PAIR_BLOCK_SECONDS = 60.0
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);
"""


def init(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    with closing(_connect()) as conn, conn:
        conn.executescript(_SCHEMA)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH or "jarvis-security.db"), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ── Eşleştirme akışı ─────────────────────────────────────────────────────────

def start_pairing() -> dict[str, Any]:
    """Yeni 6 haneli kod üretir (eskisi geçersiz olur)."""
    global _pair_failures, _pair_blocked_until
    code = f"{secrets.randbelow(1_000_000):06d}"
    with _PAIR_LOCK:
        _pending_code.clear()
        _pending_code["code"] = code
        _pending_code["expires_at"] = time.time() + _CODE_TTL_SECONDS
        _pair_failures = 0
        _pair_blocked_until = 0.0
    return {"code": code, "expires_in": _CODE_TTL_SECONDS}


def pending_code_info() -> dict[str, Any]:
    if not _pending_code or _pending_code.get("expires_at", 0) < time.time():
        return {"active": False}
    return {
        "active": True,
        "code": _pending_code["code"],
        "expires_in": int(_pending_code["expires_at"] - time.time()),
    }


def claim(code: str, device_name: str) -> Optional[dict[str, Any]]:
    """Geçerli kodu cihaz token'ıyla takas eder; kod tek kullanımlıktır."""
    global _pair_failures, _pair_blocked_until
    with _PAIR_LOCK:
        now = time.time()
        if now < _pair_blocked_until:
            return None
        expected = str(_pending_code.get("code", ""))
        if not _pending_code or _pending_code.get("expires_at", 0) < now:
            return None
        if not secrets.compare_digest(str(code).strip(), expected):
            _pair_failures += 1
            if _pair_failures >= _PAIR_MAX_FAILURES:
                _pair_blocked_until = now + _PAIR_BLOCK_SECONDS
                _pair_failures = 0
            return None
        _pending_code.clear()
        _pair_failures = 0

        token = secrets.token_urlsafe(32)
        device = {
            "id": secrets.token_hex(4),
            "name": (device_name or "cihaz").strip()[:40] or "cihaz",
            "token_hash": _hash(token),
            "created_at": _now_iso(),
        }
    with _DB_LOCK, closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO devices (id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
            (device["id"], device["name"], device["token_hash"], device["created_at"]),
        )
    return {"device_id": device["id"], "name": device["name"], "device_token": token}


# ── Doğrulama / yönetim ──────────────────────────────────────────────────────

def verify_token(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    digest = _hash(token)
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM devices WHERE token_hash = ?", (digest,)
        ).fetchone()
    if row is None:
        return None
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE devices SET last_seen_at = ? WHERE id = ?", (_now_iso(), row["id"])
        )
    return {"device_id": row["id"], "name": row["name"]}


def list_devices() -> list[dict[str, Any]]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, last_seen_at FROM devices ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def revoke(device_id: str) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    return cur.rowcount > 0


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def required() -> bool:
    """Cihaz doğrulaması şart mı? Loopback dışındaki tüm bind adresleri korunur."""
    bind = config.env("JARVIS_BIND", "127.0.0.1").strip().lower()
    return config.env("JARVIS_PAIRING_REQUIRED") == "1" or bind not in {
        "127.0.0.1",
        "::1",
        "localhost",
    }


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def require_user(request: Any) -> dict:
    """Korumalı uçlar için bağımlılık: geçerli access token sahibi olmalı.

    Loopback (yerel masaüstü) istisnası: PC'nin kendi arayüzü giriş yapmadan
    çalışmaya devam eder (owner='local'). Uzak istemciler 401 alır.
    """
    from fastapi import HTTPException

    user = getattr(getattr(request, "state", None), "user", None)
    if user:
        return user
    if is_loopback(_client_host(request)):
        return {"id": "local", "first_name": "Local", "last_name": ""}
    raise HTTPException(status_code=401, detail="Giriş yapmanız gerekiyor.")


_USER_TOKEN_DIGEST = "user_access_v1"  # sabit etiket (yalnızca kimlik ayrımı için)


def is_user_token_valid(token: str) -> bool:
    """Access token'ı doğrular; geçerliyse True."""
    if not token:
        return False
    # Döngüsel importu önlemek için geç import.
    from . import auth

    try:
        auth.decode_token(token, expected_type="access")
    except auth.AuthError:
        return False
    return True


def _client_owner(value: Any) -> Optional[str]:
    client_id = str(value or "").strip()
    if not _CLIENT_ID_RE.fullmatch(client_id):
        return None
    return f"client:{client_id}"


def _user_owner(request: Any) -> Optional[str]:
    """JWT ile doğrulanmış kullanıcı → 'user:<id>' (en yüksek öncelik)."""
    user = getattr(getattr(request, "state", None), "user", None)
    user_id = str((user or {}).get("id") or "").strip() if user else ""
    return f"user:{user_id}" if user_id else None


def request_owner(request: Any) -> str:
    """Return the stable data partition for an authenticated request.

    Priority (Prompt 1): user:<id> > device:<id> > client:<id> > local.
    Paired devices are isolated by device id. Local desktop traffic uses one
    explicit local partition because it has no remote device identity.
    Unauthenticated remote requests are guests ("guest:*", madde 6): their
    settings and chat are never persisted.
    """
    user_owner = _user_owner(request)
    if user_owner:
        return user_owner
    device = getattr(getattr(request, "state", None), "device", None)
    device_id = str((device or {}).get("device_id") or "").strip()
    if device_id:
        return f"device:{device_id}"
    headers = getattr(request, "headers", {})
    client_owner = _client_owner(headers.get("x-client-id"))
    if client_owner:
        return client_owner
    query_params = getattr(request, "query_params", {})
    qp_owner = _client_owner(query_params.get("client_id"))
    if qp_owner:
        return qp_owner
    # Kimliksiz uzak istek = misafir; 'local' partisyonuna ASLA yazmamalı.
    if not is_loopback(_client_host(request)):
        return "guest:anon"
    return "local"


def _client_host(request: Any) -> str:
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "") or "") if client else ""


def is_guest(request: Any) -> bool:
    """Kimliği doğrulanamayan uzak istek = misafir (Bölüm A/B kuralı).

    Misafir: loopback dışından gelir, giriş yapmamış, eşleşmiş cihazı ve
    geçerli bir client_id'si yoktur. Sohbeti ve ayarları KAYIT EDİLMEZ.
    """
    if is_loopback(_client_host(request)):
        return False
    if _user_owner(request):
        return False
    if getattr(getattr(request, "state", None), "device", None):
        return False
    headers = getattr(request, "headers", {})
    return _client_owner(headers.get("x-client-id")) is None


def websocket_owner(websocket: Any) -> tuple[str, str]:
    """Return the validated session partition and its client id."""
    client_id = str(websocket.query_params.get("client_id") or "").strip()
    if not _CLIENT_ID_RE.fullmatch(client_id):
        client_id = secrets.token_urlsafe(24)
    device_info = getattr(getattr(websocket, "state", None), "device", None)
    device_id = str((device_info or {}).get("device_id") or "").strip()
    owner = f"device:{device_id}" if device_id else f"client:{client_id}"
    return owner, client_id


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def lan_ip() -> Optional[str]:
    """Varsayılan rotanın yerel IP'si (paket göndermez, sadece yönlendirir)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None
