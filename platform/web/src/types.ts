/** Backend ile paylaşılan tip tanımları (Faz 1). */

export type LogoState = "idle" | "thinking" | "speaking" | "offline";

export interface CpuInfo {
  percent: number;
  physical_cores: number;
  logical_cores: number;
  freq_mhz: number | null;
}

export interface MemoryInfo {
  total_gb: number;
  used_gb: number;
  percent: number;
}

export interface DiskInfo {
  total_gb: number;
  used_gb: number;
  percent: number;
}

export interface SystemStats {
  timestamp: string;
  cpu: CpuInfo;
  memory: MemoryInfo;
  disk: DiskInfo;
  uptime_seconds: number;
  boot_time: string;
  load_level: "low" | "medium" | "high";
  command_count?: number;
  session_count?: number;
  /** Faz 3: mikrofon durumu akışta her zaman taşınır. */
  voice?: VoiceStatus;
}

export interface HealthInfo {
  status: string;
  version: string;
  agent_uptime_seconds: number;
  llm_provider: string;
  llm_ready: boolean;
  session_count: number;
}

export interface WeatherInfo {
  available: boolean;
  reason?: string;
  city?: string;
  temperature?: number;
  feels_like?: number;
  humidity?: number;
  wind_speed?: number;
  description?: string;
  icon?: string;
  lat?: number;
  lon?: number;
  fetched_at: string;
}

export interface ChatMessage {
  id: number | string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface CameraStatus {
  status: "live" | "off";
  width: number | null;
  height: number | null;
}

/** Faz 3: sesli mod durumu — /api/voice/status ve /ws/stats içindeki "voice". */
export interface VoiceStatus {
  mic: "off" | "wake" | "voice";
  session: null | "listening" | "thinking" | "speaking";
  mic_available: boolean;
  local_stt: boolean;
  clap_enabled: boolean;
  clap_sensitivity: number;
  wake_phrases: string[];
  exit_phrases: string[];
  last_heard?: string | null;
  last_reply?: string | null;
  error?: string | null;
}

export type BackgroundColor =
  | "maroon"
  | "light"
  | "dark"
  | "custom"
  | "red"
  | "green"
  | "blue";
export type Language = "tr" | "en";
export type ChatPanelPosition = "right" | "center";
export type ConversationMode = "formal" | "casual" | "adaptive";

/** Özel palet: CSS değişkenlerine yazılan değerler ("r g b" | "#hex"). */
export interface CustomPalette {
  accent?: string;
  accent_soft?: string;
  bg_page?: string;
}

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
  room: string;
  type: string;
  traits: string[];
  state: Record<string, unknown>;
  online: boolean;
}

export interface SmartHomeStatus {
  configured: boolean;
  connected: boolean;
  reason?: string;
}
