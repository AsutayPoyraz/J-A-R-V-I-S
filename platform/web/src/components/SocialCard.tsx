/** Bölüm F kartı (madde 19/20/21/24): oyunlaştırma, makrolar, sesli notlar,
 * paylaşımlı oturumlar ve kullanım analitiği. Tüm metinler i18n'den gelir. */
import { useCallback, useEffect, useRef, useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import { t } from "../i18n";
import type {
  AnalyticsSummary,
  GamifyStatus,
  MacroItem,
  HistoryResult,
  SharedMessageItem,
  SharedSessionInfo,
  VoiceNoteItem,
} from "../types";

type Tab = "xp" | "macros" | "voice" | "share" | "insights";

const TABS: { value: Tab; labelKey: string }[] = [
  { value: "xp", labelKey: "social.tab_xp" },
  { value: "macros", labelKey: "social.tab_macros" },
  { value: "voice", labelKey: "social.tab_voice" },
  { value: "share", labelKey: "social.tab_share" },
  { value: "insights", labelKey: "social.tab_insights" },
];

const input =
  "w-full rounded-lg border bg-black/30 px-2 py-1.5 text-xs outline-none placeholder:text-slate-500";
const inputStyle = { borderColor: "var(--border)" };
const btn =
  "rounded-lg border px-2.5 py-1 text-[10px] font-semibold disabled:opacity-50";

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function SocialCard() {
  const [tab, setTab] = useState<Tab>("xp");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gamify, setGamify] = useState<GamifyStatus | null>(null);
  const [macros, setMacros] = useState<MacroItem[]>([]);
  const [macroName, setMacroName] = useState("");
  const [notes, setNotes] = useState<VoiceNoteItem[]>([]);
  const [voiceText, setVoiceText] = useState("");
  const [voiceQuery, setVoiceQuery] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [shareCode, setShareCode] = useState("");
  const [session, setSession] = useState<SharedSessionInfo | null>(null);
  const [messages, setMessages] = useState<SharedMessageItem[]>([]);
  const [draft, setDraft] = useState("");
  const pollRef = useRef<number | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [searchQ, setSearchQ] = useState("");
  const [searchTag, setSearchTag] = useState("");
  const [searchResults, setSearchResults] = useState<HistoryResult[]>([]);

  const load = useCallback(async () => {
    try {
      const [g, m, n] = await Promise.all([
        api.gamify(),
        api.macros(),
        api.voiceNotes(),
      ]);
      setGamify(g);
      setMacros(m.macros);
      setNotes(n.notes);
      setError(null);
    } catch {
      setError(t("agent.screen_failed"));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Paylaşılan oturum: 3 sn'de bir uzun yoklama (WS olmayan istemci için de çalışır)
  useEffect(() => {
    if (!shareCode) return;
    const poll = async () => {
      try {
        const r = await api.sharedMessages(shareCode);
        setMessages(r.messages);
      } catch {
        /* üye değil ya da oturum kapandı — sessizce bekle */
      }
    };
    void poll();
    pollRef.current = window.setInterval(poll, 3000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [shareCode]);

  const act = async (fn: () => Promise<unknown>, reload = true) => {
    setBusy(true);
    try {
      await fn();
      if (reload) await load();
      setError(null);
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const loadAnalytics = async () => {
    try {
      setAnalytics(await api.analytics(14));
      setError(null);
    } catch {
      setError(t("common.error"));
    }
  };

  const runSearch = async () => {
    try {
      const r = await api.historySearch(searchQ, searchTag);
      setSearchResults(r.results);
      setError(null);
    } catch {
      setError(t("common.error"));
    }
  };

  const joinSession = async () => {
    const code = shareCode.trim().toUpperCase();
    if (!code) return;
    setBusy(true);
    try {
      if (displayName.trim()) {
        await api.joinSharedSession(code, displayName.trim());
      }
      setSession(await api.sharedSession(code));
      setShareCode(code);
      setError(null);
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const createSession = async () => {
    setBusy(true);
    try {
      const r = await api.createSharedSession("JARVIS");
      setShareCode(r.code);
      setSession(await api.sharedSession(r.code));
      setError(null);
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const sendMessage = async () => {
    const text = draft.trim();
    if (!text || !shareCode) return;
    setDraft("");
    await act(
      () => api.postSharedMessage(shareCode, text, displayName || "guest"),
      false
    );
  };

  const importBackup = async (file: File) => {
    try {
      const data = JSON.parse(await file.text());
      await api.backupImport(data);
      setError(null);
    } catch {
      setError(t("social.import_failed"));
    }
  };

  const maxDay = analytics
    ? Math.max(1, ...analytics.days.map((d) => Object.entries(d).filter(([k]) => k !== "date").reduce((s, [, v]) => s + Number(v), 0)))
    : 1;

  return (
    <Card title={t("social.title")}>
      <div className="mb-2 flex flex-wrap gap-1">
        {TABS.map((x) => (
          <button
            key={x.value}
            type="button"
            onClick={() => {
              setTab(x.value);
              if (x.value === "insights" && !analytics) void loadAnalytics();
            }}
            className={btn + " " + (tab === x.value ? "bg-white/10 text-slate-100" : "text-slate-400")}
            style={inputStyle}
          >
            {t(x.labelKey)}
          </button>
        ))}
      </div>
      {error && <p className="mb-2 text-[10px] text-red-400">{error}</p>}

      {tab === "xp" && gamify && (
        <div className="space-y-2 text-xs text-slate-300">
          <div className="flex gap-4">
            <span>{t("social.xp_total")}: <b>{gamify.xp_total}</b></span>
            <span>{t("social.tab_xp")}: <b>{gamify.level}</b></span>
            <span>{t("social.streak")}: <b>{gamify.streak_days}</b></span>
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase text-slate-500">{t("social.badges")}</p>
            {gamify.badges && gamify.badges.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {gamify.badges.map((b) => (
                  <span key={b.code} className="rounded border px-1.5 py-0.5 text-[10px]" style={inputStyle}>{b.code}</span>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-slate-500">{t("social.no_badges")}</p>
            )}
          </div>
          <div>
            <p className="mb-1 text-[10px] uppercase text-slate-500">{t("social.leaderboard")}</p>
            {gamify.leaderboard && gamify.leaderboard.length > 0 ? (
              <ol className="space-y-0.5">
                {gamify.leaderboard.map((l, i) => (
                  <li key={i} className="text-[11px]">{i + 1}. {l.name} — {l.xp} XP</li>
                ))}
              </ol>
            ) : (
              <p className="text-[10px] text-slate-500">{t("social.leader_empty")}</p>
            )}
          </div>
        </div>
      )}

      {tab === "macros" && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <input className={input} style={inputStyle} placeholder={t("social.macro_name")}
              value={macroName} onChange={(e) => setMacroName(e.target.value)} />
            <button type="button" className={btn} style={inputStyle}
              disabled={busy || !macroName.trim()}
              onClick={() => { void act(() => api.createMacro(macroName.trim())); setMacroName(""); }}>
              {t("social.macro_add")}
            </button>
          </div>
          {macros.length === 0 && <p className="text-[10px] text-slate-500">{t("social.macro_empty")}</p>}
          {macros.map((m) => (
            <div key={m.id} className="flex items-center justify-between border-b py-1 text-xs last:border-b-0" style={inputStyle}>
              <span className="text-slate-200">{m.name}</span>
              <button type="button" className="text-[10px] text-slate-500 hover:text-red-400"
                onClick={() => void act(() => api.deleteMacro(m.id))}>✕</button>
            </div>
          ))}
        </div>
      )}

      {tab === "voice" && (
        <div className="space-y-2">
          <textarea className={input} style={inputStyle} rows={2}
            placeholder={t("social.voice_placeholder")}
            value={voiceText} onChange={(e) => setVoiceText(e.target.value)} />
          <div className="flex gap-2">
            <input className={input} style={inputStyle} placeholder={t("social.voice_search")}
              value={voiceQuery}
              onChange={(e) => {
                setVoiceQuery(e.target.value);
                void api.voiceNotes(e.target.value).then((r) => setNotes(r.notes)).catch(() => undefined);
              }} />
            <button type="button" className={btn} style={inputStyle}
              disabled={busy || !voiceText.trim()}
              onClick={() => { void act(() => api.createVoiceNote(voiceText.trim())); setVoiceText(""); }}>
              {t("social.voice_add")}
            </button>
          </div>
          {notes.length === 0 && <p className="text-[10px] text-slate-500">{t("social.voice_empty")}</p>}
          {notes.map((n) => (
            <div key={n.id} className="flex items-start justify-between border-b py-1 text-xs last:border-b-0" style={inputStyle}>
              <div className="min-w-0">
                <p className="truncate text-slate-200">{n.text}</p>
                <p className="text-[10px] text-slate-500">{n.created_at}</p>
              </div>
              <button type="button" className="text-[10px] text-slate-500 hover:text-red-400"
                onClick={() => void act(() => api.deleteVoiceNote(n.id))}>✕</button>
            </div>
          ))}
        </div>
      )}

      {tab === "share" && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <input className={input} style={inputStyle} placeholder={t("social.share_name")}
              value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            <input className={input} style={inputStyle} placeholder={t("social.share_code")}
              value={shareCode} onChange={(e) => setShareCode(e.target.value.toUpperCase())} />
          </div>
          <div className="flex gap-2">
            <button type="button" className={btn} style={inputStyle} disabled={busy} onClick={() => void createSession()}>
              {t("social.share_create")}
            </button>
            <button type="button" className={btn} style={inputStyle}
              disabled={busy || !shareCode.trim()} onClick={() => void joinSession()}>
              {t("social.share_join")}
            </button>
            {session && (
              <button type="button" className={btn + " text-red-400"} style={inputStyle} disabled={busy}
                title={t("social.share_host_only")}
                onClick={() => { void act(async () => { await api.deleteSharedSession(shareCode); setSession(null); setMessages([]); }, false); }}>
                ✕
              </button>
            )}
          </div>
          <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border p-2" style={inputStyle}>
            {messages.length === 0 && <p className="text-[10px] text-slate-500">{t("social.share_empty")}</p>}
            {messages.map((msg) => (
              <p key={msg.id} className="text-[11px]">
                <b className="text-slate-300">{msg.display_name}: </b>
                <span className="text-slate-400">{msg.content}</span>
              </p>
            ))}
          </div>
          <div className="flex gap-2">
            <input className={input} style={inputStyle} placeholder={t("social.share_message")}
              value={draft} onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void sendMessage()} />
            <button type="button" className={btn} style={inputStyle}
              disabled={busy || !session || !draft.trim()} onClick={() => void sendMessage()}>
              {t("social.share_send")}
            </button>
          </div>
        </div>
      )}

      {tab === "insights" && (
        <div className="space-y-2">
          <p className="text-[10px] uppercase text-slate-500">{t("social.insights_days")}</p>
          {/* Son 14 gün mini çubuk grafik (madde 24) */}
          <div className="flex h-16 items-end gap-1">
            {analytics && analytics.days.length === 0 && (
              <p className="text-[10px] text-slate-500">{t("social.activity_empty")}</p>
            )}
            {analytics?.days.map((d) => {
              const total = Object.entries(d)
                .filter(([k]) => k !== "date")
                .reduce((s, [, v]) => s + Number(v), 0);
              return (
                <div key={d.date} title={d.date + ": " + total}
                  className="flex-1 rounded-t bg-slate-500/60"
                  style={{ height: Math.max(6, Math.round((total / maxDay) * 100)) + "%" }} />
              );
            })}
          </div>
          {analytics && (
            <p className="text-[10px] text-slate-400">
              {Object.entries(analytics.totals).map(([k, v]) => k + ": " + v).join(" · ")}
            </p>
          )}
          {/* JSON/CSV dışa aktarma + notlar (MD) + yedek al/geri yükle */}
          <div className="flex flex-wrap gap-1">
            <button type="button" className={btn} style={inputStyle}
              onClick={() => void api.exportAnalytics("json").then((b) => download(b, "jarvis-analytics.json"))}>
              {t("social.export_json")}
            </button>
            <button type="button" className={btn} style={inputStyle}
              onClick={() => void api.exportAnalytics("csv").then((b) => download(b, "jarvis-analytics.csv"))}>
              {t("social.export_csv")}
            </button>
            <button type="button" className={btn} style={inputStyle}
              onClick={() => void api.notesExport().then((b) => download(b, "jarvis-notes.md"))}>
              {t("social.notes_export")}
            </button>
            <button type="button" className={btn} style={inputStyle}
              onClick={() => void api.backupExport().then((b) => download(b, "jarvis-backup.zip"))}>
              {t("social.backup_export")}
            </button>
            <label className={btn + " cursor-pointer"} style={inputStyle}>
              {t("social.backup_import")}
              <input type="file" accept="application/json" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void importBackup(f); }} />
            </label>
          </div>
          {/* Etiketli arama geçmişi (madde 24): filtre + tarih aralığı */}
          <div className="flex gap-2">
            <input className={input} style={inputStyle} placeholder={t("social.files_search")}
              value={searchQ} onChange={(e) => setSearchQ(e.target.value)} />
            <input className={input} style={inputStyle} placeholder="#" title={t("social.files_search")}
              value={searchTag} onChange={(e) => setSearchTag(e.target.value)} />
            <button type="button" className={btn} style={inputStyle} disabled={busy}
              onClick={() => void runSearch()}>🔍</button>
          </div>
          <div className="max-h-32 space-y-1 overflow-y-auto">
            {searchResults.length === 0 && <p className="text-[10px] text-slate-500">{t("social.files_empty")}</p>}
            {searchResults.map((r) => (
              <p key={r.source + "-" + r.id} className="truncate text-[11px]">
                <b className="text-slate-300">[{r.source}] </b>
                <span className="text-slate-400">{r.text}{r.tags ? " #" + r.tags : ""}</span>
              </p>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}