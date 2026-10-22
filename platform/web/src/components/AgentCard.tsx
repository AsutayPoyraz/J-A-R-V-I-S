/** Bölüm E kartı: notlar/yapılacaklar (madde 23), Memory Bank (madde 18)
 * ve ekran analizi (madde 9). Tüm metinler i18n'den gelir. */
import { useCallback, useEffect, useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import { t } from "../i18n";
import type { MemoryItem, NoteItem, TodoItem } from "../types";

type Tab = "notes" | "todos" | "memory";

const TABS: { value: Tab; labelKey: string }[] = [
  { value: "notes", labelKey: "productivity.tab_notes" },
  { value: "todos", labelKey: "productivity.tab_todos" },
  { value: "memory", labelKey: "productivity.tab_memory" },
];

const input =
  "w-full rounded-lg border bg-black/30 px-2 py-1.5 text-xs outline-none placeholder:text-slate-500";
const inputStyle = { borderColor: "var(--border)" };
const btn =
  "rounded-lg border px-2.5 py-1 text-[10px] font-semibold disabled:opacity-50";

function Row({
  main,
  sub,
  onDelete,
  children,
}: {
  main: string;
  sub?: string;
  onDelete: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div
      className="flex items-start gap-2 border-b py-1.5 last:border-b-0"
      style={{ borderColor: "var(--border)" }}
    >
      {children}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs text-slate-200">{main}</p>
        {sub && <p className="truncate text-[10px] text-slate-500">{sub}</p>}
      </div>
      <button
        type="button"
        onClick={onDelete}
        className="text-[10px] text-slate-500 hover:text-red-400"
        title={t("common.delete")}
      >
        ✕
      </button>
    </div>
  );
}

export default function AgentCard() {
  const [tab, setTab] = useState<Tab>("notes");
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [todoText, setTodoText] = useState("");
  const [memoryText, setMemoryText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Madde 9: ekran analizi hızlı eylemi
  const [screenBusy, setScreenBusy] = useState(false);
  const [screenResult, setScreenResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [n, td, m] = await Promise.all([api.notes(), api.todos(), api.memory()]);
      setNotes(n.notes);
      setTodos(td.todos);
      setMemories(m.memories);
      setError(null);
    } catch {
      setError(t("common.error"));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const analyzeScreen = async () => {
    setScreenBusy(true);
    setScreenResult(null);
    try {
      const res = await api.screenAnalyze();
      setScreenResult(
        res.available && res.analysis ? res.analysis : t("agent.screen_failed")
      );
    } catch {
      setScreenResult(t("agent.screen_failed"));
    } finally {
      setScreenBusy(false);
    }
  };

  const addBtnStyle = {
    borderColor: "rgb(var(--accent-soft-rgb))",
    color: "rgb(var(--accent-soft-rgb))",
  };

  return (
    <Card title={t("productivity.title")} onRefresh={load} refreshing={busy}>
      {error && <p className="mb-2 text-[10px] text-amber-400">{error}</p>}

      {/* Sekmeler */}
      <div className="mb-3 flex gap-1.5">
        {TABS.map((tb) => (
          <button
            key={tb.value}
            type="button"
            onClick={() => setTab(tb.value)}
            className={`${btn} flex-1`}
            style={{
              borderColor: tab === tb.value ? "rgb(var(--accent-soft-rgb))" : "var(--border)",
              background: tab === tb.value ? "rgb(var(--accent-rgb) / 0.2)" : "transparent",
              color: tab === tb.value ? "rgb(var(--accent-soft-rgb))" : "var(--text-dim)",
            }}
          >
            {t(tb.labelKey)}
          </button>
        ))}
      </div>

      {tab === "notes" && (
        <>
          <form
            className="mb-2 space-y-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (!noteTitle.trim()) return;
              void run(async () => {
                await api.createNote(noteTitle.trim(), noteContent.trim());
                setNoteTitle("");
                setNoteContent("");
              });
            }}
          >
            <input
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              placeholder={t("productivity.note_title")}
              maxLength={80}
              className={input}
              style={inputStyle}
            />
            <input
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              placeholder={t("productivity.note_content")}
              maxLength={500}
              className={input}
              style={inputStyle}
            />
            <button type="submit" disabled={busy || !noteTitle.trim()} className={`${btn} w-full`} style={addBtnStyle}>
              {t("productivity.add")}
            </button>
          </form>
          {notes.length === 0 ? (
            <p className="text-[10px] text-slate-500">{t("productivity.empty_notes")}</p>
          ) : (
            notes.map((n) => (
              <Row key={n.id} main={n.title} sub={n.content || undefined} onDelete={() => void run(() => api.deleteNote(n.id))} />
            ))
          )}
        </>
      )}

      {tab === "todos" && (
        <>
          <form
            className="mb-2 flex gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (!todoText.trim()) return;
              void run(async () => {
                await api.createTodo(todoText.trim());
                setTodoText("");
              });
            }}
          >
            <input
              value={todoText}
              onChange={(e) => setTodoText(e.target.value)}
              placeholder={t("productivity.todo_placeholder")}
              maxLength={120}
              className={input}
              style={inputStyle}
            />
            <button type="submit" disabled={busy || !todoText.trim()} className={btn} style={addBtnStyle}>
              {t("productivity.add")}
            </button>
          </form>
          {todos.length === 0 ? (
            <p className="text-[10px] text-slate-500">{t("productivity.empty_todos")}</p>
          ) : (
            todos.map((td) => (
              <Row key={td.id} main={td.title} onDelete={() => void run(() => api.deleteTodo(td.id))}>
                <input
                  type="checkbox"
                  checked={!!td.done}
                  onChange={() => void run(() => api.setTodoDone(td.id, !td.done))}
                  className="mt-0.5"
                  style={{ accentColor: "rgb(var(--accent-soft-rgb))" }}
                />
              </Row>
            ))
          )}
        </>
      )}

      {tab === "memory" && (
        <>
          <form
            className="mb-2 flex gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (!memoryText.trim()) return;
              void run(async () => {
                await api.createMemory(memoryText.trim());
                setMemoryText("");
              });
            }}
          >
            <input
              value={memoryText}
              onChange={(e) => setMemoryText(e.target.value)}
              placeholder={t("productivity.memory_placeholder")}
              maxLength={500}
              className={input}
              style={inputStyle}
            />
            <button type="submit" disabled={busy || !memoryText.trim()} className={btn} style={addBtnStyle}>
              {t("productivity.add")}
            </button>
          </form>
          {memories.length === 0 ? (
            <p className="text-[10px] text-slate-500">{t("productivity.empty_memory")}</p>
          ) : (
            memories.map((m) => (
              <Row key={m.id} main={m.content} onDelete={() => void run(() => api.deleteMemory(m.id))} />
            ))
          )}
        </>
      )}

      {/* Madde 9: ekran analizi (vision sağlayıcı yapılandırılmışsa çalışır) */}
      <div className="mt-3 border-t pt-2.5" style={{ borderColor: "var(--border)" }}>
        <button
          type="button"
          onClick={() => void analyzeScreen()}
          disabled={screenBusy}
          className={`${btn} w-full`}
          style={addBtnStyle}
        >
          {screenBusy ? t("agent.screen_analyzing") : t("agent.screen_analyze")}
        </button>
        {screenResult && (
          <p className="mt-2 whitespace-pre-wrap text-[10px] leading-relaxed text-slate-300">
            {screenResult}
          </p>
        )}
      </div>
    </Card>
  );
}
