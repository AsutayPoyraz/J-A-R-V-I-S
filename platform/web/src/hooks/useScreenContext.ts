/**
 * useScreenContext — Özellik 7: onaylı ekran paylaşımı → 30 sn'de bir kare →
 * /api/screen/analyze → öneri toast'ı. Kullanıcı onaylamadan hiçbir şey çekilmez;
 * görüntüler yalnızca RAM'de işlenir (diske yazılmaz).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { isGuestMode } from "../components/LoginGate";

const ANALYZE_INTERVAL_MS = 30_000;

export function useScreenContext(onSuggestion?: (text: string) => void) {
  const [sharing, setSharing] = useState(false);
  const [denied, setDenied] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const suggestionRef = useRef(onSuggestion);
  suggestionRef.current = onSuggestion;

  const captureAndAnalyze = useCallback(async () => {
    const stream = streamRef.current;
    const video = videoRef.current;
    if (!stream || !video) return;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = Math.min(1280, video.videoWidth || 1280);
      canvas.height = Math.round(
        canvas.width * ((video.videoHeight || 720) / (video.videoWidth || 1280))
      );
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.5);
      const resp = await api.screenAnalyzeImage(dataUrl);
      if (resp.ok && resp.suggestion) {
        suggestionRef.current?.(resp.suggestion);
      }
    } catch {
      /* analiz hatası sessizce yutulur (graceful degradation) */
    }
  }, []);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    videoRef.current = null;
    setSharing(false);
  }, []);

  /** Kullanıcı onayı ister (Özellik 7.1: onay yok → hiçbir şey çekilmez). */
  const start = useCallback(async (): Promise<boolean> => {
    if (isGuestMode()) return false;
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setDenied(true);
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 1 },
        audio: false, // ses YOK, yalnızca görüntü (Özellik 7.1)
      });
      streamRef.current = stream;
      const video = document.createElement("video");
      video.srcObject = stream;
      video.muted = true;
      await video.play().catch(() => undefined);
      videoRef.current = video;
      setSharing(true);
      setDenied(false);
      // Kullanıcı paylaşımı durdurursa otomatik temizle:
      stream.getVideoTracks()[0]?.addEventListener("ended", stop);
      timerRef.current = setInterval(() => void captureAndAnalyze(), ANALYZE_INTERVAL_MS);
      // İlk analiz hemen yapılır:
      void captureAndAnalyze();
      return true;
    } catch {
      // NotAllowedError vb. → onay reddedildi
      setDenied(true);
      return false;
    }
  }, [captureAndAnalyze, stop]);

  useEffect(() => stop, [stop]);

  return { sharing, denied, start, stop };
}
