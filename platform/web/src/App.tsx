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
import PairCard from "./components/PairCard";
import FileTransferCard from "./components/FileTransferCard";
import CenterStage from "./components/CenterStage";
import ConversationPanel from "./components/ConversationPanel";
import SettingsModal from "./components/SettingsModal";
import SmartHomeCard from "./components/SmartHomeCard";
import GuestLocked from "./components/GuestLocked";
import LoginGate from "./components/LoginGate";
import { useSession } from "./hooks/useSession";
import type { LogoState } from "./types";

export default function App() {
  const jarvis = useJarvis();
  const session = useSession();
  const chatInputRef = useRef<HTMLInputElement>(null);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [speakingUntil, setSpeakingUntil] = useState(0);

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

  const firingReminders = jarvis.reminders.filter((r) => r.status === "firing");

  const cards = (
    <>
      <SystemStatsCard stats={jarvis.stats} online={jarvis.online} />
      <WeatherCard
        weather={jarvis.weather}
        online={jarvis.online}
        citySetting={jarvis.settings?.city}
        onRefresh={() => jarvis.refreshWeather(true)}
      />
      <ReminderCard online={jarvis.online} />
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

      {/* Çalan alarm banner'ı (Faz 4): user hareketi susar, buton ack yapar */}
      {firingReminders.length > 0 && (
        <div
          className="relative z-20 mx-3 mt-2 flex animate-pulse items-center justify-between gap-3 rounded-xl border px-4 py-2.5"
          style={{ borderColor: "var(--border-strong)", background: "rgb(70 18 18 / 0.88)" }}
        >
          <div className="truncate text-sm font-semibold text-red-100">
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
            className="absolute bottom-0 left-0 right-0 max-h-[70vh] space-y-2.5 overflow-y-auto rounded-t-2xl border-t p-3 pb-6"
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
          <div className="hidden space-y-2.5 pr-0.5 lg:block">{cards}</div>
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
                onSend={jarvis.sendMessage}
                onClear={jarvis.clearConversation}
                onExport={handleExport}
              />
            </div>
          )}
        </div>

        {/* Sağ panel — sohbet (right konumu), sesli oturumda gizli */}
        {!voiceSessionActive && chatPosition !== "center" && (
          <div className="min-w-0 lg:block">
            <ConversationPanel
              ref={chatInputRef}
              messages={jarvis.messages}
              sending={jarvis.sending}
              online={jarvis.online}
              lastError={jarvis.lastError}
              onSend={jarvis.sendMessage}
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
    </div>
    </LoginGate>
  );
}
