/**
 * CompareMode — Özellik 12: çoklu LLM karşılaştırma (yan yana kartlar).
 * Kısıt: yalnızca giriş yapmış kullanıcılar; misafirde gizli.
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { CompareResult } from "../types";

const PROVIDER_LABELS: Record<string, string> = {
  gemini: "✦ Gemini",
  deepseek: "⬢ DeepSeek R1",
  groq: "⚡ Groq",
  llama: "🦙 Llama 3.3 70B",
  openai: "◎ OpenAI",
  anthropic: "✳ Claude",
  mock: "○ Demo",
};

interface Props {
  open: boolean;
  initialMessage: string;
  canUse: boolean;
  onClose: () => void;
  onPick: (response: string, provider: string) => void;
}

export default function CompareMode({ open, initialMessage, canUse, onClose, onPick }: Props) {
  const [message, setMessage] = useState(initialMessage);
  const [results, setResults] = useState<CompareResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) setMessage(initialMessage);
  }, [initialMessage, open]);

  const run = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !canUse) return;
      setBusy(true);
      setError(null);
      setResults([]);
      try {
        const resp = await api.chatCompare(trimmed, []);
        setResults(resp.results);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Karşılaştırma başarısız");
      } finally {
        setBusy(false);
      }
    },
    [canUse]
  );

  // Açılışta hazır mesaj varsa otomatik çalıştır (/compare komutu ile).
  useEffect(() => {
    if (open && initialMessage.trim() && canUse) void run(initialMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-4xl overflow-y-auto rounded-2xl border p-4 shadow-2xl"
        style={{ borderColor: "var(--border-strong)", background: "rgb(10 12 18)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100">
            ⚖️ LLM Karşılaştırma{" "}
            <span className="text-[10px] font-normal text-slate-500">
              (aynı soru → tüm sağlayıcılar)
            </span>
          </h3>
          <button type="button" onClick={onClose} className="min-h-[44px] px-2 text-slate-400 hover:text-white">
            ✕
          </button>
        </div>

        {!canUse ? (
          <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-center text-xs text-amber-200">
            🔒 Karşılaştırma modu yalnızca giriş yapmış kullanıcılara açıktır.
          </p>
        ) : (
          <>
            <form
              className="mb-3 flex gap-1.5"
              onSubmit={(e) => {
                e.preventDefault();
                void run(message);
              }}
            >
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Aynı soruyu tüm sağlayıcılara gönder…"
                className="min-h-[44px] flex-1 rounded-lg border bg-black/30 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-500"
                style={{ borderColor: "var(--border)" }}
              />
              <button
                type="submit"
                disabled={busy}
                className="btn-accent min-h-[44px] rounded-lg px-4 text-xs font-semibold"
              >
                {busy ? "Çalışıyor…" : "Karşılaştır"}
              </button>
            </form>
            {error && <p className="mb-2 text-xs text-rose-400">{error}</p>}
            <ResultGrid results={results} busy={busy} onPick={onPick} onClose={onClose} />
          </>
        )}
      </div>
    </div>
  );
}

function ResultGrid({
  results,
  busy,
  onPick,
  onClose,
}: {
  results: CompareResult[];
  busy: boolean;
  onPick: (response: string, provider: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {results.map((r) => (
        <div
          key={r.provider}
          className="flex flex-col rounded-xl border p-3"
          style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
        >
          <div className="mb-1.5 flex items-center justify-between text-[11px]">
            <span className="font-semibold text-slate-200">
              {PROVIDER_LABELS[r.provider] ?? r.provider}
            </span>
            <span className="tabular-nums text-slate-500">
              {r.latency_ms} ms · {r.tokens_used} tok
            </span>
          </div>
          <div className="mb-2 flex-1 whitespace-pre-wrap text-[12px] leading-relaxed text-slate-300">
            {r.error ? <span className="text-rose-400">⚠ {r.error}</span> : r.response || "—"}
          </div>
          {!r.error && (
            <button
              type="button"
              onClick={() => {
                onPick(r.response, r.provider);
                onClose();
              }}
              className="btn-accent min-h-[36px] rounded-lg text-[11px] font-semibold"
            >
              Bu yanıtı seç →
            </button>
          )}
        </div>
      ))}
      {busy &&
        Array.from({ length: 2 }).map((_, i) => (
          <div
            key={`skeleton-${i}`}
            className="h-32 animate-pulse rounded-xl border"
            style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.03)" }}
          />
        ))}
    </div>
  );
}
