"""Sistem uçları: sağlık kontrolü, canlı istatistik, hava durumu, audit."""
from __future__ import annotations

import socket
import time

from fastapi import APIRouter, Request

from .. import config
from ..core import counters
from ..core import weather as weather_module
from ..relay_client import wake_via_node
from ..store import database
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
