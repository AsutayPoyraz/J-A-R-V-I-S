/** JARVIS Web UI — Faz 1 yerçekirdeği düzeni.

Masaüstü: sol kartlar | orta logo sahnesi | sağ sohbet paneli.
Mobil: logo + sohbet; sistem kartları açılır çekmecede.
v11 (mega prompt): lazy-loading kartlar (Özellik 16), ATLAS paneli (17),
karşılaştırma (12), ekran/günlük özet toast'ları (7/11), yeniden bağlanma
banner'ı (16), mobil alt navigasyon (16).
*/
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { useJarvis } from "./hooks/useJarvis";
import { useClientStats } from "./hooks/useClientStats";
import { useLocation } from "./hooks/useLocation";
import { api } from "./api/client";
import TopBar from "./components/TopBar";
import GuestBanner from "./components/GuestBanner";
import SystemStatsCard from "./components/SystemStatsCard";
import WeatherCard from "./components/WeatherCard";
import ReminderCard from "./components/ReminderCard";
import UptimeCard from "./components/UptimeCard";
import CenterStage from "./components/CenterStage";
import ConversationPanel from "./components/ConversationPanel";
import SettingsModal from "./components/SettingsModal";
import GuestLocked from "./components/GuestLocked";
import LoginGate, { isGuestMode } from "./components/LoginGate";
import AtlasPanel from "./components/AtlasPanel";
import CompareMode from "./components/CompareMode";
import { useSession } from "./hooks/useSession";
import type { LogoState } from "./types";

// Özellik 16.1: ağır kartlar React.lazy ile ayrı chunk'lara bölünür.
const CameraCard = lazy(() => import("./components/CameraCard"));
const AgentCard = lazy(() => import("./components/AgentCard"));
const SocialCard = lazy(() => import("./components/SocialCard"));
const PrivacyWellnessCard = lazy(() => import("./components/PrivacyWellnessCard"));
const FileTransferCard = lazy(() => import("./components/FileTransferCard"));
const SmartHomeCard = lazy(() => import("./components/SmartHomeCard"));
const PairCard = lazy(() => import("./components/PairCard"));
const TaskManagerCard = lazy(() => import("./components/TaskManagerCard"));
const HabitsCard = lazy(() => import("./components/HabitsCard"));
const KnowledgeCard = lazy(() => import("./components/KnowledgeCard"));
const MacrosCard = lazy(() => import("./components/MacrosCard"));

function CardSkeleton({ height = 120 }: { height?: number }) {
  return (
    <div
      className="animate-pulse rounded-2xl border"
      style={{ height, borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
    />
  );
}

/** Özellik 7/11: sağ alt köşede 5 sn'lik non-intrusive toast. */
function Toast({ text, onClose }: { text: string; onClose: () => void }) {
  useEffect(() => {
    const id = setTimeout(onClose, 5000);
    return () => clearTimeout(id);
  }, [onClose]);
  return (
    <button
      type="button"
      onClick={onClose}
      className="fixed bottom-20 right-4 z-50 max-w-xs rounded-xl border px-3.5 py-2.5 text-left text-[12px] leading-relaxed text-slate-100 shadow-2xl lg:bottom-6"
      style={{
        borderColor: "rgb(var(--accent-rgb) / 0.5)",
        background: "rgb(12 14 22 / 0.97)",
        boxShadow: "0 0 24px rgb(var(--accent-rgb) / 0.25)",
      }}
    >
      <span className="mb-0.5 block text-[9px] uppercase tracking-widest text-slate-500">
        JARVIS öneri
      </span>
      {text}
    </button>
  );
}

export default function App() {
  const jarvis = useJarvis();
  const session = useSession();
  const chatInputRef = useRef<HTMLInputElement>(null);
  // Özellik 2: "Bu Cihaz" istemci istatistikleri (3 sn'de bir).
  const clientStats = useClientStats();
  // Özellik 19: otomatik konum → şehir ayarı + toast.
  const [cityToast, setCityToast] = useState<string | null>(null);
  useLocation((city) => setCityToast(`Konumunuz ${city} olarak ayarlandı ✓`));
  // Özellik 17: ATLAS paneli (sağdan drawer, sohbet split view'a girer).
  const [atlasOpen, setAtlasOpen] = useState(false);
  // Özellik 12: karşılaştırma modalı (/compare komutu veya butonla).
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareMessage, setCompareMessage] = useState("");
  // PWA sw.js güncelleme bildirimi (Özellik 16.10 — otomatik yenileme YOK).
  const [swUpdateReady, setSwUpdateReady] = useState(false);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [speakingUntil, setSpeakingUntil] = useState(0);

  // Kullanıcı girişli mi (karşılaştırma modu kısıtı — Özellik 12)?
  const member = !isGuestMode() && !!session;

  // Yanıt gelince kısa "Konuşuyor..." vurgusu (yalnızca logoda görünür)
  const messageCount = jarvis.messages.length;
  const lastIsAssistant = jarvis.messages[messageCount - 1]?.role === "assistant";
  useEffect(() => {
    if (!jarvis.sending && lastIsAssistant && messageCount > 0) {
      setSpeakingUntil(Date.now() + 1600);
    }
  }, [messageCount, jarvis.sending, lastIsAssistant]);

  useEffect(() => {
    if (!speakingUntil) return;
    const id = setInterval(() => {
      if (Date.now() >= speakingUntil) setSpeakingUntil(0);
    }, 200);
    return () => clearInterval(id);
  }, [speakingUntil]);

  // Logo durumu: offline > thinking > speaking > idle
  const phase: LogoState = !jarvis.online
    ? "offline"
    : jarvis.sending
      ? "thinking"
      : speakingUntil > 0
        ? "speaking"
        : "idle";

  // Sesli oturum aktifken masaüstünde yalnızca orta alan görünür (gereklim 4).
  const voiceSessionActive = !!jarvis.voice?.session;
  // Madde 32: sohbet paneli konumu (DB'de kullanıcıya özel saklanır).
  const chatPosition = jarvis.settings?.chat_panel_position ?? "right";

  const handleExport = async (format: "txt" | "md") => {
    const blob = await api.exportConversation(format);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `jarvis-conversation.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Kullanıcı etkileşimi: çalan alarmları susar (koşul 1 — active UI).
  useEffect(() => {
    const ping = () => void jarvis.reportActivity();
    window.addEventListener("pointerdown", ping);
    window.addEventListener("keydown", ping);
    return () => {
      window.removeEventListener("pointerdown", ping);
      window.removeEventListener("keydown", ping);
    };
  }, [jarvis.reportActivity]);

  // PWA service worker güncellemesi algılanınca banner göster (F16.10).
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        reg.addEventListener("updatefound", () => {
          const newWorker = reg.installing;
          newWorker?.addEventListener("statechange", () => {
            if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
              setSwUpdateReady(true);
            }
          });
        });
      })
      .catch(() => undefined);
  }, []);

  const handleSend = (text: string) => {
    // Özellik 12: "/compare" komutu → karşılaştırma modalı; "/atlas" → ATLAS.
    const lowered = text.trim().toLowerCase();
    if (lowered.startsWith("/compare")) {
      setCompareMessage(text.slice(8).trim());
      setCompareOpen(true);
      return;
    }
    if (lowered.startsWith("/atlas")) {
      setAtlasOpen(true);
      return;
    }
    void jarvis.sendMessage(text);
  };

  const firingReminders = jarvis.reminders.filter((r) => r.status === "firing");

  const cards = (
    <>
      <Suspense fallback={<CardSkeleton />}>
        <SystemStatsCard stats={jarvis.stats} online={jarvis.online} clientStats={clientStats} />
        <TaskManagerCard />
        <HabitsCard />
      </Suspense>
      <WeatherCard
        weather={jarvis.weather}
        online={jarvis.online}
        citySetting={jarvis.settings?.city}
        onRefresh={() => jarvis.refreshWeather(true)}
      />
      <ReminderCard online={jarvis.online} />
      <Suspense fallback={<CardSkeleton />}>
        <GuestLocked title="Productivity" allowed={session.can("history")}>
          <AgentCard />
        </GuestLocked>
        <GuestLocked title="Social" allowed={session.can("history")}>
          <SocialCard />
          <PrivacyWellnessCard />
        </GuestLocked>
        <GuestLocked title="Camera" allowed={session.can("device_control")}>
          <CameraCard
            camera={jarvis.camera}
            photo={jarvis.photo}
            busy={jarvis.cameraBusy}
            error={jarvis.cameraError}
            online={jarvis.online}
            onToggle={jarvis.toggleCamera}
            onCapture={jarvis.capturePhoto}
            onClosePhoto={() => jarvis.setPhoto(null)}
          />
        </GuestLocked>
        <GuestLocked title="File Transfer" allowed={session.can("files")}>
          <FileTransferCard />
        </GuestLocked>
        <PairCard online={jarvis.online} />
        <GuestLocked title="Smart Home" allowed={session.can("device_control")}>
          <SmartHomeCard />
        </GuestLocked>
      </Suspense>
      <Suspense fallback={<CardSkeleton />}>
        <KnowledgeCard />
        <MacrosCard />
      </Suspense>
      <UptimeCard stats={jarvis.stats} online={jarvis.online} />
    </>
  );

  return (
    <LoginGate>
    <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden overflow-y-auto">
      <TopBar
        online={jarvis.online}
        weather={jarvis.weather}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenDrawer={() => setDrawerOpen(true)}
      />
      <GuestBanner />

      {/* Özellik 16.4: "Yeniden bağlanıyor..." banner'ı */}
      {jarvis.reconnecting && !jarvis.online && (
        <div className="sticky top-0 z-40 border-b border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-center text-[11px] font-medium text-amber-200">
          ⟳ Yeniden bağlanıyor... (arka planda otomatik deneniyor)
        </div>
      )}

      {/* Özellik 16.10: PWA yeni sürüm banner'ı (otomatik yenileme yok) */}
      {swUpdateReady && (
        <div className="sticky top-0 z-40 border-b border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-center text-[11px] text-cyan-200">
          🎉 Yeni sürüm var —{" "}
          <button
            type="button"
            className="font-bold underline"
            onClick={() => window.location.reload()}
          >
            Yenile
          </button>
        </div>
      )}

      {/* Çalan alarm banner'ı (Faz 4): user hareketi susar, buton ack yapar */}
      {firingReminders.length > 0 && (
        <div className="sticky top-0 z-40 flex items-center justify-between border-b border-red-500/30 bg-red-600/25 px-3 py-2">
          <div className="min-w-0 flex-1 truncate text-[12px] font-semibold text-red-100">
            🔔 {firingReminders[0].title}
            {firingReminders.length > 1 && ` (+${firingReminders.length - 1} alarm daha)`}
          </div>
          <button
            onClick={() => void jarvis.ackAllAlarms()}
            className="shrink-0 rounded-lg border border-red-300/30 bg-red-500/25 px-3 py-1 text-xs font-bold text-red-50 hover:bg-red-500/40"
          >
            Sustur
          </button>
        </div>
      )}

      {/* Mobil çekmece (sistem kartları) */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setDrawerOpen(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[70vh] space-y-2.5 overflow-y-auto rounded-t-2xl border-t p-3 pb-20"
            style={{ borderColor: "var(--border-strong)", background: "rgb(6 8 14 / 0.97)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-white/20" />
            {cards}
          </div>
        </div>
      )}

      {/* Ana ızgara — sesli oturumda masaüstünde yalnızca orta alan.
          Madde 32: center konumunda sohbet paneli orta kolona taşınır. */}
      <main
        className={
          voiceSessionActive
            ? "relative z-10 grid min-h-0 flex-1 place-items-center p-3"
            : chatPosition === "center"
              ? "relative z-10 grid flex-1 items-start gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)]"
              : "relative z-10 grid flex-1 items-start gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)_340px]"
        }
      >
        {/* Sol kolon — masaüstü, sesli oturumda gizli */}
        {!voiceSessionActive && (
          <div className="hidden space-y-2.5 pb-16 pr-0.5 lg:block">{cards}</div>
        )}

        {/* Orta alan */}
        <div
          className={
            chatPosition === "center" && !voiceSessionActive
              ? "flex min-w-0 flex-col items-center gap-3"
              : ""
          }
        >
          <CenterStage
            phase={phase}
            cameraLive={jarvis.camera.status === "live"}
            voice={jarvis.voice}
            voiceError={jarvis.voiceError}
            onCamera={() => {
              if (window.innerWidth < 1024) setDrawerOpen(true);
              else jarvis.toggleCamera();
            }}
            onMic={jarvis.toggleMic}
            onKeyboard={() => chatInputRef.current?.focus()}
            onExitVoiceMode={jarvis.exitVoiceMode}
          />
          {chatPosition === "center" && !voiceSessionActive && (
            <div className="w-full max-w-2xl">
              <ConversationPanel
                ref={chatInputRef}
                messages={jarvis.messages}
                sending={jarvis.sending}
                online={jarvis.online}
                lastError={jarvis.lastError}
                onSend={handleSend}
                providerPref={jarvis.providerPref}
                onProviderChange={jarvis.setProviderPref}
                onClear={jarvis.clearConversation}
                onExport={handleExport}
              />
            </div>
          )}
        </div>

        {/* Sağ panel — sohbet (right konumu), sesli oturumda gizli */}
        {!voiceSessionActive && chatPosition !== "center" && (
          <div className="min-w-0 pb-16 lg:block">
            <ConversationPanel
              ref={chatInputRef}
              messages={jarvis.messages}
              sending={jarvis.sending}
              online={jarvis.online}
              lastError={jarvis.lastError}
              onSend={handleSend}
              providerPref={jarvis.providerPref}
              onProviderChange={jarvis.setProviderPref}
              onClear={jarvis.clearConversation}
              onExport={handleExport}
            />
          </div>
        )}
      </main>

      <SettingsModal
        open={settingsOpen}
        settings={jarvis.settings}
        online={jarvis.online}
        health={jarvis.health}
        integrations={jarvis.integrations}
        voice={jarvis.voice}
        onClose={() => setSettingsOpen(false)}
        onSave={jarvis.saveSettings}
        onSaveVoice={jarvis.updateVoiceSettings}
        onChangeLanguage={jarvis.changeLanguage}
      />

      {/* ── v11 panelleri ve bildirimleri ── */}
      <AtlasPanel open={atlasOpen} onClose={() => setAtlasOpen(false)} />
      <CompareMode
        open={compareOpen}
        initialMessage={compareMessage}
        canUse={member}
        onClose={() => setCompareOpen(false)}
        onPick={(response, provider) => {
          // Kullanıcı beğendiği yanıtı ana sohbete alır (Özellik 12.3).
          void jarvis.sendMessage(response, provider);
        }}
      />
      {jarvis.screenSuggestion && (
        <Toast text={jarvis.screenSuggestion} onClose={() => jarvis.setScreenSuggestion(null)} />
      )}
      {jarvis.dailySummary && (
        <Toast text={jarvis.dailySummary} onClose={() => jarvis.setDailySummary(null)} />
      )}
      {cityToast && <Toast text={cityToast} onClose={() => setCityToast(null)} />}

      {/* Özellik 16.8: mobil alt tab navigasyonu (<768px) */}
      <MobileNav
        onHome={() => setDrawerOpen(false)}
        onChat={() => {
          setDrawerOpen(false);
          chatInputRef.current?.focus();
        }}
        onCards={() => setDrawerOpen(true)}
        onSettings={() => setSettingsOpen(true)}
      />
    </div>
    </LoginGate>
  );
}

/** Özellik 16.8: mobil (<768px) alt tab bar — 44px+ dokunma hedefleri (HIG). */
function MobileNav({ onHome, onChat, onCards, onSettings }: {
  onHome: () => void;
  onChat: () => void;
  onCards: () => void;
  onSettings: () => void;
}) {
  const items: { icon: string; label: string; action: () => void }[] = [
    { icon: "🏠", label: "Ana Sayfa", action: onHome },
    { icon: "💬", label: "Sohbet", action: onChat },
    { icon: "🗂️", label: "Kartlar", action: onCards },
    { icon: "⚙️", label: "Ayarlar", action: onSettings },
  ];
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 grid grid-cols-4 border-t lg:hidden"
      style={{ borderColor: "var(--border)", background: "rgb(6 8 14 / 0.97)" }}
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          onClick={item.action}
          className="flex min-h-[52px] flex-col items-center justify-center gap-0.5 text-slate-300 active:bg-white/5"
        >
          <span className="text-base leading-none">{item.icon}</span>
          <span className="text-[9px]">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
