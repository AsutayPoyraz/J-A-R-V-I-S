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
  sendChat: (message: string) =>
    request<{ reply: string; error: boolean; provider: string; model: string }>(
      "/api/chat",
      { method: "POST", body: JSON.stringify({ message }) }
    ),
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
};
