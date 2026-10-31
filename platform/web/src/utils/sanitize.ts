/**
 * sanitizeSettings — Özellik 13: form verilerini null/undefined'a dayanıklı hale getirir.
 *
 * "Cannot read properties of null (reading 'trim')" kök nedeni: null/undefined
 * alanlar. Bu yardımcı gönderim öncesi TÜM alanları güvenli tiplere normalize
 * eder: null/undefined → "" (string alanlar), boole → false, sayı → varsayılan.
 */
type Settings = Record<string, unknown>;

const DEFAULTS: Record<string, string | number | boolean> = {
  background_color: "maroon",
  language: "tr",
  chat_position: "right",
  chat_panel_position: "right",
  conversation_mode: "adaptive",
  tts_voice: "tr",
  tts_rate: 1.0,
  font_scale: 1.0,
  auto_lock_minutes: 0,
  break_reminder_minutes: 0,
  daily_limit_minutes: 0,
};

export function safeTrim(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

export function sanitizeSettings(form: Settings): Settings {
  const out: Settings = {};
  for (const [key, raw] of Object.entries(form)) {
    if (raw === null || raw === undefined) {
      // Bilinen anahtarlar varsayılana, bilinmeyenler boş string'e normalize.
      out[key] = key in DEFAULTS ? DEFAULTS[key] : "";
      continue;
    }
    if (typeof raw === "string") {
      const trimmed = raw.trim();
      out[key] = trimmed === "" && key in DEFAULTS ? DEFAULTS[key] : trimmed;
      continue;
    }
    if (typeof raw === "number" && Number.isNaN(raw)) {
      out[key] = key in DEFAULTS ? DEFAULTS[key] : 0;
      continue;
    }
    out[key] = raw;
  }
  return out;
}
