"""Kimlik doğrulama uçları (Bölüm B — madde 5/16).

Akış:
- POST /api/auth/register  → hesap + access/refresh token
- POST /api/auth/login     → token çifti (5 hata → 15 dk kilit, 429 + Retry-After)
- POST /api/auth/refresh   → yeni access token (refresh rotation: eski iptal edilir)
- POST /api/auth/reset-password → güvenlik sorusu cevabıyla yeni şifre
- GET  /api/auth/me        → access token sahibinin bilgisi
- POST /api/auth/logout    → refresh token iptali

JARVIS_JWT_SECRET tanımlı değilse tüm uçlar 503 döner (güvensiz varsayılan yok).
Bilerek yapılmayan: eski cihaz/istemci verisinin kullanıcıya taşınması
(owner geçişi) bu görevin dışındadır — raporda öneri olarak duruyor.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import auth, security
from ..store import database

router = APIRouter()


class RegisterBody(BaseModel):
    # Özellik 5A: kullanıcı adı akışı — username doluysa güvenlik sorusu zorunlu değil.
    username: Optional[str] = Field(default=None, max_length=32)
    first_name: str = Field(min_length=2, max_length=40)
    last_name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    password_repeat: Optional[str] = Field(default=None, max_length=128)
    birth_date: Optional[str] = Field(default=None, max_length=10)
    security_question: Optional[str] = Field(default=None, max_length=200)
    security_answer: Optional[str] = Field(default=None, max_length=120)


class LoginBody(BaseModel):
    # Özellik 5A: username doluysa kullanıcı adı akışı; yoksa ad/soyad akışı.
    username: Optional[str] = Field(default=None, max_length=32)
    first_name: Optional[str] = Field(default=None, max_length=40)
    last_name: Optional[str] = Field(default=None, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=8)


class ResetBody(BaseModel):
    first_name: str = Field(min_length=1, max_length=40)
    last_name: str = Field(min_length=1, max_length=40)
    birth_date: str = Field(min_length=10, max_length=10)
    security_answer: str = Field(min_length=1, max_length=120)
    new_password: str = Field(min_length=8, max_length=128)


class LogoutBody(BaseModel):
    refresh_token: str = Field(min_length=8)


def _client_ip(request: Request) -> str:
    host = request.client.host if request.client else ""
    return host or "unknown"


def _error(exc: auth.AuthError) -> JSONResponse:
    return JSONResponse(
        {"detail": str(exc)}, status_code=exc.status_code, headers=exc.headers
    )


def _available() -> None:
    if not auth.auth_available():
        raise HTTPException(
            status_code=503,
            detail="Kimlik doğrulama yapılandırılmamış (JARVIS_JWT_SECRET).",
        )


def _tokens_for(user: dict) -> dict:
    """Token çifti + güvenli kullanıcı alanları (user_id anahtarıyla)."""
    return {**auth.issue_token_pair(str(user["id"])), **auth.user_public(user)}


@router.post("/api/auth/register")
def register(payload: RegisterBody) -> JSONResponse:
    _available()
    # ── Özellik 5A: kullanıcı adı akışı ──
    if payload.username:
        if payload.password_repeat is not None and payload.password != payload.password_repeat:
            return JSONResponse({"detail": "Şifreler eşleşmiyor.", "field": "password_repeat"}, 422)
        try:
            user = auth.register_with_username(
                payload.username, payload.first_name, payload.last_name, payload.password
            )
        except auth.AuthError as exc:
            return _error(exc)
        database.audit("auth.register", actor=f"user:{user['id']}", detail=user["id"])
        return JSONResponse(_tokens_for(user), status_code=201)
    # ── Klasik ad/soyad + güvenlik sorusu akışı (geriye dönük uyumlu) ──
    if not payload.birth_date or not payload.security_question or not payload.security_answer:
        return JSONResponse(
            {"detail": "Klasik kayıt için doğum tarihi ve güvenlik sorusu gerekli."}, 422
        )
    try:
        user = auth.create_account(
            payload.first_name,
            payload.last_name,
            payload.birth_date,
            payload.password,
            payload.security_question,
            payload.security_answer,
        )
    except auth.AuthError as exc:
        return _error(exc)
    database.audit("auth.register", actor=f"user:{user['id']}", detail=user["id"])
    return JSONResponse(_tokens_for(user), status_code=201)


@router.post("/api/auth/login")
def login(payload: LoginBody, request: Request) -> JSONResponse:
    _available()
    # ── Özellik 5A: kullanıcı adı akışı ──
    if payload.username:
        try:
            user = auth.authenticate_username(
                payload.username, payload.password, _client_ip(request)
            )
        except auth.AuthError as exc:
            database.audit(
                "auth.login_failed",
                actor=f"username:{payload.username.strip().lower()}",
            )
            return _error(exc)
        database.audit("auth.login", actor=f"user:{user['id']}", detail=user["id"])
        return JSONResponse(_tokens_for(user))
    # ── Klasik ad/soyad akışı ──
    if not payload.first_name or not payload.last_name:
        return JSONResponse({"detail": "Kullanıcı adı veya ad/soyad gerekli."}, 422)
    try:
        user = auth.authenticate(
            payload.first_name, payload.last_name, payload.password, _client_ip(request)
        )
    except auth.AuthError as exc:
        database.audit(
            "auth.login_failed",
            actor=f"name:{payload.first_name.strip()} {payload.last_name.strip()}",
        )
        return _error(exc)
    database.audit("auth.login", actor=f"user:{user['id']}", detail=user["id"])
    return JSONResponse(_tokens_for(user))


@router.post("/api/auth/refresh")
def refresh(payload: RefreshBody) -> JSONResponse:
    _available()
    try:
        claims = auth.decode_token(payload.refresh_token, expected_type="refresh")
    except auth.AuthError as exc:
        return _error(exc)
    if auth.is_revoked(claims):
        return JSONResponse({"detail": "Oturum geçersiz. Tekrar giriş yapın."}, status_code=401)
    user = database.get_user_by_id(str(claims.get("sub") or ""))
    if user is None:
        return JSONResponse({"detail": "Oturum geçersiz."}, status_code=401)
    # Rotation: kullanılan refresh token bir daha kullanılamaz.
    auth.revoke_token(claims)
    return JSONResponse(_tokens_for(user))


@router.post("/api/auth/logout")
def logout(payload: LogoutBody) -> dict:
    _available()
    try:
        claims = auth.decode_token(payload.refresh_token, expected_type="refresh")
    except auth.AuthError as exc:
        return _error(exc)  # type: ignore[return-value]
    auth.revoke_token(claims)
    return {"ok": True}


@router.post("/api/auth/reset-password")
def reset_password(payload: ResetBody, request: Request) -> dict:
    _available()
    try:
        user_id = auth.reset_password(
            payload.first_name,
            payload.last_name,
            payload.birth_date,
            payload.security_answer,
            payload.new_password,
            _client_ip(request),
        )
    except auth.AuthError as exc:
        return _error(exc)  # type: ignore[return-value]
    database.audit("auth.password_reset", actor=f"user:{user_id}", detail=user_id)
    return {"ok": True}


@router.get("/api/auth/me")
def me(request: Request) -> dict:
    _available()
    user = getattr(request.state, "user", None)
    # Bearer başlığı gönderildiyse kimlik ZORUNLU: geçersiz/süresi dolmuş
    # token loopback istisnasına düşmemeli (aksi halde kopuk istemci yanlışlıkla
    # yerel kullanıcı sayılırdı).
    token = auth.bearer_of(request)
    if not user:
        if token:
            raise HTTPException(status_code=401, detail="Oturum süresi doldu veya token geçersiz.")
        if security.is_loopback(security._client_host(request)):
            local = security.require_user(request)
            return {**local, "user_id": local["id"], "local": True}
        raise HTTPException(status_code=401, detail="Giriş gerekli.")
    return auth.user_public(user)
