/** Camera kartı: aç/kapa + fotoğraf çek; OpenCV eksikse kurulum modalı (Özellik 3). */
import { useState } from "react";
import Card from "./Card";
import { api } from "../api/client";
import type { CameraStatus } from "../types";

interface Props {
  camera: CameraStatus;
  photo: string | null;
  busy: boolean;
  error: string | null;
  online: boolean;
  onToggle: () => void;
  onCapture: () => void;
  onClosePhoto: () => void;
}

export default function CameraCard({
  camera, photo, busy, error, online, onToggle, onCapture, onClosePhoto,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  // Özellik 3: "OpenCV kuruluyor..." modalı durumu.
  const [installing, setInstalling] = useState(false);
  const [installDone, setInstallDone] = useState<string | null>(null);
  const live = online && camera.status === "live";

  /** Özellik 3.5: açmadan önce /api/camera/status kontrolü + gerekirse kurulum. */
  const handleToggle = async () => {
    if (!online) return;
    try {
      const status = await api.cameraStatus();
      if (status.opencv_installed === false) {
        setInstalling(true);
        setInstallDone(null);
        try {
          const result = await api.cameraInstall();
          setInstallDone(
            result.ok
              ? "✅ OpenCV kuruldu — şimdi tekrar deneyin."
              : `⚠ ${result.detail || "Kurulum başarısız"}${
                  result.manual_command ? ` (manuel: ${result.manual_command})` : ""
                }`
          );
        } catch (e) {
          setInstallDone(
            e instanceof Error ? `⚠ ${e.message}` : "⚠ Kurulum başlatılamadı"
          );
        } finally {
          setInstalling(false);
        }
        return;
      }
      if (status.camera_available === false) {
        setInstallDone("⚠ Kamera bulunamadı — bağlı bir kamera var mı?");
        setTimeout(() => setInstallDone(null), 4000);
        return;
      }
    } catch {
      /* offline — doğrudan açmayı dene */
    }
    onToggle();
  };

  const handleCapture = () => {
    // Kayıt yalnızca kullanıcının açık eylemiyle başlar (güvenlik 6).
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 2500);
      return;
    }
    setConfirming(false);
    onCapture();
  };

  return (
    <Card title="Camera">
      {!photo && (
        <div className="relative mb-2 flex h-24 items-center justify-center rounded-lg border"
          style={{
            borderColor: live ? "rgb(239 68 68 / 0.55)" : "var(--border)",
            background: live ? "rgb(239 68 68 / 0.05)" : "rgb(255 255 255 / 0.02)",
          }}>
          {live ? (
            <>
              {/* Belirgin aktif göstergesi (gereklim 4) */}
              <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-red-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                LIVE {camera.width ? `${camera.width}×${camera.height}` : ""}
              </span>
              <span className="text-xs text-slate-300">Kamera etkin</span>
            </>
          ) : (
            <span className="text-xs text-slate-500">
              {online ? "Camera Off" : "--"}
            </span>
          )}
        </div>
      )}

      {photo && (
        <div className="relative mb-2">
          <img src={photo} alt="Son çekim" className="h-24 w-full rounded-lg object-cover" />
          <button
            type="button"
            onClick={onClosePhoto}
            className="absolute right-1.5 top-1.5 rounded-full bg-black/70 px-2 py-0.5 text-[10px] text-slate-200"
          >
            Kapat
          </button>
        </div>
      )}

      {error && <p className="mb-1.5 text-[11px] text-red-400">{error}</p>}
      {installDone && <p className="mb-1.5 text-[11px] text-slate-300">{installDone}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void handleToggle()}
          disabled={!online || busy}
          className="btn-accent min-h-[44px] flex-1 rounded-lg px-2 py-1.5 text-xs font-medium"
        >
          {busy ? "..." : live ? "Kapat" : "Aç"}
        </button>
        <button
          type="button"
          onClick={handleCapture}
          disabled={!live || busy}
          className="btn-accent min-h-[44px] flex-1 rounded-lg px-2 py-1.5 text-xs font-medium"
          title={live ? "Fotoğraf çek (iki dokunuş: onay)" : "Önce kamerayı açın"}
        >
          {confirming ? "Çek (onayla)" : "Fotoğraf Çek"}
        </button>
      </div>

      {/* Özellik 3.5: OpenCV kurulum modalı */}
      {installing && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" role="dialog">
          <div
            className="w-full max-w-sm rounded-2xl border p-5 text-center"
            style={{ borderColor: "var(--border-strong)", background: "rgb(10 12 18)" }}
          >
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
            <h4 className="mb-1 text-sm font-bold text-slate-100">OpenCV kuruluyor...</h4>
            <p className="text-[11px] leading-relaxed text-slate-400">
              Kamera modülü için opencv-python yükleniyor. Bu işlem birkaç dakika
              sürebilir — pencereyi kapatabilirsiniz, kurulum arka planda sürer.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
