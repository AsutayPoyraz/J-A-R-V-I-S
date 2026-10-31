/**
 * MacrosCard — Özellik 9: komut makroları (adım adım builder + çalıştır).
 */
import { useCallback, useEffect, useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import type { CommandMacro } from "../types";

type StepType = "chat" | "delay" | "api_call";

const STEP_LABELS: Record<StepType, string> = {
  chat: "💬 JARVIS'a söyle",
  delay: "⏱️ Bekle (sn)",
  api_call: "🌐 API çağrısı",
};

export default function MacrosCard() {
  const [macros, setMacros] = useState<CommandMacro[]>([]);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("");
  const [steps, setSteps] = useState<{ type: StepType; params: Record<string, unknown> }[]>([
    { type: "chat", params: { message: "" } },
  ]);
  const [running, setRunning] = useState<number | null>(null);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setMacros((await api.commandMacros()).macros);
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addStep = (type: StepType) => {
    setSteps((prev) => [
      ...prev,
      { type, params: type === "delay" ? { seconds: 2 } : {} },
    ]);
  };

  const updateStep = (index: number, key: string, value: unknown) => {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, params: { ...s.params, [key]: value } } : s))
    );
  };

  const create = async () => {
    if (!name.trim() || !trigger.trim() || steps.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.createCommandMacro({
        name: name.trim(),
        trigger_phrase: trigger.trim(),
        steps,
      });
      setName("");
      setTrigger("");
      setSteps([{ type: "chat", params: { message: "" } }]);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Makro oluşturulamadı");
    } finally {
      setBusy(false);
    }
  };

  const run = async (macro: CommandMacro) => {
    setRunning(macro.id);
    setOutput(null);
    setError(null);
    try {
      const resp = await api.runCommandMacro(macro.id);
      const replies = (resp.outputs || [])
        .filter((o) => o.type === "chat" && o.reply)
        .map((o) => o.reply);
      setOutput(replies.join("\n\n") || `'${macro.name}' çalıştırıldı.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Çalıştırılamadı");
    } finally {
      setRunning(null);
    }
  };

  const remove = async (macro: CommandMacro) => {
    try {
      await api.deleteCommandMacro(macro.id);
      await refresh();
    } catch {
      /* offline */
    }
  };

  return (
    <Card title="Komut Makroları">
      <p className="mb-2 text-[10px] text-slate-500">
        Tetikleyici ifadeyi sohbete yazınca makro otomatik çalışır.
      </p>

      {/* Yeni makro builder (Özellik 9.5) */}
      <div className="mb-2 space-y-1.5 rounded-lg border p-2" style={{ borderColor: "var(--border)" }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Makro adı (örn. Sabah Rutini)"
          className="min-h-[40px] w-full rounded-md border bg-black/30 px-2 py-1.5 text-[11px] text-slate-200 outline-none placeholder:text-slate-500"
          style={{ borderColor: "var(--border)" }}
        />
        <input
          value={trigger}
          onChange={(e) => setTrigger(e.target.value)}
          placeholder="Tetikleyici: 'sabah rutinini başlat'"
          className="min-h-[40px] w-full rounded-md border bg-black/30 px-2 py-1.5 text-[11px] text-slate-200 outline-none placeholder:text-slate-500"
          style={{ borderColor: "var(--border)" }}
        />
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <select
              value={step.type}
              onChange={(e) =>
                setSteps((prev) =>
                  prev.map((s, j) =>
                    j === i
                      ? {
                          type: e.target.value as StepType,
                          params: e.target.value === "delay" ? { seconds: 2 } : {},
                        }
                      : s
                  )
                )
              }
              className="min-h-[40px] w-28 rounded-md border bg-black/30 px-1 text-[10px] text-slate-300 outline-none"
              style={{ borderColor: "var(--border)" }}
            >
              {(Object.keys(STEP_LABELS) as StepType[]).map((t) => (
                <option key={t} value={t}>{STEP_LABELS[t]}</option>
              ))}
            </select>
            {step.type === "chat" && (
              <input
                value={String(step.params.message ?? "")}
                onChange={(e) => updateStep(i, "message", e.target.value)}
                placeholder="JARVIS'a iletilecek mesaj"
                className="min-h-[40px] flex-1 rounded-md border bg-black/30 px-2 py-1.5 text-[11px] text-slate-200 outline-none placeholder:text-slate-500"
                style={{ borderColor: "var(--border)" }}
              />
            )}
            {step.type === "delay" && (
              <input
                type="number"
                min={0.5}
                max={10}
                step={0.5}
                value={Number(step.params.seconds ?? 2)}
                onChange={(e) => updateStep(i, "seconds", Number(e.target.value))}
                className="min-h-[40px] w-20 rounded-md border bg-black/30 px-2 py-1.5 text-[11px] text-slate-200 outline-none"
                style={{ borderColor: "var(--border)" }}
              />
            )}
            {step.type === "api_call" && (
              <input
                value={String(step.params.endpoint ?? "")}
                onChange={(e) => updateStep(i, "endpoint", e.target.value)}
                placeholder="/api/weather"
                className="min-h-[40px] flex-1 rounded-md border bg-black/30 px-2 py-1.5 text-[11px] text-slate-200 outline-none placeholder:text-slate-500"
                style={{ borderColor: "var(--border)" }}
              />
            )}
            <button
              type="button"
              onClick={() => setSteps((prev) => prev.filter((_, j) => j !== i))}
              className="min-h-[40px] min-w-[32px] text-slate-600 hover:text-rose-400"
              title="Adımı sil"
            >
              ✕
            </button>
          </div>
        ))}
        <div className="flex gap-1.5">
          <select
            onChange={(e) => {
              if (e.target.value) addStep(e.target.value as StepType);
              e.target.value = "";
            }}
            className="min-h-[40px] flex-1 rounded-md border bg-black/30 px-1.5 text-[10px] text-slate-400 outline-none"
            style={{ borderColor: "var(--border)" }}
            defaultValue=""
          >
            <option value="" disabled>+ Adım ekle…</option>
            {(Object.keys(STEP_LABELS) as StepType[]).map((t) => (
              <option key={t} value={t}>{STEP_LABELS[t]}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void create()}
            disabled={busy || !name.trim() || !trigger.trim()}
            className="btn-accent min-h-[40px] rounded-md px-3 text-[11px] font-semibold"
          >
            Kaydet
          </button>
        </div>
      </div>

      {error && <p className="mb-1.5 text-[10px] text-rose-400">{error}</p>}
      {output && (
        <div
          className="mb-2 max-h-24 overflow-y-auto whitespace-pre-wrap rounded-md border px-2 py-1.5 text-[10px] text-slate-300"
          style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.03)" }}
        >
          {output}
        </div>
      )}

      <div className="space-y-1">
        {macros.map((macro) => (
          <div
            key={macro.id}
            className="group flex items-center gap-2 rounded-lg border px-2 py-1.5 text-[11px]"
            style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
          >
            <div className="min-w-0 flex-1">
              <div className="truncate text-slate-200">⚡ {macro.name}</div>
              <div className="truncate text-[9px] text-slate-500">
                "{macro.trigger_phrase}" · {macro.steps.length} adım
              </div>
            </div>
            <button
              type="button"
              onClick={() => void run(macro)}
              disabled={running === macro.id}
              className="btn-accent min-h-[36px] rounded-md px-2.5 text-[10px] font-semibold"
            >
              {running === macro.id ? "…" : "Çalıştır"}
            </button>
            <button
              type="button"
              onClick={() => void remove(macro)}
              className="min-h-[32px] min-w-[32px] text-slate-600 opacity-0 hover:text-rose-400 group-hover:opacity-100"
              title="Makroyu sil"
            >
              ✕
            </button>
          </div>
        ))}
        {macros.length === 0 && (
          <p className="py-2 text-center text-[10px] text-slate-500">Henüz makro yok.</p>
        )}
      </div>
    </Card>
  );
}

