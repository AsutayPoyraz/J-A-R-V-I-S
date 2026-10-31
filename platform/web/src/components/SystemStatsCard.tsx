/** System Stats kartı: "Sunucu" (psutil) | "Bu Cihaz" (istemci) sekmeleri — Özellik 2. */
import { useState } from "react";
import Card from "./Card";
import { deviceIcon } from "../hooks/useClientStats";
import type { ClientStats, SystemStats } from "../types";

interface Props {
  stats: SystemStats | null;
  online: boolean;
  clientStats: ClientStats | null;
}

/** Değer: offline ya da veri yoksa "--". */
function fmt<T>(online: boolean, value: T | undefined | null, render: (v: T) => string): string {
  if (!online || value === undefined || value === null) return "--";
  return render(value);
}

function Bar({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: "rgb(255 255 255 / 0.08)" }}>
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{
          width: `${clamped}%`,
          background: "linear-gradient(90deg, rgb(var(--accent-rgb) / 0.55), rgb(var(--accent-soft-rgb)))",
          boxShadow: "0 0 8px rgb(var(--accent-rgb) / 0.5)",
        }}
      />
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-2 text-center" style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}>
      <div className="text-[9px] uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums text-slate-100">{value}</div>
    </div>
  );
}

export default function SystemStatsCard({ stats, online, clientStats }: Props) {
  const [tab, setTab] = useState<"server" | "client">("server");
  const cpu = stats?.cpu;
  const mem = stats?.memory;
  const disk = stats?.disk;
  // Desteklenmeyen API'lerde "Veri yok" göster (hata fırlatma yok).
  const heapPercent =
    clientStats?.js_heap_used_mb != null && clientStats?.js_heap_limit_mb
      ? Math.round((clientStats.js_heap_used_mb / clientStats.js_heap_limit_mb) * 100)
      : null;
  const battery = clientStats?.battery_percent;

  return (
    <Card title="System Stats">
      {/* Özellik 2.3: Sunucu | Bu Cihaz sekme geçişi */}
      <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg border p-0.5" style={{ borderColor: "var(--border)" }}>
        <button
          type="button"
          onClick={() => setTab("server")}
          className="rounded-md py-1.5 text-[11px] font-medium transition-colors"
          style={{
            background: tab === "server" ? "rgb(var(--accent-rgb) / 0.25)" : "transparent",
            color: tab === "server" ? "rgb(var(--accent-soft-rgb))" : "rgb(148 163 184)",
          }}
        >
          🖥️ Sunucu
        </button>
        <button
          type="button"
          onClick={() => setTab("client")}
          className="rounded-md py-1.5 text-[11px] font-medium transition-colors"
          style={{
            background: tab === "client" ? "rgb(var(--accent-rgb) / 0.25)" : "transparent",
            color: tab === "client" ? "rgb(var(--accent-soft-rgb))" : "rgb(148 163 184)",
          }}
        >
          {deviceIcon(clientStats?.device_type)} Bu Cihaz
        </button>
      </div>

      {tab === "server" ? (
        <>
          {/* CPU yüzdesi */}
          <div className="mb-3">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[10px] uppercase tracking-widest text-slate-400">CPU</span>
              <span className="text-xl font-bold tabular-nums text-slate-100">
                {fmt(online, cpu?.percent, (p) => `${p.toFixed(0)}%`)}
              </span>
            </div>
            <Bar percent={online ? (cpu?.percent ?? 0) : 0} />
          </div>
          {/* RAM: GB + çubuk */}
          <div className="mb-3">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[10px] uppercase tracking-widest text-slate-400">RAM Kullanımı</span>
              <span className="text-xs tabular-nums text-slate-200">
                {fmt(online, mem, (m) => `${m.used_gb.toFixed(1)} GB / ${m.total_gb.toFixed(1)} GB`)}
              </span>
            </div>
            <Bar percent={online ? (mem?.percent ?? 0) : 0} />
          </div>
          {/* CPU / Memory / Disk kutuları */}
          <div className="grid grid-cols-3 gap-2">
            <MetricBox label="CPU" value={fmt(online, cpu?.percent, (p) => `${p.toFixed(0)}%`)} />
            <MetricBox label="Memory" value={fmt(online, mem?.percent, (p) => `${p.toFixed(0)}%`)} />
            <MetricBox label="Disk" value={fmt(online, disk?.percent, (p) => `${p.toFixed(0)}%`)} />
          </div>
        </>
      ) : (
        <>
          <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>
              {deviceIcon(clientStats?.device_type)}{" "}
              {clientStats?.device_type === "phone"
                ? "Telefon"
                : clientStats?.device_type === "tablet"
                  ? "Tablet"
                  : clientStats?.device_type === "laptop"
                    ? "Laptop"
                    : "Masaüstü"}
            </span>
            <span className="tabular-nums text-slate-300">
              {clientStats
                ? `${clientStats.screen_width}×${clientStats.screen_height} @${clientStats.pixel_ratio}x`
                : "--"}
            </span>
          </div>
          <div className="mb-3">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[10px] uppercase tracking-widest text-slate-400">RAM (cihaz)</span>
              <span className="text-sm font-semibold tabular-nums text-slate-100">
                {clientStats?.device_memory_gb != null ? `${clientStats.device_memory_gb} GB` : "Veri yok"}
              </span>
            </div>
            <Bar percent={clientStats?.device_memory_gb ? Math.min(100, clientStats.device_memory_gb * 12.5) : 0} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MetricBox
              label="CPU Çekirdek"
              value={clientStats?.cpu_cores != null ? String(clientStats.cpu_cores) : "Veri yok"}
            />
            <MetricBox
              label="JS Heap"
              value={
                heapPercent != null && clientStats
                  ? `${clientStats.js_heap_used_mb} MB (%${heapPercent})`
                  : "Veri yok"
              }
            />
            <MetricBox
              label="Batarya"
              value={
                battery != null
                  ? `%${battery}${clientStats?.battery_charging ? " ⚡" : ""}`
                  : "Veri yok"
              }
            />
            <MetricBox
              label="Ağ"
              value={
                clientStats?.connection_type && clientStats.connection_type !== "—"
                  ? clientStats.connection_type.toUpperCase() +
                    (clientStats?.downlink_mbps != null ? ` · ${clientStats.downlink_mbps} Mb/s` : "")
                  : "Veri yok"
              }
            />
          </div>
        </>
      )}
    </Card>
  );
}
