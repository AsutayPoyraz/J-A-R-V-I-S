# -*- coding: utf-8 -*-
"""G web yamasi 4: Sentry (madde 31) + vite-env + main.tsx baglantisi."""
import pathlib
R = pathlib.Path(r"F:\Software\JARVİS")
WEB = R / "platform" / "web"
SRC = WEB / "src"
def log(*a): print("[s4]", *a, flush=True)

SENTRY_TS = '''// Madde 31: Sentry baslatma + hassas veri filtresi (DSN yoksa devre disi).
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
'''
p = SRC / "sentry.ts"
if not p.exists():
    p.write_text(SENTRY_TS, encoding="utf-8")
    log("sentry.ts yazildi")
else:
    log("sentry.ts zaten var")

ve = SRC / "vite-env.d.ts"
if not ve.exists():
    ve.write_text('/// <reference types="vite/client" />\n', encoding="utf-8")
    log("vite-env.d.ts olusturuldu")

mp = SRC / "main.tsx"
m = mp.read_text(encoding="utf-8")
if "initSentry" not in m:
    lines = m.split("\n")
    idxs = [i for i, l in enumerate(lines) if l.startswith("import ")]
    if idxs:
        lines.insert(max(idxs) + 1, 'import { initSentry } from "./sentry";')
        done = False
        for j, l in enumerate(lines):
            if "createRoot(" in l:
                indent = l[: len(l) - len(l.lstrip())]
                lines.insert(j, indent + "initSentry();")
                done = True
                break
        mp.write_text("\n".join(lines), encoding="utf-8")
        log("main.tsx: Sentry baglandi (createRoot=%s)" % done)
    else:
        log("main.tsx: import yok, SKIP")
else:
    log("main.tsx: zaten var")
