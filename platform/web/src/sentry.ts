// Madde 31: Sentry baslatma + hassas veri filtresi (DSN yoksa devre disi).
import * as Sentry from "@sentry/react";

const SENSITIVE = /(password|passwd|token|secret|authorization|cookie|jwt|api_?key|refresh)/i;

/** Recursif olarak hassas anahtarlari sansurler (testlerde de kullanilir). */
export function scrubValue<T>(value: T): T {
  if (Array.isArray(value)) return value.map((v) => scrubValue(v)) as unknown as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = SENSITIVE.test(k) ? "[redacted]" : scrubValue(v);
    }
    return out as unknown as T;
  }
  return value;
}

export function initSentry(): void {
  const dsn = (import.meta.env.VITE_SENTRY_DSN as string | undefined)?.trim();
  if (!dsn) return; // DSN tanimli degilse Sentry kapali kalir
  try {
    Sentry.init({
      dsn,
      environment: import.meta.env.MODE || "development",
      tracesSampleRate: 0.1,
      beforeSend: (event) => scrubValue(event),
      beforeBreadcrumb: (breadcrumb) => scrubValue(breadcrumb),
    });
  } catch (err) {
    console.warn("Sentry init basarisiz", err);
  }
}
