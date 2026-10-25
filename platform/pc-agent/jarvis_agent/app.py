"""FastAPI uygulama fabrikası — tüm uçların bağlandığı yer.

Statik Web UI (platform/web/dist) mevcutsa aynen sunulur; yoksa yalnızca
API çalışır (arayüz geliştirilirken `npm run dev` + Vite proxy kullanılır).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from . import auth
from . import observability  # madde 31: Sentry (opsiyonel; SENTRY_DSN ile aktif)
from .relay_client import RelayClient, wake_via_node
from .api import (
    routes_auth,
    routes_camera,
    routes_chat,
    routes_conversation,
    routes_pair,
    routes_session,
    routes_settings,
    routes_system,
    routes_voice,
    routes_integrations,
    routes_smart_home,
)
from . import security
from .api import routes_critical
from .api import routes_files
from .api import routes_reminders
from .api import routes_agent
from .api import routes_social
from .api import routes_productivity
from .api import routes_privacy
from .api import ws as ws_module
from .camera.service import CameraService
from .core import counters
from .core.stats import StatsMonitor
from .llm import build_provider
from .llm import int57_bridge
from .reminders.service import SERVICE as REMINDER_SERVICE
from .store import database
from .voice.service import VoiceService

logger = logging.getLogger("jarvis.app")

# Madde 31: Sentry DSN .env'de tanımlıysa erken başlat; hassas alan filtresi
# (observability.scrub_event) tüm olaylara uygulanır. DSN yoksa no-op'tur.
observability.init_sentry()


def _relay_command_handler(message: dict) -> Optional[dict]:
    """Relay'den gelen komutu yerel ReminderService'e uygular (worker thread)."""
    from .reminders import service as reminder_module

    kind = message.get("type")
    try:
        if kind == "reminder.create":
            due = reminder_module.parse_iso(str(message.get("target_at") or ""))
            if due is None:
                return {"type": "reminder.error", "error": "target_at geçersiz"}
            row = REMINDER_SERVICE.create(str(message.get("title") or "").strip()[:200], due)
            return {"type": "reminder.created", "reminder": row}
        if kind == "reminder.cancel":
            ok = REMINDER_SERVICE.delete(int(message.get("id") or 0))
            return {"type": "reminder.deleted", "id": message.get("id"), "ok": ok}
        if kind == "reminder.ack":
            row = REMINDER_SERVICE.ack(int(message.get("id") or 0), by="relay")
            return {"type": "reminder.acked", "id": message.get("id"), "ok": row is not None}
        if kind == "wake_pc":
            from .relay_client import wake_via_node

            cfg = {
                "url": config.env("JARVIS_WOL_NODE_URL", ""),
                "secret": config.env("JARVIS_WOL_NODE_SECRET", ""),
                "mac": config.env("JARVIS_TARGET_MAC", ""),
            }
            database.audit("wol.wake_requested", detail=cfg.get("mac") or "")
            return wake_via_node(cfg)
    except (TypeError, ValueError) as exc:
        return {"type": "reminder.error", "error": str(exc)}
    return None


def _make_announcer(voice: VoiceService, relay_client: Optional[Any]) -> Any:
    """Hatırlatıcı olaylarını TTS + audit + relay'e yayan kapama döndürür.

    Announcer, tick worker thread'inden çağrılır; ``voice.speak`` çağıran
    thread'i TTS bitene kadar bloklar — bu yüzden async döngüde değil,
    to_thread worker'ında çalışması güvenlidir.
    """

    def announce(message: dict) -> None:
        event = str(message.get("event") or "")
        payload = message.get("payload") or {}
        reminder = payload.get("reminder") or {}
        title = str(reminder.get("title") or "").strip()
        if event == "fired" and title:
            database.audit("reminder.fired", detail=title)
            try:
                voice.speak(f"Hatırlatma: {title}")
            except Exception:
                logger.exception("hatırlatıcı TTS başarısız")
        if relay_client is not None and event in ("fired", "acked", "expired"):
            relay_client.publish({"type": f"reminder.{event}", "reminder": reminder})

    return announce


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    database.init_db()
    int57_bridge.set_audit_callback(
        lambda event, detail: database.audit(f"integration.{event}", detail=detail)
    )

    app = FastAPI(
        title="JARVIS PC Agent",
        version=config.APP_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    configured_origins = [
        origin.strip().rstrip("/")
        for origin in config.env("JARVIS_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    allowed_origins = configured_origins or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Device-Token",
            "X-Client-ID",
            "Authorization",
            "Accept-Language",
        ],
        allow_credentials=False,
    )

    # ── Kimlik doğrulama (Prompt 1): JWT taşıyan isteklerde request.state.user.
    #    JARVIS_JWT_SECRET boşsa tokenlar yok sayılır; uçlar 503 döner.
    auth_ready = auth.auth_available()
    if not auth_ready:
        logger.warning(
            "JARVIS_JWT_SECRET tanımlı değil — /api/auth/* uçları 503 döner. "
            "Kalıcı oturum için .env'e güçlü bir değer ekleyin."
        )

    @app.middleware("http")
    async def _attach_user(request: Request, call_next):
        if auth_ready:
            token = auth.bearer_of(request)
            if token:
                try:
                    claims = auth.decode_token(token, expected_type="access")
                    user = database.get_user_by_id(str(claims.get("sub") or ""))
                    if user:
                        request.state.user = user
                except auth.AuthError:
                    # Geçersiz/süresi dolmuş token → kimliksiz istek olarak devam.
                    pass
        return await call_next(request)

    # Bölüm A (madde 7): her isteğe kararlı veri sahipliği (owner) etiketi.
    # Sohbet/ayarlar bu etikete göre kullanıcı bazında izole edilir.
    @app.middleware("http")
    async def _attach_owner(request: Request, call_next):
        request.state.owner = security.request_owner(request)
        return await call_next(request)

    # Prompt 2: misafir kapısı (allow-list). Misafir (kimliksiz uzak istemci)
    # yalnızca sohbet/sağlık/auth/eşleştirme/oturum uçlarını kullanabilir.
    from .api import guards as guest_guard

    @app.middleware("http")
    async def _guest_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api") and not path.startswith(
            guest_guard.GUEST_ALLOWED_PREFIXES
        ):
            if security.is_guest(request):
                return JSONResponse(
                    {"detail": guest_guard.GUEST_DENIED_MESSAGE}, status_code=403
                )
        return await call_next(request)

    # ── Cihaz güvenliği (Faz 2): loopback dışı istekler eşleşmiş cihazdan
    #    geçerli X-Device-Token ile gelmek zorunda (pairing şartsa).
    security.init(config.DB_PATH)
    if security.required():

        @app.middleware("http")
        async def _device_guard(request: Request, call_next):
            path = request.url.path
            public = path == "/api/health" or path.startswith("/api/pair/")
            host = request.client.host if request.client else ""
            if not public and not security.is_loopback(host):
                device = security.verify_token(request.headers.get("x-device-token", ""))
                if device is None:
                    return JSONResponse(
                        {"detail": "Eşleşmemiş cihaz — QR ile eşleştirin."},
                        status_code=401,
                    )
                request.state.device = device
            return await call_next(request)

    # ── Uygulama durumu (bağımlılık enjeksiyonu yerine basit state) ──
    app.state.started_at = time.time()
    app.state.stats = StatsMonitor()
    app.state.camera = CameraService()
    app.state.llm = build_provider()
    app.state.voice = VoiceService(app.state.llm, app.state.stats)

    # Relay (Faz 2): JARVIS_RELAY_URL tanımlıysa outbound kanal açılır.
    wol_cfg = {
        "url": config.env("JARVIS_WOL_NODE_URL", ""),
        "secret": config.env("JARVIS_WOL_NODE_SECRET", ""),
        "mac": config.env("JARVIS_TARGET_MAC", ""),
    }
    app.state.wol_cfg = wol_cfg
    relay_url = config.env("JARVIS_RELAY_URL", "")
    relay_client = RelayClient(
        relay_url,
        config.env("JARVIS_RELAY_TOKEN", ""),
        _relay_command_handler,
    ) if relay_url else None
    app.state.relay = relay_client
    # Hatırlatıcı olayları → TTS + WS + relay (announcer bağlantısı).
    REMINDER_SERVICE.announcer = _make_announcer(app.state.voice, relay_client)
    app.state.reminders = REMINDER_SERVICE
    app.state.google_home_oauth_states = {}

    @app.middleware("http")
    async def _settings_ownership(request: Request, call_next: Any) -> Any:
        """Kullanıcıya özel ayarların sahibini istekten çözüp state'e koyar.

        Madde 7: ayarlar cihaz/istemci bazında izole tutulur (DB'de).
        """
        request.state.settings_owner = security.request_owner(request)
        return await call_next(request)

    app.include_router(routes_system.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_conversation.router)
    app.include_router(routes_camera.router)
    app.include_router(routes_voice.router)
    app.include_router(routes_reminders.router)
    app.include_router(routes_files.router)
    app.include_router(routes_pair.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_session.router)
    app.include_router(routes_critical.router)
    app.include_router(routes_agent.router)
    app.include_router(routes_integrations.router)
    app.include_router(routes_smart_home.router)
    app.include_router(routes_social.router)
    app.include_router(routes_productivity.router)
    app.include_router(routes_privacy.router)  # madde 25 + 27
    app.include_router(ws_module.router)

    @app.on_event("startup")
    async def _startup() -> None:
        import asyncio

        app.state.stats.start()
        # Ses servisi TTS/sohbet için ana event loop'a bağlanır (Faz 3).
        app.state.voice.bind_loop(asyncio.get_running_loop())
        if app.state.relay is not None:
            app.state.relay.start()
            logger.info("Relay kanalı açılıyor: %s", config.env("JARVIS_RELAY_URL", ""))
        sessions = counters.bump_session_count()
        database.audit("agent.start", detail=f"oturum #{sessions}")
        provider = app.state.llm
        logger.info(
            "JARVIS Agent v%s başladı — LLM: %s (%s)",
            config.APP_VERSION,
            provider.name,
            provider.model,
        )
        # Mikrofon varsayılan olarak KAPALI başlar (gizlilik: kullanıcı eylemi
        # şart). Otomatik wake dinleme istenirse .env: JARVIS_VOICE_AUTOSTART=1
        if config.env("JARVIS_VOICE_AUTOSTART") == "1":
            app.state.voice.start()
            logger.info("Ses servisi otomatik başlatıldı (JARVIS_VOICE_AUTOSTART=1)")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.relay is not None:
            await app.state.relay.stop()
        app.state.voice.stop()
        app.state.camera.close()
        app.state.stats.stop()
        database.audit("agent.stop")
        logger.info("JARVIS Agent durduruldu")

    # ── Statik Web UI (varsa) ──
    dist = config.WEB_DIST_DIR
    if (dist / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(str(dist / "index.html"))

        @app.get("/{path:path}", include_in_schema=False)
        async def serve_spa(path: str):
            # API öneki altındaki bilinmeyen yollar SPA'ya düşmemeli:
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            # Path traversal koruması: yalnızca dist içindeki dosyalar sunulur.
            candidate = (dist / path).resolve()
            if not candidate.is_relative_to(dist.resolve()):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            if candidate.is_file():
                return FileResponse(str(candidate))
            # SPA fallback: dosya yoksa index.html (Faz 2'de QR vb. rotalar için)
            return FileResponse(str(dist / "index.html"))
    else:
        @app.get("/", include_in_schema=False)
        async def api_only_notice() -> JSONResponse:
            return JSONResponse(
                {
                    "name": "JARVIS PC Agent",
                    "version": config.APP_VERSION,
                    "note": (
                        "Web UI derlenmemiş. platform/web altında `npm install && "
                        "npm run build` çalıştırın veya geliştirme için "
                        "`npm run dev` kullanın."
                    ),
                    "docs": "/api/docs",
                }
            )

    return app
