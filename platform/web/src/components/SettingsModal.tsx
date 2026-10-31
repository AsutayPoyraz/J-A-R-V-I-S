/** Ayarlar modalı: tema (madde 4), dil (madde 3), panel konumu (madde 32),
 * şehir ve ses ayarları (Faz 3). Tüm metinler i18n'den gelir.
 * v11: "API Anahtarları" (Özellik 5B) ve "Mikrofon" (Özellik 14) sekmeleri. */
import { useEffect, useState } from "react";
import { t, getLang } from "../i18n";
import { api } from "../api/client";
import { sanitizeSettings } from "../utils/sanitize";
import ApiKeysSettings from "./ApiKeysSettings";
import type {
  AppSettings,
  ChatPanelPosition,
  ConversationMode,
  Language,
  VoiceStatus,
} from "../types";

interface Props {
  open: boolean;
  settings: AppSettings | null;
  online: boolean;
  health: { llm_provider: string; llm_ready: boolean } | null;
  integrations: Record<string, { configured: boolean; connected?: boolean; reachable?: boolean; detail?: string }> | null;
  voice: VoiceStatus | null;
  /** Özellik 5B: API anahtarları sekmesi için oturum sahibi. */
  user?: { user_id: string; username?: string } | null;
  onClose: () => void;
  onSave: (patch: {
    background_color?: AppSettings["background_color"];
    city?: string;
    language?: Language;
    chat_panel_position?: ChatPanelPosition;
    conversation_mode?: ConversationMode;
    custom_palette?: Record<string, string>;
    tts_voice?: string;
    tts_rate?: number;
  }) => Promise<unknown>;
  onSaveVoice: (patch: {
    wake_phrases?: string[];
    exit_phrases?: string[];
    clap_enabled?: boolean;
    clap_sensitivity?: number;
  }) => Promise<unknown>;
  /** Madde 3: dil değişimi (anında uygulanır, DB'ye yazılır). */
  onChangeLanguage: (lang: Language) => Promise<unknown> | void;
}

/** Prompt 0/4: Bordo varsayılan; Light/Dark/Custom + eski renkler korunur. */
const COLORS: { value: AppSettings["background_color"]; css: string; labelKey: string }[] = [
  { value: "maroon", css: "#800000", labelKey: "theme.maroon" },
  { value: "dark", css: "#111318", labelKey: "theme.dark" },
  { value: "light", css: "#f7f3ee", labelKey: "theme.light" },
  { value: "custom", css: "connect", labelKey: "theme.custom" },
  { value: "red", css: "rgb(239 68 68)", labelKey: "theme.red" },
  { value: "green", css: "rgb(34 197 94)", labelKey: "theme.green" },
  { value: "blue", css: "rgb(59 130 246)", labelKey: "theme.blue" },
];

const MODES: { value: ConversationMode; labelKey: string; descKey: string }[] = [
  { value: "adaptive", labelKey: "mode.adaptive", descKey: "mode.adaptive_desc" },
  { value: "formal", labelKey: "mode.formal", descKey: "mode.formal_desc" },
  { value: "casual", labelKey: "mode.casual", descKey: "mode.casual_desc" },
];

/** "#rrggbb" → "r g b" (CSS değişkenleri rgb(r g b / a) biçimini bekler). */
function hexToRgb(hex: string): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return "128 0 0";
  const n = parseInt(m[1], 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
}

const POSITIONS: { value: ChatPanelPosition; labelKey: string }[] = [
  { value: "right", labelKey: "settings.chat_position_right" },
  { value: "center", labelKey: "settings.chat_position_center" },
];

const inputCls = "w-full rounded-lg border bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-500";
const inputStyle = { borderColor: "var(--border)" };

export default function SettingsModal({
  open, settings, online, health, integrations, voice, user = null, onClose, onSave, onSaveVoice, onChangeLanguage,
}: Props) {
  // v11: sekme gezinmesi (genel | apikeys | mikrofon)
  const [tab, setTab] = useState<"genel" | "apikeys" | "mikrofon">("genel");
  const [color, setColor] = useState<AppSettings["background_color"]>("maroon");
  const [city, setCity] = useState("");
  const [chatPosition, setChatPosition] = useState<ChatPanelPosition>("right");
  const [mode, setMode] = useState<ConversationMode>("adaptive");
  const [customAccent, setCustomAccent] = useState("#800000");
  const [customBg, setCustomBg] = useState("#0d0308");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ses ayarları (Faz 3 — gereklim 5.4: ifadeler düzenlenebilir)
  const [wakeText, setWakeText] = useState("");
  const [exitText, setExitText] = useState("");
  const [clapEnabled, setClapEnabled] = useState(true);
  const [clapSens, setClapSens] = useState(6.0);
  // Madde 14: TTS ses ve hız tercihleri
  const [ttsVoice, setTtsVoice] = useState("tr");
  const [ttsRate, setTtsRate] = useState(1.0);

  useEffect(() => {
    if (open && settings) {
      setColor(settings.background_color);
      setCity(settings.city);
      setChatPosition(settings.chat_panel_position);
      setMode(settings.conversation_mode ?? "adaptive");
      setTtsVoice(settings.tts_voice ?? "tr");
      setTtsRate(settings.tts_rate ?? 1.0);
      if (settings.custom_palette?.accent) {
        const [r, g, b] = settings.custom_palette.accent.split(" ").map(Number);
        if ([r, g, b].every((n) => Number.isFinite(n))) setCustomAccent(`#${[r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("")}`);
      }
      if (settings.custom_palette?.bg_page) setCustomBg(settings.custom_palette.bg_page);
      setError(null);
    }
  }, [open, settings]);

  useEffect(() => {
    if (open && voice) {
      setWakeText((voice.wake_phrases ?? []).join("\n"));
      setExitText((voice.exit_phrases ?? []).join(", "));
      setClapEnabled(!!voice.clap_enabled);
      setClapSens(voice.clap_sensitivity ?? 6.0);
    }
  }, [open, voice]);

  if (!open) return null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      // Madde 7/32: tema, şehir ve panel konumu kullanıcıya özel DB'de saklanır.
      // Özellik 13: gönderim öncesi sanitizeSettings ile null/undefined normalizasyonu.
      const payload = sanitizeSettings({
        background_color: color,
        city: city.trim() || undefined,
        chat_panel_position: chatPosition,
        conversation_mode: mode,
        tts_voice: ttsVoice,
        tts_rate: ttsRate,
        custom_palette:
          color === "custom"
            ? { accent: hexToRgb(customAccent), bg_page: customBg }
            : undefined,
      });
      await onSave(payload as Parameters<typeof onSave>[0]);
      const wakes = wakeText.split("\n").map((l) => l.trim()).filter((l) => l.length >= 4).slice(0, 12);
      const exits = exitText.split(",").map((l) => l.trim()).filter((l) => l.length >= 3).slice(0, 12);
      await onSaveVoice({
        wake_phrases: wakes.length > 0 ? wakes : undefined,
        exit_phrases: exits.length > 0 ? exits : undefined,
        clap_enabled: clapEnabled,
        clap_sensitivity: clapSens,
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-black/60 p-4" onClick={onClose}>
      <div
        className="panel my-8 w-full max-w-md p-5"
        style={{ background: "rgb(8 10 18 / 0.95)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-200">{t("settings.title")}</h2>
          <button type="button" onClick={onClose} className="btn-accent rounded-md px-2 py-1 text-xs">✕</button>
        </div>

        {/* v11: sekme gezinmesi */}
        <div className="mb-4 grid grid-cols-3 gap-1 rounded-lg border p-0.5" style={{ borderColor: "var(--border)" }}>
          {(
            [
              ["genel", "⚙️ Genel"],
              ["apikeys", "🔑 API Anahtarları"],
              ["mikrofon", "🎤 Mikrofon"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className="min-h-[44px] rounded-md text-[11px] font-medium transition-colors"
              style={{
                background: tab === key ? "rgb(var(--accent-rgb) / 0.25)" : "transparent",
                color: tab === key ? "rgb(var(--accent-soft-rgb))" : "rgb(148 163 184)",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Özellik 5B: kullanıcı bazlı API anahtarları */}
        {tab === "apikeys" && <ApiKeysSettings user={user} />}

        {/* Özellik 14: mikrofon cihazı seçimi + tarayıcı izin testi */}
        {tab === "mikrofon" && <MicSection />}

        {tab === "genel" && (<>

        {/* Dil (madde 3) — seçim anında uygulanır ve DB'ye yazılır */}
        <div className="mb-5">
          <label className="mb-2 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.language")}
          </label>
          <div className="flex gap-2">
            {(["tr", "en"] as Language[]).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => void onChangeLanguage(l)}
                disabled={l === getLang()}
                className="flex-1 rounded-lg border py-2 text-xs font-semibold disabled:opacity-100"
                style={{
                  borderColor: l === getLang() ? "rgb(var(--accent-soft-rgb))" : "var(--border)",
                  background: l === getLang() ? "rgb(var(--accent-rgb) / 0.2)" : "transparent",
                  color: l === getLang() ? "rgb(var(--accent-soft-rgb))" : "var(--text-dim)",
                }}
              >
                {l === "tr" ? t("settings.language_tr") : t("settings.language_en")}
              </button>
            ))}
          </div>
        </div>

        {/* Sohbet paneli konumu (madde 32) */}
        <div className="mb-5">
          <label className="mb-2 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.chat_position")}
          </label>
          <div className="flex gap-2">
            {POSITIONS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setChatPosition(p.value)}
                className="flex-1 rounded-lg border py-2 text-xs font-semibold disabled:opacity-100"
                style={{
                  borderColor: chatPosition === p.value ? "rgb(var(--accent-soft-rgb))" : "var(--border)",
                  background: chatPosition === p.value ? "rgb(var(--accent-rgb) / 0.2)" : "transparent",
                  color: chatPosition === p.value ? "rgb(var(--accent-soft-rgb))" : "var(--text-dim)",
                }}
              >
                {t(p.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Arka plan rengi */}
        <div className="mb-5">
          <label className="mb-2 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.theme")}
          </label>
          <div className="flex flex-wrap gap-2">
            {COLORS.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setColor(c.value)}
                className="flex min-w-[70px] flex-1 flex-col items-center gap-1.5 rounded-lg border p-2.5 transition-transform hover:scale-[1.03]"
                style={{
                  borderColor: color === c.value ? c.css : "var(--border)",
                  background: color === c.value ? "rgb(255 255 255 / 0.04)" : "transparent",
                  boxShadow: color === c.value && c.value !== "custom" ? `0 0 14px ${c.css}66` : "none",
                }}
              >
                <span
                  className="h-5 w-5 rounded-full"
                  style={{
                    background:
                      c.value === "custom"
                        ? "conic-gradient(from 0deg, #800000, #2b6cb0, #2f855a, #800000)"
                        : c.css,
                    boxShadow: c.value === "custom" ? "none" : `0 0 10px ${c.css}`,
                  }}
                />
                <span className="text-[10px] text-slate-300">{t(c.labelKey)}</span>
              </button>
            ))}
          </div>
          {color === "custom" && (
            <div className="mt-3 flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-[10px] text-slate-400">
                {t("settings.custom_accent")}
                <input
                  type="color"
                  value={customAccent}
                  onChange={(e) => setCustomAccent(e.target.value)}
                  className="h-7 w-9 cursor-pointer rounded border-0 bg-transparent"
                />
              </label>
              <label className="flex items-center gap-1.5 text-[10px] text-slate-400">
                {t("settings.custom_bg")}
                <input
                  type="color"
                  value={customBg}
                  onChange={(e) => setCustomBg(e.target.value)}
                  className="h-7 w-9 cursor-pointer rounded border-0 bg-transparent"
                />
              </label>
            </div>
          )}
        </div>

        {/* Prompt 3: konuşma modu */}
        <div className="mb-5">
          <label className="mb-2 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.mode")}
          </label>
          <div className="space-y-1.5">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={mode === m.value}
                onClick={() => setMode(m.value)}
                className="flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left"
                style={{
                  borderColor: mode === m.value ? "rgb(var(--accent-soft-rgb))" : "var(--border)",
                  background: mode === m.value ? "rgb(var(--accent-rgb) / 0.15)" : "transparent",
                }}
              >
                <span
                  className="mt-0.5 grid h-3.5 w-3.5 shrink-0 place-items-center rounded-full border"
                  style={{ borderColor: "rgb(var(--accent-soft-rgb))" }}
                >
                  {mode === m.value && (
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: "rgb(var(--accent-soft-rgb))" }}
                    />
                  )}
                </span>
                <span>
                  <span className="block text-xs font-medium text-slate-200">{t(m.labelKey)}</span>
                  <span className="block text-[10px] text-slate-500">{t(m.descKey)}</span>
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Şehir */}
        <div className="mb-5">
          <label htmlFor="city" className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.city")}
          </label>
          <input
            id="city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Örn. Tuzla,TR"
            maxLength={64}
            className={inputCls}
            style={inputStyle}
          />
          <p className="mt-1 text-[10px] text-slate-500">OpenWeatherMap biçimi: "Şehir,ÜlkeKodu" (örn. İstanbul,TR)</p>
        </div>

        {/* Ses ayarları (Faz 3) */}
        <div className="mb-5 border-t pt-4" style={{ borderColor: "var(--border)" }}>
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: "rgb(var(--accent-soft-rgb))" }}>
            Ses Ayarları
          </h3>

          {!voice?.mic_available && (
            <p className="mb-3 text-[10px] text-amber-400">
              Mikrofon bu cihazda bulunamadı; ayarlar yine de kaydedilir.
            </p>
          )}

          {/* Madde 14: TTS ses ve hız */}
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.tts_voice")}
          </label>
          <div className="mb-3 flex gap-2">
            {(["tr", "en"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setTtsVoice(v)}
                className="flex-1 rounded-lg border py-2 text-xs font-semibold"
                style={{
                  borderColor: ttsVoice === v ? "rgb(var(--accent-soft-rgb))" : "var(--border)",
                  background: ttsVoice === v ? "rgb(var(--accent-rgb) / 0.2)" : "transparent",
                  color: ttsVoice === v ? "rgb(var(--accent-soft-rgb))" : "var(--text-dim)",
                }}
              >
                {v === "tr" ? t("settings.language_tr") : t("settings.language_en")}
              </button>
            ))}
          </div>

          <label htmlFor="tts-rate" className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.tts_rate")} ({ttsRate.toFixed(2)}x)
          </label>
          <input
            id="tts-rate"
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={ttsRate}
            onChange={(e) => setTtsRate(Number(e.target.value))}
            className="w-full accent-[rgb(var(--accent-rgb))]"
          />
          <p className="mb-3 text-[10px] text-slate-500">{t("settings.tts_rate_hint")}</p>

          {/* Uyandırma ifadeleri — satır satır */}
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.wake_phrases")}
          </label>
          <textarea
            value={wakeText}
            onChange={(e) => setWakeText(e.target.value)}
            placeholder={"hey jarvis\nuyan bakalım baba eve geldi"}
            rows={3}
            maxLength={600}
            className={`${inputCls} resize-none font-mono text-xs`}
            style={inputStyle}
          />
          <p className="mt-1 mb-3 text-[10px] text-slate-500">
            Her ifade en az 4 karakter olmalı; en fazla 12 ifade.
          </p>

          {/* Çıkış ifadeleri */}
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            {t("settings.exit_phrases")}
          </label>
          <input
            value={exitText}
            onChange={(e) => setExitText(e.target.value)}
            placeholder={t("settings.exit_phrases_placeholder")}
            maxLength={300}
            className={inputCls}
            style={inputStyle}
          />
          <p className="mt-1 mb-3 text-[10px] text-slate-500">
            {t("settings.exit_hint")}
          </p>

          {/* Çift alkış */}
          <div className="mb-2 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-200">{t("settings.clap")}</p>
              <p className="text-[10px] text-slate-500">
                {t("settings.clap_desc")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setClapEnabled((v) => !v)}
              role="switch"
              aria-checked={clapEnabled}
              className="relative h-6 w-11 rounded-full transition-colors"
              style={{
                background: clapEnabled ? "rgb(var(--accent-rgb) / 0.6)" : "rgb(255 255 255 / 0.12)",
              }}
            >
              <span
                className="absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all"
                style={{ left: clapEnabled ? "22px" : "2px" }}
              />
            </button>
          </div>

          {/* Alkış hassasiyeti */}
          <div className="mb-1">
            <div className="flex justify-between text-[11px]">
              <span className="text-slate-400">{t("settings.clap_sensitivity")}</span>
              <span className="tabular-nums text-slate-200">{clapSens.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              step={0.5}
              value={clapSens}
              onChange={(e) => setClapSens(parseFloat(e.target.value))}
              className="mt-1 w-full accent-current"
              style={{ accentColor: "rgb(var(--accent-soft-rgb))" }}
            />
            <div className="flex justify-between text-[9px] text-slate-500">
              <span>{t("settings.less_sensitive")}</span>
              <span>{t("settings.more_sensitive")}</span>
            </div>
          </div>
        </div>


        {/* Sistem bilgisi */}
        <div className="mb-5 rounded-lg border p-3 text-[11px] leading-relaxed text-slate-400"
          style={{ borderColor: "var(--border)" }}>
          <div className="flex justify-between">
            <span>Bağlantı</span>
            <span style={{ color: online ? "rgb(74 222 128)" : "rgb(248 113 113)" }}>
              {online ? "Çevrimiçi" : "Çevrimdışı"}
            </span>
          </div>
          <div className="mt-1 flex justify-between">
            <span>LLM Sağlayıcısı</span>
            <span className="text-slate-200">
              {health ? (health.llm_ready ? health.llm_provider : `${health.llm_provider} (demo)`) : "--"}
            </span>
          </div>
          <div className="mt-2 border-t pt-2" style={{ borderColor: "var(--border)" }}>
            {[
              ["integrations.whatsapp", "whatsapp"],
              ["integrations.mail", "smtp"],
              ["integrations.home_assistant", "home_assistant"],
              ["integrations.relay", "relay"],
            ].map(([label, key]) => {
              const item = integrations?.[key];
              const active = !!item?.configured && (item.connected ?? item.reachable ?? true);
              return (
                <div className="mt-1 flex justify-between" key={key}>
                  <span>{t(label)}</span>
                  <span style={{ color: active ? "rgb(74 222 128)" : "rgb(148 163 184)" }}>
                    {active ? t("integrations.ready") : t("integrations.off")}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="mt-1 flex justify-between">
            <span>Mikrofon</span>
            <span className="text-slate-200">
              {voice ? (voice.mic_available ? voice.mic : "yok") : "--"}
            </span>
          </div>
        </div>

        {error && <p className="mb-3 text-xs text-red-400">{error}</p>}

        </>)}

        <button
          type="button"
          onClick={tab === "genel" ? save : onClose}
          disabled={saving || !online}
          className="btn-accent w-full rounded-lg py-2.5 text-sm font-semibold"
        >
          {saving ? "Kaydediliyor..." : tab === "genel" ? "Kaydet" : "Kapat"}
        </button>
      </div>
    </div>
  );
}

/** Özellik 14: mikrofon cihazları + tarayıcı izin akışı (hata türü bazlı mesajlar). */
function MicSection() {
  const [devices, setDevices] = useState<
    { index: number; name: string; max_input_channels: number; is_default_input: boolean }[]
  >([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [sdAvailable, setSdAvailable] = useState(true);
  const [permStatus, setPermStatus] = useState<string>("");
  const [micError, setMicError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const resp = await api.voiceDevices();
        setDevices(resp.devices.filter((d) => d.max_input_channels > 0));
        setSelected(resp.selected);
        setSdAvailable(resp.sd_available);
      } catch {
        /* offline */
      }
    })();
  }, []);

  /** Özellik 14.1: navigator.permissions + getUserMedia hata eşlemesi. */
  const testBrowserPermission = async () => {
    setMicError(null);
    setPermStatus("");
    try {
      if (navigator.permissions?.query) {
        const status = await navigator.permissions.query({
          name: "microphone" as PermissionName,
        });
        if (status.state === "denied") {
          setMicError(
            "Tarayıcı mikrofon iznini reddetti. Adres çubuğundaki kilit simgesine tıklayıp izin verin."
          );
          return;
        }
        setPermStatus(
          status.state === "granted" ? "İzin zaten verilmiş ✓" : "İzin sorulacak…"
        );
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setPermStatus("✅ Tarayıcı mikrofonu erişilebilir");
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      if (name === "NotAllowedError") {
        setMicError(
          "Tarayıcı mikrofon iznini reddetti. Adres çubuğundaki kilit simgesine tıklayıp izin verin."
        );
      } else if (name === "NotFoundError") {
        setMicError("Cihazda mikrofon bulunamadı.");
      } else if (name === "NotReadableError") {
        setMicError("Mikrofon başka bir uygulama tarafından kullanılıyor.");
      } else {
        setMicError(
          e instanceof Error ? e.message : "Bilinmeyen mikrofon hatası"
        );
      }
    }
  };

  return (
    <div className="space-y-2 text-[11px]">
      <p className="text-slate-400">
        Sunucu (PC) ses cihazları — voice modu bunlardan birini kullanır:
      </p>
      {!sdAvailable && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-amber-200">
          sounddevice kurulu değil — ses modu devre dışı.
        </p>
      )}
      <select
        value={selected ?? ""}
        onChange={(e) => setSelected(Number(e.target.value))}
        className="min-h-[44px] w-full rounded-lg border bg-black/30 px-2 py-2 text-slate-200 outline-none"
        style={{ borderColor: "var(--border)" }}
        title="Seçim sunucuda JARVIS_AUDIO_INPUT_DEVICE ortam değişkeni ile değiştirilebilir"
      >
        {devices.map((d) => (
          <option key={d.index} value={d.index}>
            [{d.index}] {d.name}
            {d.is_default_input ? " (varsayılan)" : ""}
          </option>
        ))}
        {devices.length === 0 && <option value="">Giriş cihazı bulunamadı</option>}
      </select>
      <button
        type="button"
        onClick={() => void testBrowserPermission()}
        className="min-h-[44px] w-full rounded-lg border py-2 text-xs text-slate-300 hover:bg-white/5"
        style={{ borderColor: "var(--border)" }}
      >
        🎙️ Tarayıcı mikrofon iznini test et
      </button>
      {permStatus && <p className="text-emerald-400">{permStatus}</p>}
      {micError && <p className="text-rose-400">{micError}</p>}
    </div>
  );
}
