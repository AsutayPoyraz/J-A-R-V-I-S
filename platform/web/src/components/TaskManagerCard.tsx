/**
 * TaskManagerCard — Özellik 6: Kanban görünümü (Yapılacak / Devam / Bitti).
 * Misafirde: sunucu çağrısı yapılmaz, oturumluk yerel liste (kayıt yok).
 */
import { useCallback, useEffect, useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import { isGuestMode } from "./LoginGate";
import type { Task } from "../types";

const PRIORITY_COLORS: Record<Task["priority"], string> = {
  low: "rgb(148 163 184)",
  medium: "rgb(59 130 246)",
  high: "rgb(249 115 22)",
  urgent: "rgb(239 68 68)",
};

const COLUMNS: { key: Task["status"]; label: string }[] = [
  { key: "todo", label: "Yapılacak" },
  { key: "in_progress", label: "Devam" },
  { key: "done", label: "Bitti" },
];

function TaskRow({ task, onCycle, onDelete }: {
  task: Task;
  onCycle: (t: Task) => void;
  onDelete: (t: Task) => void;
}) {
  return (
    <div
      className="group rounded-lg border px-2 py-1.5 text-[11px]"
      style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
    >
      <div className="flex items-start justify-between gap-1.5">
        <button
          type="button"
          onClick={() => onCycle(task)}
          className="min-h-[32px] flex-1 text-left text-slate-200 hover:text-white"
          title="Durumu ilerlet (todo → devam → bitti)"
        >
          <span
            className="mr-1 inline-block h-2 w-2 rounded-full"
            style={{ background: PRIORITY_COLORS[task.priority] }}
            title={`Öncelik: ${task.priority}`}
          />
          {task.title}
          {task.due_date ? (
            <span className="ml-1 text-[9px] text-slate-500">📅 {task.due_date.slice(0, 10)}</span>
          ) : null}
        </button>
        <button
          type="button"
          onClick={() => onDelete(task)}
          className="min-h-[32px] min-w-[32px] text-slate-500 opacity-0 transition-opacity hover:text-rose-400 group-hover:opacity-100"
          title="Görevi sil"
        >
          ✕
        </button>
      </div>
      {task.project_name ? (
        <div className="mt-0.5 text-[9px] uppercase tracking-wider text-slate-500">
          {task.project_name}
        </div>
      ) : null}
    </div>
  );
}

export default function TaskManagerCard() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<Task["priority"]>("medium");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const guest = isGuestMode();

  const refresh = useCallback(async () => {
    if (guest) return; // misafir: session-only (yerel liste kalır)
    try {
      setTasks((await api.tasks()).tasks);
    } catch {
      /* offline — mevcut liste korunur */
    }
  }, [guest]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addTask = async () => {
    const trimmed = title.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    if (guest) {
      // Misafir: yalnızca bu oturumda yaşar (sayfa yenilenince sıfır).
      setTasks((prev) => [
        {
          id: Date.now(),
          project_id: null,
          title: trimmed,
          description: "",
          priority,
          status: "todo",
          due_date: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setTitle("");
      setBusy(false);
      return;
    }
    try {
      await api.createTask({ title: trimmed, priority });
      setTitle("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Görev eklenemedi");
    } finally {
      setBusy(false);
    }
  };

  const cycle = async (task: Task) => {
    const next: Task["status"] =
      task.status === "todo"
        ? "in_progress"
        : task.status === "in_progress"
          ? "done"
          : "todo";
    if (guest) {
      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: next } : t))
      );
      return;
    }
    try {
      await api.updateTask(task.id, { status: next });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Durum güncellenemedi");
    }
  };

  const remove = async (task: Task) => {
    if (guest) {
      setTasks((prev) => prev.filter((t) => t.id !== task.id));
      return;
    }
    try {
      await api.deleteTask(task.id);
      await refresh();
    } catch {
      /* offline */
    }
  };

  return (
    <Card title="Görevler">
      {guest && (
        <p className="mb-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-200">
          Misafir modu: görevler bu oturumda tutulur, kaydedilmez.
        </p>
      )}
      <div className="mb-2 flex gap-1.5">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void addTask()}
          placeholder="Yeni görev..."
          className="min-h-[44px] flex-1 rounded-lg border bg-black/30 px-2.5 py-2 text-xs text-slate-200 outline-none placeholder:text-slate-500"
          style={{ borderColor: "var(--border)" }}
        />
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value as Task["priority"])}
          className="min-h-[44px] rounded-lg border bg-black/30 px-1.5 text-[10px] text-slate-300 outline-none"
          style={{ borderColor: "var(--border)" }}
        >
          <option value="low">Düşük</option>
          <option value="medium">Orta</option>
          <option value="high">Yüksek</option>
          <option value="urgent">Acil</option>
        </select>
        <button
          type="button"
          onClick={() => void addTask()}
          disabled={busy}
          className="btn-accent min-h-[44px] rounded-lg px-3 text-xs font-semibold"
        >
          +
        </button>
      </div>
      {error && <p className="mb-1.5 text-[10px] text-rose-400">{error}</p>}
      <div className="grid grid-cols-3 gap-1.5">
        {COLUMNS.map((col) => (
          <div key={col.key} className="min-w-0">
            <div className="mb-1 flex items-center justify-between px-0.5">
              <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">
                {col.label}
              </span>
              <span className="text-[9px] tabular-nums text-slate-500">
                {tasks.filter((t) => t.status === col.key).length}
              </span>
            </div>
            <div className="space-y-1">
              {tasks
                .filter((t) => t.status === col.key)
                .slice(0, 12)
                .map((t) => (
                  <TaskRow
                    key={t.id}
                    task={t}
                    onCycle={(x) => void cycle(x)}
                    onDelete={(x) => void remove(x)}
                  />
                ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
