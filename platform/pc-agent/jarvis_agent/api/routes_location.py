"""Konum uçları (Özellik 19) — IP tabanlı tespit + reverse geocode.

- ipapi.co (günde 1000 ücretsiz istek) → aşılırsa/ağ yoksa ip-api.com fallback.
- Gizlilik: konum yalnızca hava durumu için kullanılır; üçüncü taraflara
  (OWM hariç) gönderilmez.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from .. import security
from ..store import database

logger = logging.getLogger("jarvis.api.location")

router = APIRouter()

_TIMEOUT = 8.0


def _detect_by_ip() -> dict[str, Any]:
    """Sunucu IP'sinden şehir tespiti (ipapi.co → ip-api.com fallback)."""
    try:
        resp = httpx.get("https://ipapi.co/json/", timeout=_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("city"):
                return {
                    "city": str(data.get("city") or ""),
                    "country": str(data.get("country_name") or ""),
                    "lat": data.get("latitude"),
                    "lon": data.get("longitude"),
                    "timezone": str(data.get("timezone") or ""),
                    "source": "ipapi.co",
                }
    except httpx.HTTPError as exc:
        logger.warning("ipapi.co erişilemedi (%s); ip-api.com deneniyor", exc)
    except ValueError:
        pass
    try:
        resp = httpx.get(
            "http://ip-api.com/json/", params={"lang": "tr"}, timeout=_TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success" and data.get("city"):
                return {
                    "city": str(data.get("city") or ""),
                    "country": str(data.get("country") or ""),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "timezone": str(data.get("timezone") or ""),
                    "source": "ip-api.com",
                }
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("ip-api.com da başarısız: %s", exc)
    return {"city": "", "country": "", "lat": None, "lon": None,
            "timezone": "", "source": "none"}


@router.get("/api/location/detect")
def location_detect(request: Request) -> dict:
    result = _detect_by_ip()
    if not result.get("city"):
        return {**result, "ok": False, "detail": "Konum tespit edilemedi."}
    return {**result, "ok": True}


class ReverseBody(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


@router.post("/api/location/reverse-geocode")
def reverse_geocode(payload: ReverseBody) -> dict:
    """{lat, lon} → {city, country, timezone} (Open-Meteo geocoding; anahtarsız)."""
    try:
        resp = httpx.get(
            "https://api.bigdatacloud.net/data/reverse-geocode-client",
            params={"latitude": payload.lat, "longitude": payload.lon,
                    "localityLanguage": "tr"},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "ok": True,
                "city": str(data.get("city") or data.get("locality") or ""),
                "country": str(data.get("countryName") or ""),
                "timezone": "",
                "lat": payload.lat,
                "lon": payload.lon,
            }
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("reverse-geocode başarısız: %s", exc)
    return {"ok": False, "city": "", "country": "", "timezone": ""}


class SetCityBody(BaseModel):
    city: str = Field(min_length=1, max_length=80)


@router.put("/api/location/set")
def location_set(payload: SetCityBody, request: Request) -> dict:
    """Şehri ayara kaydeder (user_settings.city — mevcut ayar akışıyla aynı)."""
    owner = security.request_owner(request)
    if database.is_guest(owner):
        raise HTTPException(status_code=403, detail="Misafir konum ayarlayamaz.")
    city = payload.city.strip()
    if not city:
        raise HTTPException(status_code=422, detail="Şehir boş olamaz.")
    database.update_user_settings(owner, {"city": city})
    database.audit("location.set", actor=owner, detail=city[:60])
    return {"ok": True, "city": city}
