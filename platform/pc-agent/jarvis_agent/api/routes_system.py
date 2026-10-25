"""Sistem uçları: sağlık kontrolü, canlı istatistik, hava durumu, audit."""
from __future__ import annotations

import socket
import time

from fastapi import APIRouter, HTTPException, Request

from .. import config, security
from ..core import counters
from ..core import weather as weather_module
from ..relay_client import wake_via_node
from ..store import database
from .guards import require_permission
from .routes_integrations import build_integrations_payload

router = APIRouter()


def build_stats_payload(app) -> dict:
    """İstatistik anlık görüntüsü + kullanıcı sayaçları (REST ve WS ortak).

    ``app`` doğrudan FastAPI uygulamasıdır (Request/WebSocket'ten ``.app``
    ile alınır); böylece iki protokol aynı kodu paylaşır.
    """
    snap = dict(app.state.stats.snapshot())
    snap["command_count"] = counters.get_command_count()
    snap["session_count"] = counters.get_session_count()
    # Mikrofon dinleme durumu her istatistik itmesinde taşınır (gereklim 5.4).
    voice = getattr(app.state, "voice", None)
    if voice is not None:
        snap["voice"] = voice.status()
    return snap


@router.get("/api/health")
def health(request: Request) -> dict:
    """Ölçüm uç noktası — arayüz bağlantı durumunu buradan anlar.

    Bilinçli olarak hafiftir: ağ çağrısı yapmaz, yalnızca bellekteki
    duruma bakar. Offline algılamanın hızlı ve garantili olması için.
    """
    provider = getattr(request.app.state, "llm", None)
    started = getattr(request.app.state, "started_at", None)
    body = {
        "status": "ok",
        "version": config.APP_VERSION,
        "agent_uptime_seconds": round(time.time() - started, 1) if started else 0.0,
        "llm_provider": provider.name if provider else "none",
        "llm_ready": bool(provider is not None and provider.name != "mock"),
        "session_count": counters.get_session_count(),
    }
    # Relay durumu (Faz 2): yapılandırılmışsa bağlantı bilgisi taşınır.
    relay = getattr(request.app.state, "relay", None)
    if relay is not None:
        body["relay"] = relay.status()
    else:
        body["relay"] = {"configured": False, "connected": False, "relay": None}
    body["integrations"] = build_integrations_payload(request)
    return body


@router.get("/api/system/wol")
def wol_status(request: Request) -> dict:
    """WoL kurulum durumu (node URL + MAC doldurulmuş mu)."""
    cfg = getattr(request.app.state, "wol_cfg", {}) or {}
    return {
        "configured": bool(cfg.get("url") and cfg.get("mac")),
        "node_url": cfg.get("url") or None,
        "mac": cfg.get("mac") or None,
    }


@router.post("/api/system/wol/wake")
def wol_wake(request: Request) -> dict:
    """WoL node'a (LAN içi) magic packet komutu yollar — test amaçlı."""
    result = wake_via_node(getattr(request.app.state, "wol_cfg", {}) or {})
    database.audit("wol.wake", detail=result.get("mac") or "")
    return result


@router.get("/api/pair/lan")
def pair_lan(request: Request) -> dict:
    """Yerel ağ eşleştirme (Faz 2): telefonun bağlanacağı URL'ler + QR.

    QR, segno (bağımlılıksız) ile SVG olarak üretilir; kütüphane yoksa
    yalnızca URL listesi döner (QR arayüzde metin olarak gösterilir).
    """
    bind = config.env("JARVIS_BIND", "127.0.0.1")
    port = str(config.env("JARVIS_PORT", "8000"))
    candidates: list[str] = []
    if bind in ("0.0.0.0", ""):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                candidates.append(f"http://{s.getsockname()[0]}:{port}")
        except OSError:
            pass
        for name in ("WLAN", "Ethernet", "Ethernet 2"):
            try:
                import psutil

                addrs = psutil.net_if_addrs().get(name) or []
                for a in addrs:
                    if str(getattr(a, "family", "")) == "AddressFamily.AF_INET":
                        ip = a.address
                        if ip and not ip.startswith("169.254"):
                            url = f"http://{ip}:{port}"
                            if url not in candidates:
                                candidates.append(url)
            except Exception:
                pass
    else:
        candidates.append(f"http://{bind}:{port}")
    primary = candidates[0] if candidates else f"http://127.0.0.1:{port}"
    qr_svg = ""
    try:
        import segno

        qr_svg = segno.make(primary, error="m").svg_data_uri(scale=6, border=2)
    except Exception:
        qr_svg = ""
    return {"primary": primary, "urls": candidates, "qr_svg": qr_svg}


@router.get("/api/system/stats")
def system_stats(request: Request) -> dict:
    return build_stats_payload(request.app)


@router.get("/api/weather")
def get_weather(
    request: Request, refresh: bool = False, lat: float | None = None, lon: float | None = None
) -> dict:
    # Bölüm A: şehir ve dil sahibine özel user_settings'ten okunur.
    owner = getattr(request.state, "owner", "local")
    row = database.get_user_settings(owner)
    lang = str(row.get("language") or "") or config.DEFAULT_LANGUAGE
    if lat is not None and lon is not None:
        # Tarayıcı konumu (Prompt 0 item 6): koordinattan şehir bulunur.
        return weather_module.get_by_coords(lat, lon, force=refresh, lang=lang)
    city = (str(row.get("city") or "") or config.DEFAULT_CITY or "").strip()
    return weather_module.get(city, force=refresh, lang=lang)


@router.get("/api/audit")
def get_audit(limit: int = 100) -> dict:
    """Son audit kayıtları (Faz 1: yerel; Faz 2: cihaz bazlı)."""
    return {"entries": database.get_audit(limit=limit)}


# ── Bölüm C — madde 12: cihaz algılama (User-Agent) ─────────────────────────

_OS_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Windows NT 10.0", "Windows 10/11"),
    ("Windows NT 6.3", "Windows 8.1"),
    ("Windows NT 6.2", "Windows 8"),
    ("Windows NT 6.1", "Windows 7"),
    ("Windows", "Windows"),
    ("iPhone OS", "iOS"),
    ("iPad; CPU OS", "iPadOS"),
    ("CPU OS", "iPadOS"),
    ("Android", "Android"),
    ("Mac OS X", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
)

# Sıra önemlidir: en özel tarayıcı önce test edilir.
_BROWSER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)


def parse_user_agent(ua: str) -> dict:
    """User-Agent'tan cihaz türü, işletim sistemi ve tarayıcı çıkarır."""
    ua = (ua or "").strip()
    lowered = ua.lower()
    if "ipad" in lowered or "tablet" in lowered or ("android" in lowered and "mobile" not in lowered):
        device_type = "tablet"
    elif "mobile" in lowered or "iphone" in lowered or "android" in lowered:
        device_type = "mobile"
    else:
        device_type = "desktop"

    os_name, os_version = "Bilinmiyor", ""
    for needle, label in _OS_PATTERNS:
        if needle.lower() in lowered:
            os_name = label
            if "android" in lowered:
                idx = lowered.find("android")
                os_version = ua[idx + len("android"):].strip("; ) ").split(";")[0].strip()
            elif "iphone os" in lowered or "cpu os" in lowered:
                idx = lowered.find("cpu os")
                os_version = ua[idx + len("cpu os"):].strip("_; ) ").split(" ")[0].replace("_", ".")
            elif "mac os x" in lowered:
                idx = lowered.find("mac os x")
                os_version = ua[idx + len("mac os x"):].strip("; ) ").split(")")[0].replace("_", ".")
            elif "windows nt" in lowered:
                idx = lowered.find("windows nt")
                os_version = ua[idx + len("windows nt"):].strip("; ) ").split(";")[0].strip()
            break

    browser, browser_version = "Bilinmiyor", ""
    for needle, label in _BROWSER_PATTERNS:
        idx = lowered.find(needle.lower())
        if idx != -1:
            browser = label
            raw = ua[idx + len(needle):]
            browser_version = raw.split(" ")[0].split(";")[0].strip()
            break

    return {
        "device_type": device_type,
        "os": os_name,
        "os_version": os_version,
        "browser": browser,
        "browser_version": browser_version,
    }


@router.get("/api/system/device")
def device_detect(request: Request) -> dict:
    """İsteği yapan istemcinin cihaz bilgisi (madde 12: cihaz algılama paneli)."""
    info = parse_user_agent(request.headers.get("user-agent", ""))
    info["authenticated"] = guards_mode(request)
    return info


def guards_mode(request: Request) -> bool:
    """Kullanıcının kimlikli istemci olup olmadığı (misafir ≠ kimlikli)."""
    from . import guards

    return guards.mode_of(request) != "guest"


@router.post("/api/system/shutdown")
def shutdown_pc(request: Request) -> dict:
    """PC'yi kapatır — DAIMA 2FA elevation ister, varsayılan olarak kapalıdır.

    JARVIS_ALLOW_SHUTDOWN=1 yoksa 503 döner (yanlışlıkla tetiklenemez).
    """
    from .routes_critical import elevation_of, require_elevation

    require_permission(request, "shutdown")  # madde 25: izin kapalıysa 403
    require_elevation(request)  # shutdown DAIMA 2FA elevation ister (loopback dahil)
    user = getattr(request.state, "user", None) or {}
    if not user.get("id"):
        user = security.require_user(request)  # yerel (PC) istek → sahip hesabı
    user_id = str(user.get("id") or "")
    token = elevation_of(request)
    from .. import twofa

    if not twofa.verify_elevation(token, user_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "2fa_elevation_required", "reason": "PC'yi kapatmak için 2FA onayı gerekli"},
        )
    if not config.ALLOW_SHUTDOWN:
        raise HTTPException(
            status_code=503,
            detail="PC kapatma devre dışı (.env: JARVIS_ALLOW_SHUTDOWN=1 ile açılır).",
        )
    database.audit("system.shutdown", actor=f"user:{user_id}")
    import subprocess

    try:
        subprocess.Popen(["shutdown", "/s", "/t", "10"])
    except OSError as exc:  # shutdown komutu yok (macOS/Linux)
        raise HTTPException(status_code=500, detail=f"Kapatma komutu çalıştırılamadı: {exc}") from exc
    return {"ok": True, "detail": "PC 10 saniye içinde kapatılacak."}

