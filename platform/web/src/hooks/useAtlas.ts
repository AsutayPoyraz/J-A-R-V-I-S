/**
 * useAtlas — Özellik 17: web ATLAS görev yönetimi (REST + canlı WS adımları).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { AtlasTask } from "../types";

export function useAtlas() {
  const [current, setCurrent] = useState<AtlasTask | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const watch = useCallback((taskId: string) => {
    // Önce REST anlık görüntüsü, sonra WS canlı akış; WS yoksa 1 sn REST polling.
    void api
      .atlasTask(taskId)
      .then(setCurrent)
      .catch(() => undefined);
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    try {
      const ws = new WebSocket(`${proto}//${location.host}/ws/atlas/${taskId}`);
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data as string) as Partial<AtlasTask>;
          setCurrent((prev) =>
            prev && prev.task_id === taskId ? { ...prev, ...data } as AtlasTask : prev
          );
        } catch {
          /* bozuk kare yok sayılır */
        }
      };
      ws.onerror = () => startPolling(taskId);
      ws.onclose = () => startPolling(taskId);
    } catch {
      startPolling(taskId);
    }
  }, []);

  const startPolling = useCallback((taskId: string) => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const task = await api.atlasTask(taskId);
        setCurrent(task);
        if (task.status === "done" || task.status === "error") stopPolling();
      } catch {
        stopPolling();
      }
    }, 1200);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const createTask = useCallback(
    async (instruction: string) => {
      setBusy(true);
      setError(null);
      try {
        const created = await api.atlasCreateTask(instruction);
        setCurrent({
          task_id: created.task_id,
          instruction,
          type: created.type,
          status: "queued",
          steps: [],
          result: "",
        });
        watch(created.task_id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Görev oluşturulamadı");
      } finally {
        setBusy(false);
      }
    },
    [watch]
  );

  const cancel = useCallback(async () => {
    if (!current) return;
    try {
      await api.atlasCancelTask(current.task_id);
    } catch {
      /* offline */
    }
    setCurrent(null);
    stopPolling();
    wsRef.current?.close();
  }, [current, stopPolling]);

  useEffect(
    () => () => {
      wsRef.current?.close();
      stopPolling();
    },
    [stopPolling]
  );

  return { current, busy, error, createTask, cancel };
}
