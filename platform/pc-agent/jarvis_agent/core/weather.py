"""Güncel hava durumu — OpenWeatherMap istemcisi (kısa önbellekli)."""
from __future__ import annotations

import datetime
import logging
import threading
import time
from typing import Any, Optional

import httpx

from .. import config

logger = logging.getLogger("jarvis.weather")

_CACHE_TTL = 600.0  # 10 dk — ücretsiz katman dostu
_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "fetched_at": _now_iso()}


def get(city: Optional[str] = None, force: bool = False, lang: str = "tr") -> dict[str, Any]:
    """Şehir için güncel hava durumu; her hata zarif biçimde `available=False` döner.

    ``lang`` OWM açıklama dilidir (madde 3: yalnızca tr/en desteklenir).
    """
    city = (city or config.DEFAULT_CITY).strip()
    if not city:
        # Prompt 0 item 6: izin reddi / kayıt yoksa varsayılan şehir İstanbul.
        city = "Istanbul,TR"
    lang = lang if lang in config.ALLOWED_LANGUAGES else "tr"
    api_key = config.OWM_API_KEY
    if not api_key:
        return _unavailable("no_api_key")
    if not city:
        return _unavailable("no_city")

    cache_key = f"{city.lower()}:{lang}"
    if not force:
        with _lock:
            hit = _cache.get(cache_key)
            if hit and time.time() - hit[0] < _CACHE_TTL:
                return hit[1]

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "units": "metric", "lang": lang, "appid": api_key},
            )
    except httpx.HTTPError as exc:
        logger.warning("Hava durumu isteği başarısız (%s): %s", city, exc)
        return _unavailable("network_error")

    if resp.status_code == 404:
        return _unavailable("invalid_city")
    if resp.status_code in (401, 403):
        return _unavailable("invalid_api_key")
    if resp.status_code != 200:
        logger.warning("Hava durumu HTTP %s", resp.status_code)
        return _unavailable("http_error")

    try:
        data = resp.json()
        payload = {
            "available": True,
            "city": data.get("name", city),
            "temperature": round(float(data["main"]["temp"]), 1),
            "feels_like": round(float(data["main"]["feels_like"]), 1),
            "humidity": int(data["main"]["humidity"]),
            "wind_speed": round(float(data["wind"]["speed"]), 1),
            "description": (data.get("weather") or [{}])[0].get("description", ""),
            "icon": (data.get("weather") or [{}])[0].get("icon", ""),
            "fetched_at": _now_iso(),
        }
    except (KeyError, ValueError, TypeError):
        logger.exception("Hava durumu yanıtı ayrıştırılamadı")
        return _unavailable("parse_error")

    with _lock:
        _cache[city.lower()] = (time.time(), payload)
    return payload


def get_by_coords(
    lat: float, lon: float, force: bool = False, lang: str = "tr"
) -> dict[str, Any]:
    """Tarayıcı konumundan (enlem/boylam) hava durumu (Prompt 0 item 6).

    Aynı OWM ucu kullanılır; dönen ``city`` alanı koordinatın karşılık geldiği
    şehir adıdır. Geçersiz koordinatta ``invalid_location`` döner.
    """
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return _unavailable("invalid_location")
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return _unavailable("invalid_location")
    api_key = config.OWM_API_KEY
    if not api_key:
        return _unavailable("no_api_key")
    lang = lang if lang in config.ALLOWED_LANGUAGES else "tr"
    cache_key = f"geo:{round(lat_f, 2)},{round(lon_f, 2)}:{lang}"
    if not force:
        with _lock:
            hit = _cache.get(cache_key)
            if hit and time.time() - hit[0] < _CACHE_TTL:
                return hit[1]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": lat_f,
                    "lon": lon_f,
                    "units": "metric",
                    "lang": lang,
                    "appid": api_key,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("Konum hava durumu isteği başarısız: %s", exc)
        return _unavailable("network_error")
    if resp.status_code in (401, 403):
        return _unavailable("invalid_api_key")
    if resp.status_code != 200:
        return _unavailable("http_error")
    try:
        data = resp.json()
        payload = {
            "available": True,
            "city": data.get("name") or "",
            "temperature": round(float(data["main"]["temp"]), 1),
            "feels_like": round(float(data["main"]["feels_like"]), 1),
            "humidity": int(data["main"]["humidity"]),
            "wind_speed": round(float(data["wind"]["speed"]), 1),
            "description": (data.get("weather") or [{}])[0].get("description", ""),
            "icon": (data.get("weather") or [{}])[0].get("icon", ""),
            "lat": lat_f,
            "lon": lon_f,
            "fetched_at": _now_iso(),
        }
    except (KeyError, ValueError, TypeError):
        logger.exception("Konum hava durumu yanıtı ayrıştırılamadı")
        return _unavailable("parse_error")
    with _lock:
        _cache[cache_key] = (time.time(), payload)
    return payload
