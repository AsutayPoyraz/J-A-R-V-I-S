/** Backend ile paylaşılan tip tanımları (Faz 1 + v11). */

// ══ JARVIS v11 (mega prompt) tipleri ════════════════════════════════════════

/** Özellik 6: görev yöneticisi. */
export interface Task {
  id: number;
  project_id: number | null;
  project_name?: string | null;
  title: string;
  description: string;
  priority: "low" | "medium" | "high" | "urgent";
  status: "todo" | "in_progress" | "done";
  due_date: string | null;
  created_at: string;
  updated_at: string;
  subtasks?: { id: number; task_id: number; title: string; done: number }[];
}

/** Özellik 9: komut makrosu (trigger'lı). */
export interface CommandMacro {
  id: number;
  name: string;
  trigger_phrase: string;
  steps: {
    type: "chat" | "api_call" | "delay";
    params: Record<string, unknown>;
  }[];
  created_at: string;
}

/** Özellik 10: alışkanlık. */
export interface Habit {
  id: number;
  name: string;
  frequency: string;
  color: string;
  icon: string;
  today_done: boolean;
  streak: number;
  logs: { date: string; completed: boolean }[];
}

/** Özellik 17: ATLAS web görevi. */
export interface AtlasTask {
  task_id: string;
  instruction: string;
  type: string;
  status: "queued" | "running" | "done" | "error";
  steps: { index: number; description: string; status: string; detail?: string }[];
  result: string;
}

/** Özellik 2: istemci (bu cihaz) istatistikleri. */
export interface ClientStats {
  device_type: "phone" | "tablet" | "desktop" | "laptop";
  platform: string;
  device_memory_gb: number | null;
  cpu_cores: number | null;
  js_heap_used_mb: number | null;
  js_heap_limit_mb: number | null;
  battery_percent: number | null;
  battery_charging: boolean | null;
  connection_type: string;
  downlink_mbps: number | null;
  screen_width: number;
  screen_height: number;
  pixel_ratio: number;
  online: boolean;
  updated_at: number;
}

/** Özellik 12: karşılaştırma yanıtı. */
export interface CompareResult {
  provider: string;
  response: string;
  latency_ms: number;
  tokens_used: number;
  model: string;
  error: string;
}

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
  /** Özellik 18: yanıtı üreten sağlayıcı (fallback bilgisiyle). */
  provider?: string;
  fallback?: boolean;
  content: string;
  created_at: string;
}

export interface CameraStatus {
  status: "live" | "off";
  width: number | null;
  height: number | null;
  /** Özellik 3: zenginleştirilmiş durum alanları (/api/camera/status). */
  opencv_installed?: boolean;
  camera_available?: boolean;
  disabled_by_env?: boolean;
  error?: string;
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
  /** Bölüm G (madde 25/26/27): gizlilik, kişilik, erişilebilirlik, sağlık. */
  privacy_mode?: boolean;
  auto_lock_minutes?: number;
  persona_name?: string;
  persona_style?: string;
  font_scale?: number;
  dyslexic_font?: boolean;
  high_contrast?: boolean;
  break_reminder_minutes?: number;
  daily_limit_minutes?: number;
  focus_mode?: boolean;
  mood?: string;
  dashboard_layout?: string[];
  allowed_persona_styles?: string[];
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

/** Bölüm E: notlar / yapılacaklar / Memory Bank (madde 18, 23). */
export interface NoteItem {
  id: number;
  title: string;
  content: string;
  created_at: string;
}

export interface TodoItem {
  id: number;
  title: string;
  done: number;
  created_at: string;
}

export interface MemoryItem {
  id: number;
  content: string;
  created_at: string;
}

/** Bölüm F (madde 19/20/21/24): sesli notlar, makrolar, oyunlaştırma, analitik. */
export interface VoiceNoteItem {
  id: number;
  text: string;
  created_at: string;
}

export interface MacroItem {
  id: number;
  name: string;
  steps: Record<string, unknown>[];
  created_at: string;
}

export interface SharedMember {
  owner_id: string;
  display_name: string;
  joined_at: string;
}

export interface SharedSessionInfo {
  code: string;
  owner_id: string;
  title: string;
  created_at: string;
  members: SharedMember[];
}

export interface SharedMessageItem {
  id: number;
  owner_id: string;
  display_name: string;
  role: string;
  content: string;
  created_at: string;
}

export interface DailyTask {
  code: string;
  goal: number;
  done: number;
}

export interface GamifyStatus {
  xp_total: number;
  level: number;
  streak_days: number;
  counts: Record<string, number>;
  level_progress: number;
  today_xp: number;
  badges: { code: string; earned_at: string }[];
  daily_tasks: DailyTask[];
  /** Opsiyonel: ENABLE_LEADERBOARD=1 iken merged yanıtla gelir (madde 21). */
  leaderboard?: { name: string; xp: number }[];
}

export interface AnalyticsDay {
  date: string;
  [key: string]: number | string;
}

export interface AnalyticsSummary {
  days: AnalyticsDay[];
  totals: Record<string, number>;
  period_days: number;
}

export interface HistoryResult {
  source: string;
  id: number | string;
  text: string;
  detail?: string;
  tags?: string;
  created_at: string;
}

// ===== Section G: Privacy / Wellness / A11y (auto) =====
export interface PrivacyNoteItem { id: string; title: string; created_at?: string; content?: string; [k: string]: unknown; }
export interface PrivacyVaultStatus { locked?: boolean; auto_lock_minutes?: number; privacy_mode?: boolean; [k: string]: unknown; }
export interface PermissionState { [k: string]: boolean; }
export interface AuditLogEntry { id?: string; ts?: string; action?: string; detail?: string; [k: string]: unknown; }
export interface MoodEntryItem { id?: string; mood?: string; note?: string; ts?: string; [k: string]: unknown; }
export interface WellbeingSummaryData { focus_mode?: boolean; daily_limit?: number; used_today?: number; last_mood?: string; [k: string]: unknown; }
export interface GAccessibilitySettings { font_size?: string; dyslexic_font?: boolean; high_contrast?: boolean; [k: string]: unknown; }
