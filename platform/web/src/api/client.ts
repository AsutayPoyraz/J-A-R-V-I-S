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
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export const clientId = {
  get: () => {
    const existing = localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const created = createClientId();
    localStorage.setItem(CLIENT_ID_KEY, created);
    return created;
  },
};

export const deviceToken = {
  get: () => localStorage.getItem(TOKEN_KEY) ?? "",
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Prompt 1: JWT oturumu.
 *
 * Saklama stratejisi: tokenlar localStorage'da tutulur çünkü backend
 * `allow_credentials=False` ile çalışır ve cookie tabanlı CSRF koruması
 * istemci tarafında ek karmaşıklık getirir. XSS riski kabul edilir; azaltmak
 * için access token 15 dk ile sınırlıdır, refresh her kullanımda döndürülür
 * (rotation) ve sunucu tarafında iptal edilebilir.
 */
const ACCESS_KEY = "jarvis.access_token";
const REFRESH_KEY = "jarvis.refresh_token";

export const authToken = {
  access: () => localStorage.getItem(ACCESS_KEY) ?? "",
  refresh: () => localStorage.getItem(REFRESH_KEY) ?? "",
  set: (access: string, refresh?: string) => {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
  isLoggedIn: () => !!localStorage.getItem(ACCESS_KEY),
};

interface TokenPair {
  access_token: string;
  refresh_token: string;
  user_id?: string;
  first_name?: string;
  last_name?: string;
}

let refreshing: Promise<boolean> | null = null;
/** Misafir modunda X-Client-ID gönderilmez → backend owner='guest:*' üretir. */
function isGuest(): boolean {
  try {
    return sessionStorage.getItem("jarvis.guest") === "1";
  } catch {
    return false;
  }
}

/** Access token'ı refresh token ile yeniler; eşzamanlı çağrılar tek istek paylaşır. */
async function refreshAccess(): Promise<boolean> {
  const refresh = authToken.refresh();
  if (!refresh) return false;
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const resp = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!resp.ok) {
          authToken.clear();
          window.dispatchEvent(new CustomEvent("jarvis:auth-expired"));
          return false;
        }
        const pair = (await resp.json()) as TokenPair;
        authToken.set(pair.access_token, pair.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

function authHeaders(): Record<string, string> {
  const access = authToken.access();
  return access ? { Authorization: `Bearer ${access}` } : {};
}

async function openRequest(path: string, init?: RequestInit): Promise<Response> {
  const token = deviceToken.get();
  const headers: Record<string, string> = {
    ...authHeaders(),
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (!isGuest()) headers["X-Client-ID"] = clientId.get();
  // FormData yüklerken Content-Type'ı tarayıcı boundary ile kendisi koyar.
  if (!(init?.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (token && !isGuest()) headers["X-Device-Token"] = token;
  return fetch(path, { ...init, headers });
}

async function readDetail(resp: Response): Promise<string> {
  let detail = `HTTP ${resp.status}`;
  try {
    const body = await resp.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    /* gövde yok — önemsiz */
  }
  return detail;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp = await openRequest(path, init);
  // Süresi dolmuş access token → bir kez refresh dene, sonra isteği tekrarla.
  if (resp.status === 401 && authToken.refresh() && !path.startsWith("/api/auth/")) {
    if (await refreshAccess()) resp = await openRequest(path, init);
  }
  if (!resp.ok) throw new ApiError(resp.status, await readDetail(resp));
  return (await resp.json()) as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const resp = await openRequest(path);
  if (!resp.ok) throw new ApiError(resp.status, `HTTP ${resp.status}`);
  return resp.blob();
}

export const api = {
  /** Prompt 2: oturum modu + yetenekler (misafirde buton kapısı). */
  session: () =>
    request<{ mode: "guest" | "user" | "local"; capabilities: Record<string, boolean> }>(
      "/api/session"
    ),

  /** Prompt 1: kimlik doğrulama. */
  authRegister: (body: {
    first_name: string;
    last_name: string;
    birth_date: string;
    password: string;
    security_question: string;
    security_answer: string;
  }) => request<TokenPair>("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
  authLogin: (body: { first_name: string; last_name: string; password: string }) =>
    request<TokenPair>("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  authMe: () => request<{ user_id: string; first_name: string; last_name: string; local?: boolean }>("/api/auth/me"),
  authReset: (body: {
    first_name: string;
    last_name: string;
    birth_date: string;
    security_answer: string;
    new_password: string;
  }) =>
    request<{ ok: boolean }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  authLogout: () =>
    request<{ ok: boolean }>("/api/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: authToken.refresh() }),
    }),
  /** Özellik 5A: kullanıcı adı bazlı giriş/kayıt (geriye dönük uyumlu ekleme). */
  authLoginUsername: (username: string, password: string) =>
    request<TokenPair>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  authRegisterUsername: (body: {
    username: string;
    first_name: string;
    last_name: string;
    password: string;
    password_repeat: string;
  }) =>
    request<TokenPair>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  health: () => request<import("../types").HealthInfo>("/api/health"),
  integrations: () =>
    request<{ integrations: Record<string, { configured: boolean; connected?: boolean; reachable?: boolean; detail?: string }> }>(
      "/api/integrations"
    ),
  stats: () => request<import("../types").SystemStats>("/api/system/stats"),
  weather: (refresh = false, coords?: { lat: number; lon: number }) =>
    request<import("../types").WeatherInfo>(
      `/api/weather?${new URLSearchParams({
        ...(refresh ? { refresh: "true" } : {}),
        ...(coords ? { lat: String(coords.lat), lon: String(coords.lon) } : {}),
      }).toString()}`
    ),
  settings: () => request<import("../types").AppSettings>("/api/settings"),
  updateSettings: (
    patch: Partial<{
      background_color: string;
      city: string;
      language: string;
      chat_panel_position: string;
      conversation_mode: string;
      custom_palette: Record<string, string>;
      tts_voice: string;
      tts_rate: number;
      /** Bölüm G (madde 25/26/27): gizlilik, kişilik, erişilebilirlik, sağlık. */
      privacy_mode: boolean;
      auto_lock_minutes: number;
      persona_name: string;
      persona_style: string;
      font_scale: number;
      dyslexic_font: boolean;
      high_contrast: boolean;
      break_reminder_minutes: number;
      daily_limit_minutes: number;
      focus_mode: boolean;
      dashboard_layout: string[];
    }>
  ) =>
    request<import("../types").AppSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  conversation: () =>
    request<{ messages: import("../types").ChatMessage[]; count: number }>(
      "/api/conversation"
    ),
  sendChat: (message: string, provider = "") =>
    request<{
      reply: string;
      error: boolean;
      provider: string;
      model: string;
      provider_used?: string;
      fallback_occurred?: boolean;
      used_tools?: string[];
    }>(
      "/api/chat",
      { method: "POST", body: JSON.stringify({ message, provider }) }
    ),
  /** Özellik 12: çoklu LLM karşılaştırma (yalnızca üyeler). */
  chatCompare: (message: string, providers: string[]) =>
    request<{
      results: {
        provider: string;
        response: string;
        latency_ms: number;
        tokens_used: number;
        model: string;
        error: string;
      }[];
      message: string;
    }>("/api/chat/compare", {
      method: "POST",
      body: JSON.stringify({ message, providers }),
    }),
  clearConversation: () => request<{ cleared: number }>("/api/conversation", { method: "DELETE" }),
  cameraOpen: () => request<import("../types").CameraStatus>("/api/camera/open", { method: "POST" }),
  cameraClose: () => request<import("../types").CameraStatus>("/api/camera/close", { method: "POST" }),
  cameraStatus: () => request<import("../types").CameraStatus>("/api/camera/status"),
  cameraCapture: () =>
    request<{ image: string; captured_at: string }>("/api/camera/capture", { method: "POST" }),

  /** Faz 3: sesli mod uçları. */
  voiceStatus: () => request<import("../types").VoiceStatus>("/api/voice/status"),
  voiceStart: () =>
    request<import("../types").VoiceStatus>("/api/voice/start", { method: "POST" }),
  voiceStop: () =>
    request<import("../types").VoiceStatus>("/api/voice/stop", { method: "POST" }),
  voiceModeOn: (reason?: string) =>
    request<import("../types").VoiceStatus>("/api/voice/mode/on", {
      method: "POST",
      body: JSON.stringify(reason ? { reason } : {}),
    }),
  voiceModeOff: () =>
    request<import("../types").VoiceStatus>("/api/voice/mode/off", { method: "POST" }),
  voiceSay: (text: string) =>
    request<{ spoken: boolean }>("/api/voice/say", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  voiceUpdateSettings: (patch: {
    wake_phrases?: string[];
    wake_response?: string;
    exit_phrases?: string[];
    clap_enabled?: boolean;
    clap_sensitivity?: number;
  }) =>
    request<import("../types").VoiceStatus>("/api/voice/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),

  /** Dışa aktarma indirme bağlantısı (tarayıcı dosyayı indirir). */
  exportConversation: (format: "txt" | "md") =>
    requestBlob(`/api/conversation/export?format=${format}`),

  /** Faz 4: hatırlatıcılar. */
  reminders: (history = false) =>
    request<{ reminders: import("../types").Reminder[] }>(
      `/api/reminders${history ? "?history=true" : ""}`
    ),
  createReminder: (title: string, due_at: string) =>
    request<{ reminder: import("../types").Reminder }>("/api/reminders", {
      method: "POST",
      body: JSON.stringify({ title, due_at }),
    }),
  deleteReminder: (id: number) =>
    request<{ deleted: number }>(`/api/reminders/${id}`, { method: "DELETE" }),
  ackReminder: (id: number) =>
    request<{ reminder: import("../types").Reminder }>(`/api/reminders/${id}/ack`, {
      method: "POST",
    }),
  ackAllAlarms: () =>
    request<{ acked: number }>("/api/reminders/ack-all", { method: "POST" }),
  snoozeReminder: (id: number, minutes = 10) =>
    request<{ reminder: import("../types").Reminder }>(`/api/reminders/${id}/snooze`, {
      method: "POST",
      body: JSON.stringify({ minutes }),
    }),
  reportActivity: () =>
    request<{ silenced: boolean }>("/api/reminders/activity", { method: "POST" }),

  /** Bölüm E: üretkenlik + Memory Bank (madde 18, 23) — routes_agent.py şekilleri. */
  notes: (query = "") =>
    request<{ notes: import("../types").NoteItem[] }>(
      `/api/notes${query ? `?query=${encodeURIComponent(query)}` : ""}`
    ),
  createNote: (title: string, content = "") =>
    request<{ saved: boolean; id: number }>("/api/notes", {
      method: "POST",
      body: JSON.stringify({ title, content }),
    }),
  deleteNote: (id: number) =>
    request<{ deleted: boolean }>(`/api/notes/${id}`, { method: "DELETE" }),
  todos: () =>
    request<{ todos: import("../types").TodoItem[] }>("/api/todos"),
  createTodo: (title: string) =>
    request<{ saved: boolean; id: number }>("/api/todos", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  setTodoDone: (id: number, done: boolean) =>
    request<{ updated: boolean }>(`/api/todos/${id}`, {
      method: "PUT",
      body: JSON.stringify({ done }),
    }),
  deleteTodo: (id: number) =>
    request<{ deleted: boolean }>(`/api/todos/${id}`, { method: "DELETE" }),
  memory: (query = "") =>
    request<{ memories: import("../types").MemoryItem[] }>(
      `/api/memory${query ? `?query=${encodeURIComponent(query)}` : ""}`
    ),
  createMemory: (content: string) =>
    request<{ saved: boolean; id: number }>("/api/memory", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  deleteMemory: (id: number) =>
    request<{ deleted: boolean }>(`/api/memory/${id}`, { method: "DELETE" }),

  /** Bölüm E (madde 9): ekran analizi — vision sağlayıcı anahtarı gerekir. */
  screenAnalyze: (question = "") =>
    request<{ available: boolean; analysis?: string; reason?: string }>(
      "/api/screen/analyze",
      { method: "POST", body: JSON.stringify({ question }) }
    ),

  /** Faz 2: eşleştirme — QR akışı ve cihaz yönetimi (routes_pair.py şekilleri). */
  pairStart: () =>
    request<{ code: string; expires_in: number; url: string }>("/api/pair/start", {
      method: "POST",
    }),
  pairStatus: () =>
    request<{
      pending: boolean;
      expires_in: number | null;
      devices: import("../types").DeviceSummary[];
      lan_ip: string | null;
    }>("/api/pair/status"),
  pairClaim: (code: string, device_name: string) =>
    request<{ device_id: string; name: string; device_token: string }>(
      "/api/pair/claim",
      { method: "POST", body: JSON.stringify({ code, device_name }) }
    ),
  revokeDevice: (id: string) =>
    request<{ revoked: string }>(`/api/pair/devices/${id}`, { method: "DELETE" }),

  /** Faz 2: WoL — kurulum durumu ve test (routes_system.py). */
  wolStatus: () => request<Record<string, unknown>>("/api/system/wol"),
  wolTest: () =>
    request<Record<string, unknown>>("/api/system/wol/wake", { method: "POST" }),

  smartHomeStatus: () => request<import("../types").SmartHomeStatus>("/api/smart-home/status"),
  smartHomeDevices: () =>
    request<{ devices: Record<string, import("../types").SmartHomeDevice[]>; total: number }>(
      "/api/smart-home/devices"
    ),
  smartHomeCommand: (device_id: string, action: "on" | "off" | "brightness" | "temperature", value?: number) =>
    request<{ ok: boolean; device_id: string; action: string }>("/api/smart-home/command", {
      method: "POST",
      body: JSON.stringify({ device_id, action, value }),
    }),
  smartHomeOAuthStart: () =>
    request<{ authorization_url: string }>("/api/smart-home/oauth/start"),
  smartHomeDisconnect: () =>
    request<{ disconnected: boolean }>("/api/smart-home/disconnect", { method: "POST" }),

  /** Bölüm F (madde 19): sesli notlar + dosya etiketleri. */
  voiceNotes: (q = "") =>
    request<{ notes: import("../types").VoiceNoteItem[] }>(
      `/api/voice-notes${q ? `?q=${encodeURIComponent(q)}` : ""}`
    ),
  createVoiceNote: (text: string) =>
    request<{ id: number }>("/api/voice-notes", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  deleteVoiceNote: (id: number) =>
    request<{ deleted: boolean }>(`/api/voice-notes/${id}`, { method: "DELETE" }),
  fileTags: () => request<{ tags: Record<string, string[]> }>("/api/files/tags"),
  setFileTags: (fileName: string, tags: string[]) =>
    request<{ ok: boolean }>(`/api/files/tags/${encodeURIComponent(fileName)}`, {
      method: "PUT",
      body: JSON.stringify({ tags }),
    }),

  /** Bölüm F (madde 20): makrolar + paylaşılan oturumlar. */
  macros: () => request<{ macros: import("../types").MacroItem[] }>("/api/macros"),
  createMacro: (name: string, steps: Record<string, unknown>[] = []) =>
    request<{ id: number }>("/api/macros", {
      method: "POST",
      body: JSON.stringify({ name, steps }),
    }),
  deleteMacro: (id: number) =>
    request<{ deleted: boolean }>(`/api/macros/${id}`, { method: "DELETE" }),
  createSharedSession: (title = "") =>
    request<{ code: string }>("/api/shared/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  sharedSession: (code: string) =>
    request<import("../types").SharedSessionInfo>(`/api/shared/sessions/${code}`),
  joinSharedSession: (code: string, displayName: string) =>
    request<{ joined: boolean }>(`/api/shared/members/${code}`, {
      method: "POST",
      body: JSON.stringify({ display_name: displayName }),
    }),
  sharedMessages: (code: string, sinceId = 0) =>
    request<{ messages: import("../types").SharedMessageItem[] }>(
      `/api/shared/sessions/${code}/messages?since_id=${sinceId}`
    ),
  postSharedMessage: (code: string, content: string, displayName: string) =>
    request<{ id: number }>(`/api/shared/sessions/${code}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, display_name: displayName, role: "user" }),
    }),
  deleteSharedSession: (code: string) =>
    request<{ deleted: boolean }>(`/api/shared/sessions/${code}`, { method: "DELETE" }),

  /** Bölüm F (madde 21): oyunlaştırma — XP yalnızca sunucuda hesaplanır. */
  gamify: () => request<import("../types").GamifyStatus>("/api/gamify"),
  leaderboard: () =>
    request<{ leaders: { name: string; xp: number }[] }>("/api/gamify/leaderboard"),

  /** Bölüm F (madde 24): analitik, geçmiş arama, JSON/CSV + yedek indirme. */
  analytics: (days = 14) =>
    request<import("../types").AnalyticsSummary>(`/api/analytics/summary?days=${days}`),
  historySearch: (q = "", tag = "", dateFrom = "", dateTo = "") => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (tag) p.set("tag", tag);
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    return request<{ results: import("../types").HistoryResult[] }>(
      `/api/history/search?${p.toString()}`
    );
  },
  exportAnalytics: (format: "json" | "csv") =>
    requestBlob(`/api/analytics/export?format=${format}`),
  backupExport: () => requestBlob("/api/backup/export"),
  /** Notları Markdown olarak indir (madde 20: Collaborative Notes MVP). */
  notesExport: () => requestBlob("/api/notes/export"),
  backupImport: (data: Record<string, unknown>) =>
    request<{ imported: Record<string, number> }>("/api/backup/import", {
      method: "POST",
      body: JSON.stringify({ data }),
    }),

  // ══ JARVIS v11 (mega prompt) uçları ═══════════════════════════════════════

  /** Özellik 3: kamera OpenCV kurulumu. */
  cameraInstall: () =>
    request<{ ok: boolean; detail: string; manual_command?: string }>(
      "/api/camera/install",
      { method: "POST" }
    ),

  /** Özellik 4: eşleştirme tanı ucu (yalnızca PC). */
  pairDebug: () =>
    request<{
      server_ip: string | null;
      port: string;
      bind_host: string;
      paired_devices_count: number;
      pairing_required: boolean;
    }>("/api/pair/debug"),

  /** Özellik 5B: kullanıcı API anahtarları (değer ASLA döner değil). */
  listApiKeys: () =>
    request<{ keys: { key_name: string; has_value: boolean; updated_at: string | null }[] }>(
      "/api/user/api-keys"
    ),
  setApiKey: (name: string, value: string) =>
    request<{ ok: boolean; key_name: string }>(`/api/user/api-keys/${name}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  deleteApiKey: (name: string) =>
    request<{ ok: boolean }>(`/api/user/api-keys/${name}`, { method: "DELETE" }),
  testApiKey: (name: string) =>
    request<{ ok: boolean; detail: string; status?: number }>(
      `/api/user/api-keys/test/${name}`,
      { method: "POST" }
    ),

  /** Özellik 6: görev yöneticisi. */
  tasks: (status = "") =>
    request<{ tasks: import("../types").Task[] }>(
      `/api/tasks${status ? `?status=${status}` : ""}`
    ),
  createTask: (payload: {
    title: string;
    project?: string;
    priority?: string;
    due_date?: string;
  }) =>
    request<{ task: import("../types").Task }>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTask: (id: number, patch: Partial<import("../types").Task>) =>
    request<{ task: import("../types").Task }>(`/api/tasks/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  deleteTask: (id: number) =>
    request<{ ok: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),

  /** Özellik 9: komut makroları (trigger'lı; section_f /api/macros'tan AYRI). */
  commandMacros: () =>
    request<{ macros: import("../types").CommandMacro[] }>("/api/command-macros"),
  createCommandMacro: (payload: {
    name: string;
    trigger_phrase: string;
    steps: { type: string; params: Record<string, unknown> }[];
  }) =>
    request<{ macro: import("../types").CommandMacro }>("/api/command-macros", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteCommandMacro: (id: number) =>
    request<{ ok: boolean }>(`/api/command-macros/${id}`, { method: "DELETE" }),
  runCommandMacro: (id: number) =>
    request<{
      macro: string;
      outputs: { type: string; reply?: string; error?: string }[];
    }>(`/api/command-macros/${id}/run`, { method: "POST" }),

  /** Özellik 10: alışkanlıklar + üretkenlik. */
  habits: () => request<{ habits: import("../types").Habit[] }>("/api/habits"),
  createHabit: (payload: { name: string; icon?: string; color?: string }) =>
    request<{ habit: import("../types").Habit }>("/api/habits", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteHabit: (id: number) =>
    request<{ ok: boolean }>(`/api/habits/${id}`, { method: "DELETE" }),
  logHabit: (id: number, completed = true) =>
    request<{ ok: boolean }>(`/api/habits/${id}/log`, {
      method: "POST",
      body: JSON.stringify({ completed }),
    }),
  habitStats: () =>
    request<{
      total: number;
      best_streak: number;
      completion_rate: number;
      week: { date: string; done: number; of: number }[];
    }>("/api/habits/stats"),
  productivityInsights: () =>
    request<{ insight: string; source: string; data: unknown[] }>(
      "/api/productivity/insights"
    ),
  productivitySession: (focus_minutes: number, mood: number) =>
    request<{ session: unknown }>("/api/productivity/session", {
      method: "POST",
      body: JSON.stringify({ focus_minutes, mood }),
    }),

  /** Özellik 11: günlük özet. */
  generateSummary: (channels = "chat") =>
    request<{ ok: boolean; date: string; summary: string; sent: string[] }>(
      "/api/summary/generate",
      { method: "POST", body: JSON.stringify({ channels }) }
    ),
  summaryHistory: () =>
    request<{
      summaries: {
        id: number;
        date: string;
        content: string;
        channels: string;
        created_at: string;
      }[];
    }>("/api/summary/history"),

  /** Özellik 19: konum. */
  locationDetect: () =>
    request<{
      ok: boolean;
      city: string;
      country: string;
      timezone: string;
      source: string;
    }>("/api/location/detect"),
  reverseGeocode: (lat: number, lon: number) =>
    request<{ ok: boolean; city: string; country: string }>(
      "/api/location/reverse-geocode",
      { method: "POST", body: JSON.stringify({ lat, lon }) }
    ),
  setLocation: (city: string) =>
    request<{ ok: boolean; city: string }>("/api/location/set", {
      method: "PUT",
      body: JSON.stringify({ city }),
    }),

  /** Özellik 7: ekran VISION analizi (onaylı getDisplayMedia → base64 kare).
   * Not: Bölüm E'nin soru bazlı `screenAnalyze`'ından farklı uçtur. */
  screenAnalyzeImage: (imageDataUrl: string) =>
    request<{ ok: boolean; suggestion: string; detail?: string }>(
      "/api/screen/vision",
      { method: "POST", body: JSON.stringify({ image: imageDataUrl }) }
    ),

  /** Özellik 8: bilgi tabanı (RAG). */
  knowledgeDocuments: () =>
    request<{
      documents: {
        id: number;
        name: string;
        chunks_count: number;
        status: string;
        error: string;
        created_at: string;
      }[];
    }>("/api/knowledge/documents"),
  knowledgeUpload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ ok: boolean; document_id: number; chunks: number }>(
      "/api/knowledge/upload",
      { method: "POST", body: form }
    );
  },
  knowledgeDelete: (id: number) =>
    request<{ ok: boolean }>(`/api/knowledge/${id}`, { method: "DELETE" }),
  knowledgeSearch: (q: string) =>
    request<{
      results: { content: string; document_name: string; score: number }[];
    }>(`/api/knowledge/search?q=${encodeURIComponent(q)}`),

  /** Özellik 17: web ATLAS. */
  atlasCreateTask: (instruction: string) =>
    request<{ task_id: string; type: string; status: string }>("/api/atlas/task", {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  atlasTask: (id: string) =>
    request<import("../types").AtlasTask>(`/api/atlas/task/${id}`),
  atlasCancelTask: (id: string) =>
    request<{ ok: boolean }>(`/api/atlas/task/${id}`, { method: "DELETE" }),

  /** Özellik 14: ses cihazları (mikrofon seçimi). */
  voiceDevices: () =>
    request<{
      devices: {
        index: number;
        name: string;
        max_input_channels: number;
        max_output_channels: number;
        default_samplerate: number;
        is_default_input: boolean;
      }[];
      inputs: { index: number; name: string; is_default_input: boolean }[];
      selected: number | null;
      sd_available: boolean;
    }>("/api/voice/devices"),
};

/** Bölüm G: gizlilik/sağlık uçları — /api önekli yardımcı.
 * Gövde nesneyse otomatik JSON'a çevrilir; auth/refresh `request` içinde. */
type PrivInit = Omit<RequestInit, "body"> & { body?: unknown };
async function privReq<T = unknown>(path: string, init: PrivInit = {}): Promise<T> {
  const raw: unknown = init.body;
  const body =
    raw === undefined || typeof raw === "string"
      ? (raw as BodyInit | undefined)
      : JSON.stringify(raw);
  return request<T>(`/api${path}`, { ...init, body } as RequestInit);
}

export async function fetchPrivacyNotes(): Promise<unknown> {
  return privReq("/privacy/notes", { method: "GET" });
}

export async function createPrivacyNote(payload: Record<string, unknown>): Promise<unknown> {
  return privReq("/privacy/notes", { method: "POST", body: payload });
}

export async function deletePrivacyNote(id: string | number): Promise<unknown> {
  return privReq(`/privacy/notes/${id}`, { method: "DELETE" });
}

export async function fetchPrivacyPermissions(): Promise<unknown> {
  return privReq("/privacy/permissions", { method: "GET" });
}

export async function fetchPrivacyAudit(): Promise<unknown> {
  return privReq("/privacy/audit", { method: "GET" });
}

/** Hassas işlem iznini aç/kapa (madde 25; guards.require_permission uygular). */
export async function setPrivacyPermission(key: string, allowed: boolean): Promise<unknown> {
  return privReq(`/privacy/permissions/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: { allowed },
  });
}

/** Madde 27: ruh hâli + günlük kullanım + mola/limit ayarları. */
export async function fetchWellbeing(): Promise<unknown> {
  return privReq("/health/wellbeing", { method: "GET" });
}

export async function putMood(mood: string): Promise<unknown> {
  return privReq("/health/mood", { method: "PUT", body: { mood } });
}

/** Güvenlik denetim kaydını CSV olarak indir (madde 25). */
export function auditCsv(days = 90): Promise<Blob> {
  return requestBlob(`/api/privacy/audit/export.csv?days=${days}`);
}
