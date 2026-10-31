/**
 * AtlasPanel — Özellik 17: sağdan açılan tam yükseklik ATLAS paneli (drawer).
 * Düzen: üst bar (başlık+durum) | sol adım listesi | sağ canlı çıktı |
 * alt görev giriş kutusu. Panel açıkken sohbet paneli daralır (split view).
 */
import { useEffect, useState } from "react";
import { useAtlas } from "../hooks/useAtlas";

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  queued: { text: "Kuyrukta", color: "rgb(250 204 21)" },
  running: { text: "Çalışıyor", color: "rgb(59 130 246)" },
  done: { text: "Tamamlandı", color: "rgb(74 222 128)" },
  error: { text: "Hata", color: "rgb(248 113 113)" },
};

const STEP_ICONS: Record<string, string> = {
  done: "✅",
  running: "⏳",
  error: "❌",
};

export default function AtlasPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { current, busy, error, createTask, cancel } = useAtlas();
  const [instruction, setInstruction] = useState("");

  useEffect(() => {
    if (!open) setInstruction("");
  }, [open]);

  if (!open) return null;

  const status = current ? STATUS_LABELS[current.status] ?? STATUS_LABELS.queued : null;

  return (
    <>
      {/* Split view karartması */}
      <div className="fixed inset-0 z-40 bg-black/40 lg:bg-transparent" onClick={onClose} />
      <aside
        className="fixed bottom-0 right-0 top-0 z-50 flex w-full flex-col border-l shadow-2xl lg:w-[480px] lg:min-w-[480px]"
        style={{ borderColor: "var(--border-strong)", background: "rgb(8 10 16)" }}
      >
        <div
          className="flex h-14 shrink-0 items-center justify-between border-b px-4"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold tracking-widest text-slate-100">ATLAS</span>
            {status && (
              <span
                className="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                style={{
                  borderColor: `${status.color}55`,
                  color: status.color,
                  background: `${status.color}18`,
                }}
              >
                {status.text}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {current && (
              <button
                type="button"
                onClick={() => void cancel()}
                className="min-h-[44px] rounded-lg px-2 text-[11px] text-slate-400 hover:text-rose-400"
              >
                İptal
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] min-w-[44px] text-lg text-slate-400 hover:text-white"
              title="Paneli kapat"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4 lg:flex-row">
          <div className="mb-3 w-full lg:mb-0 lg:w-1/2 lg:pr-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Adımlar
            </p>
            <div className="space-y-1">
              {current?.steps?.length ? (
                current.steps.map((step) => (
                  <div
                    key={step.index}
                    className="rounded-md border px-2 py-1.5 text-[11px]"
                    style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
                  >
                    <span className="mr-1">{STEP_ICONS[step.status] ?? "•"}</span>
                    <span className="text-slate-300">{step.description}</span>
                    {step.detail && (
                      <div className="mt-0.5 text-[9px] text-rose-400">{step.detail}</div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-[11px] text-slate-500">
                  Henüz adım yok — aşağıya görev yazın.
                </p>
              )}
            </div>
          </div>
          <div className="w-full lg:w-1/2 lg:pl-3">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Canlı çıktı
            </p>
            <div
              className="min-h-[180px] whitespace-pre-wrap rounded-lg border p-3 text-[12px] leading-relaxed text-slate-300"
              style={{ borderColor: "var(--border)", background: "rgb(0 0 0 / 0.3)" }}
            >
              {error ? <span className="text-rose-400">⚠ {error}</span> : current?.result || "—"}
            </div>
            <p className="mt-2 text-[9px] leading-relaxed text-slate-600">
              Not: Web ATLAS klavye/fare kontrolü yapmaz; GUI görevleri için
              masaüstü uygulamasını kullanın.
            </p>
          </div>
        </div>

        <form
          className="flex shrink-0 gap-2 border-t p-3"
          style={{ borderColor: "var(--border)" }}
          onSubmit={(e) => {
            e.preventDefault();
            const text = instruction.trim();
            if (!text) return;
            void createTask(text);
            setInstruction("");
          }}
        >
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="ATLAS'a görev ver: 'özetle', 'çevir', 'araştır'…"
            className="min-h-[44px] flex-1 rounded-lg border bg-black/30 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-500"
            style={{ borderColor: "var(--border)" }}
          />
          <button
            type="submit"
            disabled={busy}
            className="btn-accent min-h-[44px] rounded-lg px-4 text-xs font-semibold"
          >
            {busy ? "…" : "Çalıştır"}
          </button>
        </form>
      </aside>
    </>
  );
}
