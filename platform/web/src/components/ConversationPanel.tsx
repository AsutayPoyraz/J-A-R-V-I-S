/** Sağ panel "Conversation": Clear, Extract (txt/md), balonlar, yazı alanı.
    Madde 8: scroll performansı — rAF ile tek autoscroll, passive listener. */
import { forwardRef, useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";
import { t } from "../i18n";

interface Props {
  messages: ChatMessage[];
  sending: boolean;
  online: boolean;
  lastError: string | null;
  onSend: (text: string) => void;
  onClear: () => void;
  onExport: (format: "txt" | "md") => void;
  /** Özellik 18: sağlayıcı seçici (varsayılan "Otomatik" → Gemini'den başlar). */
  providerPref?: string;
  onProviderChange?: (provider: string) => void;
}

function timeOf(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/** Sağlayıcı etiketi (Özellik 18.5): "Yanıtlayan: Gemini" / fallback notu. */
const PROVIDER_NAMES: Record<string, string> = {
  gemini: "Gemini",
  deepseek: "DeepSeek R1",
  groq: "Groq",
  llama: "Llama 3.3 70B",
  openai: "OpenAI",
  anthropic: "Claude",
  mock: "Demo",
};

function Bubble({ m }: { m: ChatMessage }) {
  if (m.role === "system") {
    return (
      <div className="mx-auto max-w-[92%] text-center">
        <p
          className="rounded-lg border px-3 py-1.5 text-[11px] leading-relaxed"
          style={{
            borderColor: "rgb(239 68 68 / 0.35)",
            color: "rgb(252 165 165)",
            background: "rgb(239 68 68 / 0.06)",
          }}
        >
          {m.content}
        </p>
      </div>
    );
  }
  return (
    <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className="max-w-[85%] rounded-2xl border px-3 py-2"
        style={
          m.role === "user"
            ? { borderColor: "var(--border-strong)", background: "rgb(var(--accent-rgb) / 0.12)" }
            : { borderColor: "var(--border)", background: "rgb(255 255 255 / 0.03)" }
        }
      >
        <p className="whitespace-pre-wrap break-words text-[13px] leading-snug text-slate-100">
          {m.content}
        </p>
        <p className="mt-1 text-right text-[9px] tabular-nums text-slate-500">
          {m.provider && m.role === "assistant" && (
            <span className="mr-1.5 normal-case tracking-normal">
              Yanıtlayan: {PROVIDER_NAMES[m.provider] ?? m.provider}
              {m.fallback ? " (tercihiniz müsait değildi)" : ""}
            </span>
          )}
          {timeOf(m.created_at)}
        </p>
      </div>
    </div>
  );
}

const ConversationPanel = forwardRef<HTMLInputElement, Props>(
  ({ messages, sending, online, lastError, onSend, onClear, onExport, providerPref = "", onProviderChange }, inputRef) => {
    const [draft, setDraft] = useState("");
    const [confirmingClear, setConfirmingClear] = useState(false);
    const [exportOpen, setExportOpen] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const rafRef = useRef<number | null>(null);

    // Madde 8: her mesaj değişiminde en fazla bir requestAnimationFrame —
    // hızlı ardışık mesajlarda scroll storm olmaz; smooth yerine "auto" ile
    // ana thread kilidi engellenir (uzun sohbetlerde takılma kaynağıydı).
    useEffect(() => {
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(() => {
            rafRef.current = null;
            bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
        });
        return () => {
            if (rafRef.current !== null) {
                cancelAnimationFrame(rafRef.current);
                rafRef.current = null;
            }
        };
    }, [messages.length, sending]);

    const submit = () => {
      if (!draft.trim() || sending || !online) return;
      onSend(draft);
      setDraft("");
    };

    const handleClear = () => {
      if (!confirmingClear) {
        setConfirmingClear(true);
        setTimeout(() => setConfirmingClear(false), 2500);
        return;
      }
      setConfirmingClear(false);
      onClear();
    };

    return (
      <aside className="panel relative z-10 flex min-h-0 flex-col overflow-hidden">
        <header
          className="flex items-center justify-between border-b px-3 py-2"
          style={{ borderColor: "var(--border)" }}
        >
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">
            {t("chat.title")}
          </h2>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleClear}
              disabled={!online || messages.length === 0}
              className="btn-accent rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wider"
            >
              {confirmingClear ? t("chat.confirm_clear") : t("chat.clear")}
            </button>
            <div className="relative">
              <button
                type="button"
                onClick={() => setExportOpen((o) => !o)}
                disabled={messages.length === 0}
                className="btn-accent rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wider"
                title={t("chat.export")}
              >
                Extract ▾
              </button>
              {exportOpen && (
                <div
                  className="absolute right-0 top-8 z-20 flex overflow-hidden rounded-md border"
                  style={{ borderColor: "var(--border-strong)", background: "rgb(10 12 20 / 0.97)" }}
                >
                  <button
                    type="button"
                    className="px-3 py-1.5 text-[11px] hover:bg-white/5"
                    style={{ color: "rgb(var(--accent-soft-rgb))" }}
                    onClick={() => { onExport("txt"); setExportOpen(false); }}
                  >
                    .txt
                  </button>
                  <button
                    type="button"
                    className="border-l px-3 py-1.5 text-[11px] hover:bg-white/5"
                    style={{ borderLeftColor: "var(--border)", color: "rgb(var(--accent-soft-rgb))" }}
                    onClick={() => { onExport("md"); setExportOpen(false); }}
                  >
                    .md
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <div ref={scrollRef} className="chat-scroll min-h-0 flex-1 space-y-2.5 px-3 py-3">
          {messages.length === 0 && (
            <p className="mt-6 text-center text-xs text-slate-500">
              {t("chat.empty")}
            </p>
          )}
          {messages.map((m) => (
            <Bubble key={m.id} m={m} />
          ))}
          {sending && (
            <div className="flex justify-start">
              <div
                className="flex items-center gap-1 rounded-2xl border px-3.5 py-3"
                style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.03)" }}
              >
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="typing-dot h-1.5 w-1.5 rounded-full"
                    style={{ background: "rgb(var(--accent-soft-rgb))" }}
                  />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <footer className="border-t p-2.5" style={{ borderColor: "var(--border)" }}>
          {lastError && <p className="mb-1.5 text-[10px] text-red-400">{lastError}</p>}
          <div className="flex items-center gap-1.5">
            {/* Özellik 18.4: sağlayıcı seçici (Otomatik = gemini → fallback zinciri) */}
            <select
              value={providerPref}
              onChange={(e) => onProviderChange?.(e.target.value)}
              className="h-9 shrink-0 rounded-lg border bg-black/30 px-1 text-[10px] text-slate-300 outline-none"
              style={{ borderColor: "var(--border)" }}
              title="LLM sağlayıcı tercihi (hata olursa otomatik sıradakine geçilir)"
            >
              <option value="">🤖 Otomatik</option>
              <option value="gemini">✦ Gemini</option>
              <option value="deepseek">⬢ DeepSeek</option>
              <option value="groq">⚡ Groq</option>
              <option value="llama">🦙 Llama 3.3</option>
            </select>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              disabled={!online}
              placeholder={online ? t("chat.placeholder") : t("chat.placeholder_offline")}
              className="min-w-0 flex-1 rounded-lg border bg-black/30 px-3 py-2 text-[13px] outline-none placeholder:text-slate-500 disabled:opacity-50"
              style={{ borderColor: "var(--border)" }}
            />
            <button
              type="button"
              onClick={submit}
              disabled={!online || !draft.trim() || sending}
              className="btn-accent grid h-9 min-h-[44px] w-9 shrink-0 place-items-center rounded-lg"
              title={t("chat.send")}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <path d="M22 2L11 13 M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </footer>
      </aside>
    );
  }
);

ConversationPanel.displayName = "ConversationPanel";
export default ConversationPanel;

