/**
 * useClientStats — Özellik 2: siteyi AÇAN cihazın istatistikleri (3 sn'de bir).
 *
 * Toplanan veriler:
 * - navigator.userAgent → cihaz türü (telefon/tablet/laptop/masaüstü)
 * - navigator.deviceMemory (Chrome; desteklenmiyorsa null → arayüz "Veri yok")
 * - navigator.hardwareConcurrency → CPU çekirdek sayısı
 * - window.performance.memory (Chrome) → JS heap kullanımı
 * - navigator.getBattery() → şarj yüzdesi + durum
 * - navigator.connection → bağlantı türü + tahmini hız
 * - window.screen + devicePixelRatio
 *
 * Desteklenmeyen API'ler ASLA hata fırlatmaz (graceful degradation).
 */
import { useEffect, useState } from "react";
import type { ClientStats } from "../types";

interface NavigatorExtras {
  deviceMemory?: number;
  connection?: { effectiveType?: string; downlink?: number; type?: string };
  getBattery?: () => Promise<{
    level: number;
    charging: boolean;
    addEventListener?: (type: string, cb: () => void) => void;
  }>;
}

interface PerformanceMemory {
  usedJSHeapSize: number;
  jsHeapSizeLimit: number;
}

function detectDeviceType(ua: string): ClientStats["device_type"] {
  if (/iPad|Tablet|PlayBook|Silk|Kindle|(Android(?!.*Mobile))/i.test(ua)) {
    return "tablet";
  }
  if (/Mobi|iPhone|iPod|Android.*Mobile|Windows Phone/i.test(ua)) {
    return "phone";
  }
  // Masaüstünde dar pencere olasılığı ayrıştırılamaz; laptop/desktop'a UA
  // güvenilmez — Touch + Mac → laptop, aksi halde masaüstü varsayılır.
  if (/Macintosh/i.test(ua) && "ontouchend" in document) return "laptop";
  return "desktop";
}

function collect(): ClientStats {
  const nav = navigator as Navigator & NavigatorExtras;
  const perf = performance as Performance & { memory?: PerformanceMemory };
  let deviceType: ClientStats["device_type"] = "desktop";
  try {
    deviceType = detectDeviceType(navigator.userAgent);
  } catch {
    /* UA okunamadı → desktop */
  }
  const conn = nav.connection || {};
  return {
    device_type: deviceType,
    platform: nav.platform || "—",
    device_memory_gb: typeof nav.deviceMemory === "number" ? nav.deviceMemory : null,
    cpu_cores:
      typeof navigator.hardwareConcurrency === "number"
        ? navigator.hardwareConcurrency
        : null,
    js_heap_used_mb: perf.memory
      ? Math.round(perf.memory.usedJSHeapSize / 1048576)
      : null,
    js_heap_limit_mb: perf.memory
      ? Math.round(perf.memory.jsHeapSizeLimit / 1048576)
      : null,
    battery_percent: null,
    battery_charging: null,
    connection_type: conn.effectiveType || conn.type || "—",
    downlink_mbps: typeof conn.downlink === "number" ? conn.downlink : null,
    screen_width: window.screen?.width ?? 0,
    screen_height: window.screen?.height ?? 0,
    pixel_ratio: window.devicePixelRatio ?? 1,
    online: navigator.onLine,
    updated_at: Date.now(),
  };
}

export function useClientStats(intervalMs = 3000): ClientStats | null {
  const [stats, setStats] = useState<ClientStats | null>(null);

  useEffect(() => {
    let alive = true;

    // Batarya bir kez okunur + olay dinleyicileri bağlanır (3 sn'de değişmez).
    const nav = navigator as Navigator & NavigatorExtras;
    const applyBattery = (level: number, charging: boolean) => {
      if (!alive) return;
      setStats((prev) =>
        prev
          ? { ...prev, battery_percent: Math.round(level * 100), battery_charging: charging }
          : prev
      );
    };
    if (typeof nav.getBattery === "function") {
      nav
        .getBattery()
        .then((battery) => {
          applyBattery(battery.level, battery.charging);
          battery.addEventListener?.("levelchange", () =>
            applyBattery(battery.level, battery.charging)
          );
          battery.addEventListener?.("chargingchange", () =>
            applyBattery(battery.level, battery.charging)
          );
        })
        .catch(() => undefined); // Firefox/Safari: getBattery yok → null kalır
    }

    const tick = () => {
      try {
        setStats(collect());
      } catch {
        /* toplama arızası uygulamayı çökertmez */
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [intervalMs]);

  return stats;
}

/** Cihaz türüne göre ikon (Özellik 2.4). */
export function deviceIcon(type: ClientStats["device_type"] | undefined): string {
  switch (type) {
    case "phone":
      return "📱";
    case "tablet":
      return "📟";
    case "laptop":
      return "💻";
    default:
      return "🖥️";
  }
}
