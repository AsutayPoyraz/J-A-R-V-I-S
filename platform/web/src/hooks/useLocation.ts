/**
 * useLocation — Özellik 19: otomatik konum tespiti + hava durumu şehri.
 *
 * Akış: navigator.geolocation (izinliyse) → reverse-geocode → şehir ayarla.
 * İzin reddi / desteklenmiyor → IP tabanlı /api/location/detect fallback.
 * Gizlilik: konum yalnızca hava durumu için kullanılır.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { isGuestMode } from "../components/LoginGate";

const SET_CITY_DISABLED_KEY = "jarvis.location.disabled";

export function useLocation(onCitySet?: (city: string) => void) {
  const [detected, setDetected] = useState<string | null>(null);
  const [permission, setPermission] = useState<"unknown" | "granted" | "denied" | "unavailable">(
    "unknown"
  );
  const triedRef = useRef(false);
  const onCitySetRef = useRef(onCitySet);
  onCitySetRef.current = onCitySet;

  const saveCity = useCallback(async (city: string) => {
    if (!city) return;
    setDetected(city);
    try {
      await api.setLocation(city);
      onCitySetRef.current?.(city);
    } catch {
      /* misafir/ offline — sessizce geç */
    }
  }, []);

  const detectByIp = useCallback(async () => {
    try {
      const resp = await api.locationDetect();
      if (resp.ok && resp.city) {
        setPermission("granted");
        await saveCity(resp.city);
      }
    } catch {
      /* offline */
    }
  }, [saveCity]);

  const detect = useCallback(async () => {
    if (triedRef.current || isGuestMode()) return;
    triedRef.current = true;
    try {
      if (localStorage.getItem(SET_CITY_DISABLED_KEY) === "1") return;
    } catch {
      /* localStorage yoksa devam */
    }
    // 1) Tarayıcı geolocation (en hassas):
    if ("geolocation" in navigator) {
      try {
        const position = await new Promise<GeolocationPosition>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            timeout: 8000,
            maximumAge: 600_000,
          });
        });
        setPermission("granted");
        // 2) Koordinat → şehir (reverse-geocode):
        const geo = await api.reverseGeocode(
          position.coords.latitude,
          position.coords.longitude
        );
        if (geo.ok && geo.city) {
          await saveCity(geo.city);
          return;
        }
        await detectByIp();
        return;
      } catch {
        // 3) İzin reddedildi → IP tabanlı fallback:
        setPermission("denied");
      }
    } else {
      setPermission("unavailable");
    }
    await detectByIp();
  }, [detectByIp, saveCity]);

  useEffect(() => {
    void detect();
  }, [detect]);

  const disableAuto = useCallback(() => {
    try {
      localStorage.setItem(SET_CITY_DISABLED_KEY, "1");
    } catch {
      /* yok sayılır */
    }
  }, []);

  return { detected, permission, detect, disableAuto };
}
