"""Kimlik doğrulama çekirdeği (Bölüm B — madde 5 ve 16).

- JWT (HS256): access 15 dk, refresh 7 gün, reset 10 dk (config'ten).
- Şifreler ve güvenlik cevapları bcrypt ile hash'lenir (12 round).
- Hatalı giriş kilidi: LOGIN_MAX_FAILURES hatalı denemeden sonra
  LOGIN_BLOCK_SECONDS boyunca o hesap için login 429 döner.
Sırlar koda gömülmez: JARVIS_JWT_SECRET .env'den okunur (config.py).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any, Optional

import bcrypt
import jwt

from . import config
from .store import database

_NAME_RE = re.compile(r"^[\wçğıöşüÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ\s.-]{1,39}$", re.UNICODE)
_BIRTH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_lock_lock = threading.Lock()


class AuthError(Exception):
    """Kullanıcıya dönülebilir kimlik hatası (HTTP status + opsiyonel başlıklar)."""

    def __init__(
        self, message: str, status_code: int = 400, headers: Optional[dict] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers or {}


class AuthUnavailable(AuthError):
    """JARVIS_JWT_SECRET tanımlı değil — güvensiz varsayılanla çalışılmaz."""

    def __init__(self) -> None:
        super().__init__("Kimlik doğrulama yapılandırılmamış (JARVIS_JWT_SECRET).", 503)


# ── Şifre hash (bcrypt, madde 16: 12 round) ──────────────────────────────────

def hash_secret(plain: str) -> str:
    rounds = int(config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode()


def verify_secret(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────

def normalize_answer(value: str) -> str:
    """Güvenlik cevabı karşılaştırması için normalize eder (strip + casefold)."""
    return " ".join((value or "").strip().casefold().split())


def auth_available() -> bool:
    """JARVIS_JWT_SECRET tanımlı mı? (Auth uçlarının çalışması için şart.)"""
    return bool((config.AUTH_SECRET or "").strip())


def _secret() -> str:
    if not auth_available():
        raise AuthUnavailable()
    return config.AUTH_SECRET.strip()


def make_token(user_id: str, token_type: str, ttl_seconds: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user_id,
        "typ": token_type,
        "iat": now,
        "exp": now + dt.timedelta(seconds=ttl_seconds),
        # Tekil token kimliği (refresh rotation iptali için).
        "jti": f"{token_type}.{time.time_ns()}",
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def issue_token_pair(user_id: str) -> dict[str, Any]:
    """Access + refresh token çifti üretir (madde 16: 15 dk / 7 gün)."""
    return {
        "access_token": make_token(user_id, "access", config.ACCESS_TOKEN_TTL_SECONDS),
        "refresh_token": make_token(user_id, "refresh", config.REFRESH_TOKEN_TTL_SECONDS),
        "token_type": "bearer",
        "expires_in": config.ACCESS_TOKEN_TTL_SECONDS,
    }


def decode_token(token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Token'ı doğrular; geçersizse AuthError fırlatır."""
    if not token:
        raise AuthError("Token boş.", 401)
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Oturum süresi doldu.", 401) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Geçersiz token.", 401) from exc
    if expected_type and payload.get("typ") != expected_type:
        raise AuthError("Token türü uyuşmuyor.", 401)
    return payload


def bearer_of(request: Any) -> Optional[str]:
    """Authorization: Bearer <token> başlığından token'ı ayıklar."""
    header = ""
    try:
        header = str(request.headers.get("authorization") or "")
    except AttributeError:
        return None
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        return token or None
    return None


# ── Refresh token iptali (rotation) ──────────────────────────────────────────

def revoke_token(payload: dict[str, Any]) -> None:
    """Refresh rotation: kullanılmış refresh token'ın jti'sini iptal eder."""
    jti = str(payload.get("jti") or "")
    exp = float(payload.get("exp") or (time.time() + config.REFRESH_TOKEN_TTL_SECONDS))
    if not jti:
        return
    try:
        with database._write_lock, closing(database.connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)",
                (jti, exp),
            )
            conn.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (time.time(),))
    except sqlite3.Error:
        # İptal kaydı yazılamazsa akış bozulmaz.
        pass


def is_revoked(payload: dict[str, Any]) -> bool:
    jti = str(payload.get("jti") or "")
    if not jti:
        return False
    try:
        with closing(database.connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)
            ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None


# ── Doğrulamalar ─────────────────────────────────────────────────────────────

def validate_name(value: str, label: str) -> str:
    cleaned = (value or "").strip()
    if not _NAME_RE.fullmatch(cleaned):
        raise AuthError(f"{label} 2-40 karakter olmalı ve geçersiz karakter içermemeli.", 422)
    return cleaned


def validate_birth_date(value: str) -> str:
    cleaned = (value or "").strip()
    if not _BIRTH_RE.fullmatch(cleaned):
        raise AuthError("Doğum tarihi YYYY-MM-DD biçiminde olmalı.", 422)
    try:
        dt.date.fromisoformat(cleaned)
    except ValueError as exc:
        raise AuthError("Doğum tarihi geçersiz.", 422) from exc
    return cleaned


def validate_password(value: str) -> str:
    if len(value or "") < 8:
        raise AuthError("Şifre en az 8 karakter olmalı.", 422)
    if len(value) > 128:
        raise AuthError("Şifre en fazla 128 karakter olabilir.", 422)
    return value


def validate_security_question(value: str) -> str:
    cleaned = (value or "").strip()
    if len(cleaned) < 4 or len(cleaned) > 200:
        raise AuthError("Güvenlik sorusu 4-200 karakter olmalı.", 422)
    return cleaned


def validate_security_answer(value: str) -> str:
    cleaned = (value or "").strip()
    if len(cleaned) < 2 or len(cleaned) > 120:
        raise AuthError("Güvenlik cevabı 2-120 karakter olmalı.", 422)
    return cleaned


# ── Hatalı giriş kilidi (madde 16: 5 hata → 15 dk blok) ──────────────────────

def _lock_key(first_name: str, last_name: str, ip: str = "") -> str:
    name = f"{first_name.strip().lower()}|{last_name.strip().lower()}"
    return f"{name}|{ip.strip() or '-'}"


def check_not_locked(first_name: str, last_name: str, ip: str = "") -> None:
    key = _lock_key(first_name, last_name, ip)
    with closing(database.connect()) as conn:
        row = conn.execute(
            "SELECT blocked_until FROM login_attempts WHERE lock_key = ?", (key,)
        ).fetchone()
    if row:
        remaining = float(row["blocked_until"] or 0) - time.time()
        if remaining > 0:
            seconds = max(1, int(remaining))
            raise AuthError(
                f"Çok fazla hatalı giriş. {seconds} sn sonra tekrar deneyin.",
                429,
                {"Retry-After": str(seconds)},
            )


def register_failure(first_name: str, last_name: str, ip: str = "") -> None:
    key = _lock_key(first_name, last_name, ip)
    now = time.time()
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with _lock_lock, closing(database.connect()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO login_attempts (lock_key, fails, blocked_until, updated_at) "
            "VALUES (?, 0, 0, ?)",
            (key, stamp),
        )
        row = conn.execute(
            "SELECT fails, blocked_until FROM login_attempts WHERE lock_key = ?", (key,)
        ).fetchone()
        fails = int(row["fails"] or 0)
        blocked_until = float(row["blocked_until"] or 0)
        if blocked_until and blocked_until <= now:
            # Süre doldu → sayaç sıfırdan başlar.
            fails, blocked_until = 0, 0.0
        fails += 1
        if fails >= config.LOGIN_MAX_FAILURES:
            blocked_until = now + config.LOGIN_BLOCK_SECONDS
            fails = 0
        conn.execute(
            "UPDATE login_attempts SET fails = ?, blocked_until = ?, updated_at = ? "
            "WHERE lock_key = ?",
            (fails, blocked_until, stamp, key),
        )


def register_success(first_name: str, last_name: str, ip: str = "") -> None:
    key = _lock_key(first_name, last_name, ip)
    with _lock_lock, closing(database.connect()) as conn, conn:
        conn.execute("DELETE FROM login_attempts WHERE lock_key = ?", (key,))


def reset_login_locks() -> None:
    """Yalnızca testler/kurtarma için: tüm kilitleri temizler."""
    with _lock_lock, closing(database.connect()) as conn, conn:
        conn.execute("DELETE FROM login_attempts")


# ── Hesap akışları (db katmanı üzerine ince sarmalayıcı) ────────────────────

def user_public(user: dict[str, Any]) -> dict[str, Any]:
    """İstemciye dönen güvenli kullanıcı alanları (hash asla sızmaz)."""
    return {
        "user_id": user.get("id"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "birth_date": user.get("birth_date"),
    }


def create_account(
    first_name: str,
    last_name: str,
    birth_date: str,
    password: str,
    security_question: str,
    security_answer: str,
) -> dict[str, Any]:
    first = validate_name(first_name, "Ad")
    last = validate_name(last_name, "Soyad")
    birth = validate_birth_date(birth_date)
    password = validate_password(password)
    question = validate_security_question(security_question)
    answer = validate_security_answer(security_answer)
    try:
        return database.create_user(
            first,
            last,
            birth,
            hash_secret(password),
            question,
            hash_secret(normalize_answer(answer)),
        )
    except ValueError as exc:
        raise AuthError(str(exc), 409) from exc


def authenticate(
    first_name: str, last_name: str, password: str, ip: str = ""
) -> dict[str, Any]:
    """Kimliği doğrular. Kullanıcı varlığı sızdırılmaz (tek tip 401 mesajı)."""
    check_not_locked(first_name, last_name, ip)
    user = database.get_user_by_name(first_name, last_name)
    if user is None or not verify_secret(password, str(user.get("password_hash") or "")):
        register_failure(first_name, last_name, ip)
        raise AuthError("Ad, soyad veya şifre hatalı.", 401)
    register_success(first_name, last_name, ip)
    return user


def reset_password(
    first_name: str,
    last_name: str,
    birth_date: str,
    security_answer: str,
    new_password: str,
    ip: str = "",
) -> str:
    """Güvenlik cevabıyla şifre sıfırlar; kullanıcı varlığını sızdırmaz.

    Başarısız denemeler de giriş kilidi sayacına eklenir.
    """
    new_password = validate_password(new_password)
    generic = AuthError("Bilgiler doğrulanamadı.", 400)
    check_not_locked(first_name, last_name, ip)
    user = database.get_user_by_name(first_name, last_name)
    answer_ok = user is not None and verify_secret(
        normalize_answer(security_answer), str(user.get("security_answer_hash") or "")
    )
    birth_ok = user is not None and str(user.get("birth_date") or "") == (
        birth_date or ""
    ).strip()
    if not (answer_ok and birth_ok):
        register_failure(first_name, last_name, ip)
        raise generic
    database.update_user_password(str(user["id"]), hash_secret(new_password))
    register_success(first_name, last_name, ip)
    return str(user["id"])
