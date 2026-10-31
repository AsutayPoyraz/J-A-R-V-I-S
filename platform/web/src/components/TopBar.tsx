/** Üst bar: logo + bağlantı rozeti | canlı saat/tarih | hava + ayarlar + (mobil) kartlar. */
import { useEffect, useState } from "react";
import { getLang, t } from "../i18n";

interface TopBarProps {
  online: boolean;
  weather: { available: boolean; city?: string; temperature?: number } | null;
  onOpenSettings: () => void;
  onOpenDrawer: () => void;
}

const DAY_NAMES: Record<string, string[]> = {
  tr: ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"],
  en: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
};
const MONTH_NAMES: Record<string, string[]> = {
  tr: [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
  ],
  en: [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ],
};

export default function TopBar({ online, weather, onOpenSettings, onOpenDrawer }: TopBarProps) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const lang = getLang();
  const time = now.toLocaleTimeString(lang === "en" ? "en-GB" : "tr-TR", { hour12: false });
  const date = `${DAY_NAMES[lang][now.getDay()]} ${now.getDate()} ${MONTH_NAMES[lang][now.getMonth()]} ${now.getFullYear()}`;

  const tempText = weather?.available && weather.temperature !== undefined
    ? `${Math.round(weather.temperature)}°`
    : "--";

  return (
    <header className="relative z-10 flex h-14 shrink-0 items-center justify-between gap-3 border-b px-3 sm:px-4"
      style={{ borderColor: "var(--border)", background: "rgb(0 0 0 / 0.25)" }}>

      {/* Sol: logo + rozet */}
      <div className="flex min-w-0 items-center gap-2.5">
        <button
          type="button"
          className="btn-accent rounded-lg px-2 py-1.5 lg:hidden"
          onClick={onOpenDrawer}
          title={t("topbar.system_cards")}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        </button>
        <span
          className="select-none text-[15px] font-bold tracking-[0.3em]"
          style={{ color: "rgb(var(--accent-soft-rgb))", textShadow: "0 0 12px rgb(var(--accent-rgb) / 0.55)" }}
        >
          J.A.R.V.I.S
        </span>
        <span
          className="hidden select-none rounded-full border border-white/10 px-1.5 py-0.5 text-[9px] font-bold tracking-widest text-slate-300 sm:inline-block"
          title="JARVIS ürün sürümü (v11)"
        >
          v11
        </span>
        <span
          className="hidden items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wider sm:inline-flex"
          style={{
            borderColor: online ? "rgb(34 197 94 / 0.5)" : "rgb(239 68 68 / 0.5)",
            color: online ? "rgb(74 222 128)" : "rgb(248 113 113)",
            background: online ? "rgb(34 197 94 / 0.08)" : "rgb(239 68 68 / 0.08)",
          }}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: online ? "rgb(74 222 128)" : "rgb(248 113 113)" }}
          />
          {online ? t("topbar.online") : t("topbar.offline")}
        </span>
      </div>

      {/* Orta: saat + tarih */}
      <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-center">
        <div className="font-mono text-lg font-semibold tabular-nums leading-none text-slate-100">
          {time}
        </div>
        <div className="mt-0.5 text-[10px] tracking-wide text-slate-400">{date}</div>
      </div>

      {/* Sağ: hava + ayarlar */}
      <div className="flex items-center gap-2">
        <span className="hidden text-xs text-slate-300 md:inline">
          {weather?.available ? weather.city : "--"} · <span className="font-semibold">{tempText}</span>
        </span>
        <span className="font-semibold md:hidden">{tempText}</span>
        <button
          type="button"
          onClick={onOpenSettings}
          title={t("topbar.settings")}
          className="btn-accent rounded-lg p-2"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 15a3 3 0 100-6 3 3 0 000 6z"
              stroke="currentColor" strokeWidth="2"
            />
            <path
              d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33h.01a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51h.01a1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82v.01a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"
              stroke="currentColor" strokeWidth="1.6"
            />
          </svg>
        </button>
      </div>
    </header>
  );
}
