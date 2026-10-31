/**
 * useJarvis — uygulamanın tek merkezi state hook'u.
 *
 * Bağlantı stratejisi (offline gereksinimi):
 * 1. Birincil: /ws/stats WebSocket'i. Mesaj gelirse online=true.
 * 2. WS koparsa: REST /api/system/stats ile 5 sn'de bir denenir;
 *    cevap gelirse online kalır (transport düşmüş olsa da).
 * 3. İkisi de başarısızsa: online=false → kartlarda "--" gösterilir.
 * 4. WS her kapandığında üstel geri çekmeyle (3s → 15s) yeniden bağlanır.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { clientId, deviceToken } from "../api/client";
import { getLang, setLang as persistLang, t } from "../i18n";
import { isGuestMode } from "../components/LoginGate";
import type {
  AppSettings,
  CameraStatus,
  ChatMessage,
  HealthInfo,
  Language,
  Reminder,
  SystemStats,
  VoiceStatus,
  WeatherInfo,
} from "../types";

const MAX_CLIENT_MESSAGES = 200;

export function useJarvis() {
  const [online, setOnline] = useState(false);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [integrations, setIntegrations] = useState<
    Record<string, { configured: boolean; connected?: boolean; reachable?: boolean; detail?: string }> | null
  >(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [weather, setWeather] = useState<WeatherInfo | null>(null);
  /** Madde 3: arayüz dili (localStorage + DB senkron). */
  const [lang, setLangState] = useState<Language>(() => getLang());

  const [camera, setCamera] = useState<CameraStatus>({
    status: "off",
    width: null,
    height: null,
  });
  const [photo, setPhoto] = useState<string | null>(null);
  const [cameraBusy, setCameraBusy] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  /** Faz 3: sesli mod durumu (WS akışından + REST'ten beslenir). */
  const [voice, setVoice] = useState<VoiceStatus | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryRef = useRef(0);
  const onlineRef = useRef(false);
  const offlineNoteShown = useRef(false);
  /** WS hatırlatıcı kareleri geldiğinde CRUD yenileme tetikleyicisi. */
  const remindersRefreshRef = useRef<(() => void) | null>(null);
  /** Özellik 16.4: WS kopunca exponential backoff + "Yeniden bağlanıyor" durumu. */
  const [reconnecting, setReconnecting] = useState(false);
  /** Özellik 7/11: WS üzerinden gelen öneri/özet bildirimleri. */
  const [screenSuggestion, setScreenSuggestion] = useState<string | null>(null);
  const [dailySummary, setDailySummary] = useState<string | null>(null);

  const markOnline = useCallback((value: boolean) => {
    if (value) offlineNoteShown.current = false;
    onlineRef.current = value;
    setOnline(value);
  }, []);

  const wsConnect = useCallback(() => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const token = deviceToken.get();
    const params = new URLSearchParams({ client_id: clientId.get() });
    if (token) params.set("token", token);
    const ws = new WebSocket(`${proto}//${location.host}/ws/stats?${params.toString()}`);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as SystemStats & {
          type?: string;
          suggestion?: string;
          content?: string;
        };
        const incomingClientId = (data as { client_id?: string }).client_id;
        if (incomingClientId && incomingClientId !== clientId.get()) return;
        if ((data as { type?: string }).type === "reminder") {
          // Hatırlatıcı olayı (created/fired/acked/deleted/expired) — istatistik
          // karesi değil; listeyi tazeleyip bu kareyi stats'a yazma.
          remindersRefreshRef.current?.();
          return;
        }
        // Özellik 7: ekran önerisi (vision analizi) — toast gösterilir.
        if ((data as { type?: string }).type === "screen.suggestion") {
          if (data.suggestion) setScreenSuggestion(data.suggestion);
          return;
        }
        // Özellik 11: günlük özet bildirimi.
        if ((data as { type?: string }).type === "daily.summary") {
          if (data.content) setDailySummary(data.content);
          return;
        }
        setStats(data);
        if (data.voice) setVoice(data.voice);
        markOnline(true);
        retryRef.current = 0;
        setReconnecting(false);
      } catch {
        /* bozuk kare — yoksay */
      }
    };
    ws.onclose = () => {
      markOnline(false);
      // Özellik 16.4: exponential backoff 1s → 2s → 4s → ... → max 30s.
      retryRef.current += 1;
      setReconnecting(true);
      const delay = Math.min(1000 * 2 ** (retryRef.current - 1), 30_000);
      retryTimerRef.current = setTimeout(wsConnect, delay);
    };
    ws.onerror = () => ws.close();
  }, [markOnline]);

  useEffect(() => {
    wsConnect();
    return () => {
      wsRef.current?.close();
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    };
  }, [wsConnect]);

  // REST yedeği: WS yoklarken de online tespit edebilsin
  useEffect(() => {
    const id = setInterval(async () => {
      if (onlineRef.current && wsRef.current?.readyState === WebSocket.OPEN) return;
      try {
        const s = await api.stats();
        setStats(s);
        if (s.voice) setVoice(s.voice);
        markOnline(true);
      } catch {
        markOnline(false);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [markOnline]);

  // Sağlık bilgisi (LLM sağlayıcı adı vb.)
  useEffect(() => {
    const tick = async () => {
      try {
        setHealth(await api.health());
        setIntegrations((await api.integrations()).integrations);
      } catch {
        /* offline */
      }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    // Misafir: geçmiş çağrılmaz (403) — boş sohbetle başlanır.
    if (!isGuestMode()) {
      api
        .conversation()
        .then((r) => setMessages(r.messages.slice(-MAX_CLIENT_MESSAGES)))
        .catch(() => {});
    }
    api
      .settings()
      .then((s) => setSettings(s))
      .catch(() => {});
  }, []);

  // Tema rengini <html data-bg> uygula (Prompt 0/4: light/dark/custom dahil).
  // localStorage'da son tercih tutulur → index.html'deki inline script FOUC'u önler.
  useEffect(() => {
    if (!settings?.background_color) return;
    const root = document.documentElement;
    root.classList.add("theme-transition");
    root.dataset.bg = settings.background_color;
    try {
      localStorage.setItem("jarvis.theme", settings.background_color);
    } catch {
      /* gizli mod */
    }
    // Özel palet değişkenlerini uygula / temizle.
    const palette = settings.custom_palette;
    if (settings.background_color === "custom" && palette) {
      if (palette.accent) root.style.setProperty("--accent-rgb", palette.accent);
      if (palette.accent_soft) root.style.setProperty("--accent-soft-rgb", palette.accent_soft);
      if (palette.bg_page) root.style.setProperty("--bg-page", palette.bg_page);
      try {
        localStorage.setItem("jarvis.palette", JSON.stringify(palette));
      } catch {
        /* gizli mod */
      }
    } else {
      root.style.removeProperty("--accent-rgb");
      root.style.removeProperty("--accent-soft-rgb");
      root.style.removeProperty("--bg-page");
    }
    const timer = window.setTimeout(() => root.classList.remove("theme-transition"), 300);
    return () => window.clearTimeout(timer);
  }, [settings?.background_color, settings?.custom_palette]);

  // Madde 32: sohbet paneli konumunu <html data-chat-position> uygula
  useEffect(() => {
    document.documentElement.dataset.chatPosition =
      settings?.chat_panel_position === "center" ? "center" : "right";
  }, [settings?.chat_panel_position]);

  // Madde 3: i18n dil değişiklik olaylarını dinle (SettingsModal'dan gelir)
  useEffect(() => {
    const onLangChange = () => setLangState(getLang());
    window.addEventListener("jarvis:lang-change", onLangChange);
    return () => window.removeEventListener("jarvis:lang-change", onLangChange);
  }, []);

  // Dil etiketini <html lang> ile baştan eşitle
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // Çevrimdışı bilgi mesajı (istemci tarafında, DB'ye yazılmaz; i18n'den gelir)
  useEffect(() => {
    if (!online && !offlineNoteShown.current) {
      offlineNoteShown.current = true;
      setMessages((prev) => [...prev.slice(-(MAX_CLIENT_MESSAGES - 1)),
        {
          id: `offline-${Date.now()}`,
          role: "system",
          content: t("chat.offline_note"),
          created_at: new Date().toISOString(),
        },
      ]);
    }
  }, [online]);

  // ── Hava durumu: yükle + 10 dk'da bir yenile ──
  // Prompt 0 item 6: tarayıcı Geolocation → koordinattan şehir. İzin reddi
  // veya API yoksa kayıtlı şehir (yoksa backend'de İstanbul) kullanılır.
  const refreshWeather = useCallback(async (force = false) => {
    let coords: { lat: number; lon: number } | undefined;
    try {
      if (
        localStorage.getItem("jarvis.geo_enabled") !== "0" &&
        typeof navigator !== "undefined" &&
        navigator.geolocation &&
        localStorage.getItem("jarvis.geo_denied") !== "1"
      ) {
        coords = await new Promise((resolve) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
            () => {
              try {
                localStorage.setItem("jarvis.geo_denied", "1");
              } catch {
                /* yok */
              }
              resolve(undefined);
            },
            { timeout: 6000, maximumAge: 15 * 60 * 1000, enableHighAccuracy: false }
          );
        });
      }
    } catch {
      coords = undefined;
    }
    try {
      setWeather(await api.weather(force, coords));
    } catch {
      setWeather({ available: false, reason: "backend_offline", fetched_at: "" });
    }
  }, []);

  useEffect(() => {
    refreshWeather();
    const id = setInterval(() => refreshWeather(), 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [refreshWeather, settings?.city]);

  // ── Sohbet eylemleri ──
  /** Özellik 18: kullanıcı sağlayıcı tercihi (session bazında hatırlanır). */
  const [providerPref, setProviderPrefState] = useState<string>(() => {
    try {
      return sessionStorage.getItem("jarvis.provider") ?? "";
    } catch {
      return "";
    }
  });
  const setProviderPref = useCallback((value: string) => {
    setProviderPrefState(value);
    try {
      sessionStorage.setItem("jarvis.provider", value);
    } catch {
      /* oturumluk yedek yok */
    }
  }, []);

  const sendMessage = useCallback(
    async (text: string, providerOverride?: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;
      setSending(true);
      setLastError(null);
      setMessages((prev) => [...prev.slice(-(MAX_CLIENT_MESSAGES - 1)),
        {
          id: `local-${Date.now()}`,
          role: "user",
          content: trimmed,
          created_at: new Date().toISOString(),
        },
      ]);
      try {
        // Özellik 18: /compare komutu → karşılaştırma sinyali; aksi halde tercih.
        const isCompare = trimmed.toLowerCase().startsWith("/compare");
        const message = isCompare ? trimmed.slice(8).trim() || trimmed : trimmed;
        const provider = providerOverride ?? providerPref;
        const r = await api.sendChat(message, provider);
        setMessages((prev) => [...prev.slice(-(MAX_CLIENT_MESSAGES - 1)),
          {
            id: `reply-${Date.now()}`,
            role: "assistant",
            content: r.reply,
            created_at: new Date().toISOString(),
            provider: r.provider_used ?? r.provider,
            fallback: r.fallback_occurred,
          },
        ]);
      } catch (e) {
        setLastError(e instanceof Error ? e.message : "Bilinmeyen hata");
      } finally {
        setSending(false);
      }
    },
    [sending, providerPref]
  );

  const clearConversation = useCallback(async () => {
    setMessages([]);
    if (isGuestMode()) return; // misafirde kalıcı kayıt yok
    try {
      await api.clearConversation();
    } catch {
      /* offline — backend gelince tekrar denenebilir */
    }
  }, []);

  const reloadConversation = useCallback(async () => {
    // Prompt 2: misafir geçmişi ÇAĞIRMAZ; sohbet yalnızca bellekte tutulur
    // ve sayfa açılışında boş başlar (yenileme = sıfırlama).
    if (isGuestMode()) return;
    try {
      const r = await api.conversation();
      setMessages(r.messages.slice(-MAX_CLIENT_MESSAGES));
    } catch {
      /* offline */
    }
  }, []);

  // ── Ayarlar ──
  const saveSettings = useCallback(
    async (patch: {
      background_color?: AppSettings["background_color"];
      city?: string;
      language?: Language;
      chat_panel_position?: AppSettings["chat_panel_position"];
      conversation_mode?: AppSettings["conversation_mode"];
      custom_palette?: Record<string, string>;
      /** Madde 14: TTS tercihleri modal'dan gelir. */
      tts_voice?: string;
      tts_rate?: number;
    }) => {
      const updated = await api.updateSettings(patch);
      setSettings(updated);
      return updated;
    },
    []
  );

  /** Madde 3: dili değiştirir; online ise DB'de kullanıcıya özel kaydeder. */
  const changeLanguage = useCallback(
    async (next: Language) => {
      persistLang(next);
      setLangState(next);
      try {
        const updated = await api.updateSettings({ language: next });
        setSettings(updated);
      } catch {
        /* offline — localStorage tercihi yeterli; DB sonra senkronlanır */
      }
    },
    []
  );

  // ── Kamera ──
  const refreshCamera = useCallback(async () => {
    try {
      setCamera(await api.cameraStatus());
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    refreshCamera();
  }, [refreshCamera]);

  const toggleCamera = useCallback(async () => {
    setCameraBusy(true);
    setCameraError(null);
    try {
      setCamera(
        camera.status === "live" ? await api.cameraClose() : await api.cameraOpen()
      );
    } catch (e) {
      setCameraError(e instanceof Error ? e.message : "Kamera hatası");
    } finally {
      setCameraBusy(false);
    }
  }, [camera.status]);

  const capturePhoto = useCallback(async () => {
    setCameraBusy(true);
    setCameraError(null);
    try {
      const r = await api.cameraCapture();
      setPhoto(r.image);
    } catch (e) {
      setCameraError(e instanceof Error ? e.message : "Çekim hatası");
    } finally {
      setCameraBusy(false);
    }
  }, []);

  // ── Sesli mod (Faz 3) ──
  const refreshVoice = useCallback(async () => {
    try {
      setVoice(await api.voiceStatus());
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    refreshVoice();
  }, [refreshVoice]);

  const toggleMic = useCallback(async () => {
    setVoiceError(null);
    try {
      setVoice(voice && voice.mic !== "off" ? await api.voiceStop() : await api.voiceStart());
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Mikrofon hatası");
    }
  }, [voice]);

  const startVoiceMode = useCallback(async (reason?: string) => {
    setVoiceError(null);
    try {
      setVoice(await api.voiceModeOn(reason ?? "ui_button"));
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Sesli mod başlatılamadı");
    }
  }, []);

  const exitVoiceMode = useCallback(async () => {
    setVoiceError(null);
    try {
      setVoice(await api.voiceModeOff());
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Sesli moddan çıkılamadı");
    }
  }, []);

  const say = useCallback(async (text: string) => {
    try {
      await api.voiceSay(text);
    } catch {
      /* offline */
    }
  }, []);

  const updateVoiceSettings = useCallback(
    async (patch: Parameters<typeof api.voiceUpdateSettings>[0]) => {
      const updated = await api.voiceUpdateSettings(patch);
      setVoice(updated);
      return updated;
    },
    []
  );

  // ── Hatırlatıcılar (Faz 4) ──
  const [reminders, setReminders] = useState<Reminder[]>([]);

  const refreshReminders = useCallback(async () => {
    try {
      const r = await api.reminders(false);
      setReminders(r.reminders);
    } catch {
      /* offline — mevcut liste korunur */
    }
  }, []);

  useEffect(() => {
    refreshReminders();
    remindersRefreshRef.current = refreshReminders;
  }, [refreshReminders]);

  const createReminder = useCallback(
    async (title: string, due_at: string) => {
      const r = await api.createReminder(title, due_at);
      await refreshReminders();
      return r.reminder;
    },
    [refreshReminders]
  );

  const deleteReminder = useCallback(
    async (id: number) => {
      await api.deleteReminder(id);
      await refreshReminders();
    },
    [refreshReminders]
  );

  const ackReminder = useCallback(
    async (id: number) => {
      await api.ackReminder(id);
      await refreshReminders();
    },
    [refreshReminders]
  );

  const snoozeReminder = useCallback(
    async (id: number, minutes: number) => {
      await api.snoozeReminder(id, minutes);
      await refreshReminders();
    },
    [refreshReminders]
  );

  const ackAllAlarms = useCallback(async () => {
    await api.ackAllAlarms();
    await refreshReminders();
  }, [refreshReminders]);

  /** Kullanıcı etkileşimi ping'i — çalan alarm susar (koşul 1). */
  const reportActivity = useCallback(async () => {
    try {
      await api.reportActivity();
    } catch {
      /* offline */
    }
  }, []);

  return {
    online,
    stats,
    health,
    integrations,
    messages,
    sending,
    lastError,
    settings,
    weather,
    lang,
    changeLanguage,
    camera,
    photo,
    cameraBusy,
    cameraError,
    voice,
    voiceError,
    setPhoto,
    refreshWeather,
    sendMessage,
    clearConversation,
    reloadConversation,
    saveSettings,
    toggleCamera,
    capturePhoto,
    refreshCamera,
    toggleMic,
    startVoiceMode,
    exitVoiceMode,
    refreshVoice,
    say,
    updateVoiceSettings,
    reminders,
    refreshReminders,
    createReminder,
    deleteReminder,
    ackReminder,
    snoozeReminder,
    ackAllAlarms,
    reportActivity,
    // ── v11 (mega prompt) ──
    reconnecting,       // Özellik 16: "Yeniden bağlanıyor..." banner'ı
    screenSuggestion,   // Özellik 7: vision önerisi (toast)
    setScreenSuggestion,
    dailySummary,       // Özellik 11: günlük özet bildirimi
    setDailySummary,
    providerPref,       // Özellik 18: sağlayıcı tercihi
    setProviderPref,
  };
}

export type JarvisState = ReturnType<typeof useJarvis>;
