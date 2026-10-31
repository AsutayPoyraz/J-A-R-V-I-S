/**
 * HabitsCard — Özellik 10: alışkanlık listesi + günlük checkbox + streak +
 * haftalık ısı haritası (GitHub contribution benzeri, saf CSS grid).
 */
import { useCallback, useEffect, useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import type { Habit } from "../types";

interface HabitStats {
  total: number;
  best_streak: number;
  completion_rate: number;
  week: { date: string; done: number; of: number }[];
}

function heatColor(ratio: number): string {
  if (ratio <= 0) return "rgb(255 255 255 / 0.05)";
  if (ratio < 0.34) return "rgb(var(--accent-rgb) / 0.25)";
  if (ratio < 0.67) return "rgb(var(--accent-rgb) / 0.55)";
  return "rgb(var(--accent-rgb) / 0.9)";
}

export default function HabitsCard() {
  const [habits, setHabits] = useState<Habit[]>([]);
  const [stats, setStats] = useState<HabitStats | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([api.habits(), api.habitStats()]);
      setHabits(h.habits);
      setStats(s);
    } catch {
      /* offline */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addHabit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      await api.createHabit({ name: trimmed, icon: "check" });
      setName("");
      await refresh();
    } catch {
      /* offline */
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (habit: Habit) => {
    try {
      await api.logHabit(habit.id, !habit.today_done);
      await refresh();
    } catch {
      /* offline */
    }
  };

  const remove = async (habit: Habit) => {
    try {
      await api.deleteHabit(habit.id);
      await refresh();
    } catch {
      /* offline */
    }
  };

  return (
    <Card title="Alışkanlıklar">
      {/* Streak göstergesi (Özellik 10.6) */}
      <div className="mb-2 flex items-center justify-between text-[11px]">
        <span className="text-slate-400">
          🔥 En uzun seri:{" "}
          <strong className="text-slate-100">{stats?.best_streak ?? 0} gün</strong>
        </span>
        <span className="tabular-nums text-slate-400">
          Tamamlama: <strong className="text-slate-100">%{stats?.completion_rate ?? 0}</strong>
        </span>
      </div>

      {/* Haftalık ısı haritası */}
      {stats && stats.week.length > 0 && (
        <div className="mb-3 flex gap-1">
          {stats.week.map((day) => {
            const ratio = day.of > 0 ? day.done / day.of : 0;
            return (
              <div key={day.date} className="flex-1 text-center" title={`${day.date}: ${day.done}/${day.of}`}>
                <div
                  className="h-6 w-full rounded"
                  style={{ background: heatColor(ratio) }}
                />
                <div className="mt-0.5 text-[8px] text-slate-500">
                  {new Date(day.date + "T00:00:00").toLocaleDateString("tr-TR", { weekday: "narrow" })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mb-2 flex gap-1.5">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void addHabit()}
          placeholder="Yeni alışkanlık..."
          className="min-h-[44px] flex-1 rounded-lg border bg-black/30 px-2.5 py-2 text-xs text-slate-200 outline-none placeholder:text-slate-500"
          style={{ borderColor: "var(--border)" }}
        />
        <button
          type="button"
          onClick={() => void addHabit()}
          disabled={busy}
          className="btn-accent min-h-[44px] rounded-lg px-3 text-xs font-semibold"
        >
          +
        </button>
      </div>

      <div className="space-y-1">
        {habits.map((habit) => (
          <div
            key={habit.id}
            className="group flex items-center gap-2 rounded-lg border px-2 py-1.5"
            style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}
          >
            <button
              type="button"
              onClick={() => void toggle(habit)}
              className="min-h-[44px] min-w-[44px] text-lg"
              title={habit.today_done ? "Bugün tamamlandı" : "Bugün işaretle"}
            >
              {habit.today_done ? "✅" : "⬜"}
            </button>
            <span className="flex-1 truncate text-[11px] text-slate-200">{habit.name}</span>
            {habit.streak > 0 && (
              <span className="text-[10px] tabular-nums text-amber-300">🔥 {habit.streak}</span>
            )}
            <button
              type="button"
              onClick={() => void remove(habit)}
              className="min-h-[32px] min-w-[32px] text-slate-600 opacity-0 hover:text-rose-400 group-hover:opacity-100"
              title="Alışkanlığı sil"
            >
              ✕
            </button>
          </div>
        ))}
        {habits.length === 0 && (
          <p className="py-2 text-center text-[10px] text-slate-500">
            Henüz alışkanlık yok — ilkini ekle!
          </p>
        )}
      </div>
    </Card>
  );
}
