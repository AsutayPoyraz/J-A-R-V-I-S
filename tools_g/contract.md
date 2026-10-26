
=== CLIENT head ===
/** Backend API istemcisi — tüm fetch çağrıları tek yerde.

Offline davranış: her çağrı hata fırlatır, çağıran katman yakalar ve
arayüz "--" gösterir. fetch'in kendisi asla uygulamayı çökertmez.
*/

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}

/** Faz 2: eşleşmiş cihaz belirteci — telefonda claim sonrası saklanır. */
const TOKEN_KEY = "jarvis.device_token";
const CLIENT_ID_KEY = "jarvis.client_id";
function createClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

=== CLIENT base+exports ===
export const api = {
export class ApiError extends Error {
export const clientId = {
export const deviceToken = {
export const authToken = {
export const api = {

=== TYPES AppSettings ===
export interface AppSettings {
  background_color: BackgroundColor;
  city: string;
  /** Madde 3: arayüz dili (tr/en) — DB'de kullanıcıya özel saklanır. */
  language: Language;
  /** Madde 32: sohbet paneli konumu (right/center). */
  chat_panel_position: ChatPanelPosition;
  /** Prompt 3: konuşma modu (formal/casual/adaptive). */
  conversation_mode: ConversationMode;
  /** Prompt 0/4: özel tema paleti. */
  custom_palette: CustomPalette | null;
  /** Prompt 6: kritik komutlarda 2FA. */
  twofa_enabled?: boolean;
  /** Madde 14: TTS ses (tr/en) ve hız (0.5-2.0x) tercihleri. */
  tts_voice: string;
  tts_rate: number;
  allowed_background_colors: BackgroundColor[];
  allowed_conversation_modes?: ConversationMode[];
  allowed_tts_voices?: string[];
}

/** Faz 4: hatırlatıcı — reminders/service.py şemasıyla uyumlu. */
export interface Reminder {
  id: number;
  title: string;
  due_at: string;
  status: "pending" | "firing" | "acked" | "expired";
  repeat_count: number;
  last_fired_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Faz 2: eşleşmiş cihaz. */
export interface DeviceSummary {
  id: string;
  name: string;
  platform?: string;
  created_at?: string;
  last_seen_at?: string | null;
}

export interface SmartHomeDevice {
  id: string;
  name: string;

=== TYPES G hits ===

=== I18N anchors ===
10: export type Lang = "tr" | "en";
16: const tr: Dict = {
216: const en: Dict = {
425: export function getLang(): Lang {
430: export function setLang(lang: Lang): void {
442: export function t(key: string): string {
454: export function missingKeys(): string[] {
214: };
406: };
TOTAL 458 privacy/a11y/wellbeing hits=0

=== MODAL ===
/** Ayarlar modalı: tema (madde 4), dil (madde 3), panel konumu (madde 32),
 * şehir ve ses ayarları (Faz 3). Tüm metinler i18n'den gelir. */
import { useEffect, useState } from "react";
import { t, getLang } from "../i18n";
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
onSave: (patch: {
onSaveVoice: (patch: {
open, settings, online, health, integrations, voice, onClose, onSave, onSaveVoice, onChangeLanguage,
await onSave({
await onSaveVoice({
privacy/a11y/wellbeing hits=0

=== APP ===
/** JARVIS Web UI — Faz 1 yerçekirdeği düzeni.

Masaüstü: sol kartlar | orta logo sahnesi | sağ sohbet paneli.
Mobil: logo + sohbet; sistem kartları açılır çekmecede.
*/
import { useEffect, useRef, useState } from "react";
import { useJarvis } from "./hooks/useJarvis";
import { api } from "./api/client";
import TopBar from "./components/TopBar";
import GuestBanner from "./components/GuestBanner";
import SystemStatsCard from "./components/SystemStatsCard";
import WeatherCard from "./components/WeatherCard";
import CameraCard from "./components/CameraCard";
import UptimeCard from "./components/UptimeCard";
import ReminderCard from "./components/ReminderCard";
import AgentCard from "./components/AgentCard";
import AgentCard from "./components/AgentCard";
import SocialCard from "./components/SocialCard";
<AgentCard />
<SocialCard />
? "relative z-10 grid min-h-0 flex-1 place-items-center p-3"
? "relative z-10 grid flex-1 items-start gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)]"
: "relative z-10 grid flex-1 items-start gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)_340px]"

=== CSS ===
a11y hits=0 total=379
}
body {
  zoom: var(--jarvis-font-scale, 1);
}

=== PRIVACY EP ===
def _ctx(request: Request) -> dict:
@router.get("/api/privacy/notes")
def privacy_notes_list(ctx: dict = Depends(_ctx)) -> dict:
@router.post("/api/privacy/notes")
def privacy_notes_create(body: SecureNoteBody, ctx: dict = Depends(_ctx)) -> dict:
@router.delete("/api/privacy/notes/{note_id}")
def privacy_notes_delete(note_id: int, ctx: dict = Depends(_ctx)) -> dict:
@router.get("/api/privacy/permissions")
def privacy_permissions(ctx: dict = Depends(_ctx)) -> dict:
@router.put("/api/privacy/permissions/{key}")
def privacy_permission_set(
@router.get("/api/privacy/audit")
def privacy_audit(days: int = 30, limit: int = 200, ctx: dict = Depends(_ctx)) -> dict:
@router.get("/api/privacy/audit/export.csv")
def privacy_audit_export(days: int = 90, ctx: dict = Depends(_ctx)):
@router.get("/api/health/wellbeing")
def health_wellbeing(ctx: dict = Depends(_ctx)) -> dict:
@router.put("/api/health/mood")
def health_mood(body: MoodBody, ctx: dict = Depends(_ctx)) -> dict:

=== SETTINGS G KEYS ===
privacy_mode: bool | None = None
font_scale: float | None = None
dyslexic_font: bool | None = None
break_reminder_minutes: int | None = None
daily_limit_minutes: int | None = None
focus_mode: bool | None = None
"privacy_mode": bool(row.get("privacy_mode")),
"font_scale": _clamp_float(row.get("font_scale"), 0.8, 1.5, 1.0),
"dyslexic_font": bool(row.get("dyslexic_font")),
"break_reminder_minutes": _clamp_int(row.get("break_reminder_minutes"), 0, 240, 0),
"daily_limit_minutes": _clamp_int(row.get("daily_limit_minutes"), 0, 1440, 0),
"focus_mode": bool(row.get("focus_mode")),
"mood": str(row.get("mood") or "neutral"),
if payload.privacy_mode is not None:
patch["privacy_mode"] = "1" if payload.privacy_mode else "0"
if payload.font_scale is not None:
if not (0.8 <= payload.font_scale <= 1.5):
patch["font_scale"] = str(round(payload.font_scale, 2))
if payload.dyslexic_font is not None:
patch["dyslexic_font"] = "1" if payload.dyslexic_font else "0"
if payload.break_reminder_minutes is not None:
if not (0 <= payload.break_reminder_minutes <= 240):
patch["break_reminder_minutes"] = str(int(payload.break_reminder_minutes))
if payload.daily_limit_minutes is not None:
if not (0 <= payload.daily_limit_minutes <= 1440):
patch["daily_limit_minutes"] = str(int(payload.daily_limit_minutes))
if payload.focus_mode is not None:
patch["focus_mode"] = "1" if payload.focus_mode else "0"

=== SECTION_G ===
def _now() -> str:
def _today() -> str:
def audit(owner_id: str, event_type: str, detail: str = "", ip: str = "") -> None:
def list_audit(owner_id: str, days: int = 30, limit: int = 500) -> list[dict[str, Any]]:
def add_secure_note(owner_id: str, title_cipher: str, body_cipher: str) -> int | None:
def list_secure_notes(owner_id: str) -> list[dict[str, Any]]:
def delete_secure_note(owner_id: str, note_id: int) -> bool:
def get_permissions(owner_id: str) -> dict[str, bool]:
def set_permission(owner_id: str, permission: str, allowed: bool) -> None:
def has_permission(owner_id: str, permission: str) -> bool:
def set_mood(owner_id: str, mood: str) -> bool:
def get_mood(owner_id: str) -> str:
def touch_usage(owner_id: str, delta_seconds: int | None = None) -> None:
def usage_today(owner_id: str) -> dict[str, Any]:

=== GUARDS ===
def is_guest(request: Any) -> bool:
def require_not_guest(request: Any) -> None:
def mode_of(request: Any) -> str:
def capabilities_of(request: Any) -> dict[str, bool]:
def session_payload(request: Any) -> dict[str, Any]:
def require_permission(request: Any, key: str) -> None:

=== PYTEST ===
........................................................................ [ 46%]
........................................................................ [ 92%]
............                                                             [100%]