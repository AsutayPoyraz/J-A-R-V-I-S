/** Faz 2 — cihaz eşleştirme kapısı ve PC paneli.
 *
 * Uzak cihaz (telefon) eşleşmemişse tüm arayüz kapanır; PC'deki 6 haneli
 * kod istenir. Sayfa ?pair=KOD ile açılırsa (QR taraması) kod otomatik
 * equilir. PC'de (loopback) kapı devre dışıdır; QR + cihaz listesi görünür.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, deviceToken } from "../api/client";
import type { DeviceSummary } from "../types";

const LOOPBACK = ["localhost", "127.0.0.1", "[::1]", "::1"];

function guessName(): string {
  const ua = navigator.userAgent;
  if (/Android/i.test(ua)) return "Android telefon";
  if (/iPhone|iPad/i.test(ua)) return "iPhone/iPad";
  if (/Mac/i.test(ua)) return "Mac tarayıcı";
  return "Tarayıcı";
}

export default function PairingGate({
  onPaired,
  onGuest,
}: {
  onPaired: () => void;
  /** Prompt 2: eşleşmeden yalnızca sohbetle devam (kalıcılık yok). */
  onGuest?: () => void;
}) {
  const isPC = LOOPBACK.includes(location.hostname);
  const [code, setCode] = useState(new URLSearchParams(location.search).get("pair") ?? "");
  const [name, setName] = useState(guessName());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devices, setDevices] = useState<DeviceSummary[]>([]);
  const [qrKey, setQrKey] = useState(0);
  const claimedRef = useRef(false);

  const finish = useCallback(
    (token: string) => {
      deviceToken.set(token);
      const params = new URLSearchParams(location.search);
      params.delete("pair");
      const qs = params.toString();
      history.replaceState(null, "", location.pathname + (qs ? `?${qs}` : ""));
      onPaired();
    },
    [onPaired]
  );

  const claim = useCallback(
    async (raw: string) => {
      const c = raw.trim();
      if (c.length < 4) {
        setError("Kod en az 4 haneli olmalı.");
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const r = await api.pairClaim(c, name || guessName());
        finish(r.device_token);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Eşleştirme başarısız oldu.");
        setBusy(false);
      }
    },
    [finish, name]
  );

  // QR ile gelindiyse otomatik eşleş
  useEffect(() => {
    const auto = new URLSearchParams(location.search).get("pair") ?? "";
    if (auto && !claimedRef.current) {
      claimedRef.current = true;
      void claim(auto);
    }
  }, [claim]);

  // PC paneli: cihaz listesini periyodik çek
  useEffect(() => {
    if (!isPC) return;
    let alive = true;
    const load = async () => {
      try {
        const s = await api.pairStatus();
        if (alive) setDevices(s.devices ?? []);
      } catch {
        /* önemsiz */
      }
    };
    void load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [isPC]);

  const revoke = async (id: string) => {
    try {
      await api.revokeDevice(id);
      setDevices((d) => d.filter((x) => x.id !== id));
    } catch {
      /* önemsiz */
    }
  };

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div
        className="w-full max-w-md rounded-2xl border p-6 text-center shadow-2xl"
        style={{ borderColor: "var(--border-strong)", background: "rgb(8 10 18 / 0.85)" }}
      >
        <h1 className="text-xl font-semibold tracking-widest text-slate-100">JARVIS</h1>

        {isPC ? (
          <>
            <p className="mt-1 text-sm text-slate-400">
              Telefon kameranızla QR'ı okutun — eşleşme otomatik tamamlanır.
            </p>
            <div className="mx-auto mt-4 w-fit rounded-xl bg-white/95 p-3" key={qrKey}>
              <img
                src="/api/pair/qr.svg"
                alt="Eşleştirme QR kodu"
                className="h-56 w-56"
                onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
              />
            </div>
            <button
              className="mt-3 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
              onClick={() => {
                void api.pairStart().catch(() => undefined);
                setQrKey((k) => k + 1);
              }}
            >
              Yeni kod üret
            </button>

            <div className="mt-5 space-y-1.5 text-left">
              <p className="text-xs uppercase tracking-wider text-slate-500">
                Eşleşmiş cihazlar ({devices.length})
              </p>
              {devices.length === 0 && (
                <p className="text-sm text-slate-500">Henüz cihaz eşleşmedi.</p>
              )}
              {devices.map((d) => (
                <div
                  key={d.id}
                  className="flex items-center justify-between rounded-lg border border-white/5 px-3 py-2 text-sm"
                >
                  <span className="text-slate-200">{d.name}</span>
                  <button
                    className="text-xs text-rose-400 hover:text-rose-300"
                    onClick={() => void revoke(d.id)}
                  >
                    kaldır
                  </button>
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            <p className="mt-2 text-sm text-slate-400">
              Bu cihaz henüz eşleşmedi. PC ekranındaki JARVIS penceresinde
              görünen kodu girin.
            </p>
            <form
              className="mt-5 space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void claim(code);
              }}
            >
              <input
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-center font-mono text-2xl tracking-[0.5em] text-slate-100 outline-none focus:border-cyan-400/50"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                maxLength={8}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
              <input
                className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-400/50"
                placeholder="Cihaz adı (örn. Annemin telefonu)"
                maxLength={40}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded-lg bg-cyan-500/90 py-2.5 font-medium text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
              >
                {busy ? "Eşleştiriliyor..." : "Eşleştir"}
              </button>
            </form>
            <button
              type="button"
              onClick={onGuest}
              className="mt-3 w-full rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
            >
              Misafir olarak devam et
            </button>
          </>
        )}

        {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
      </div>
    </div>
  );
}