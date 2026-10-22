"""TTS — gTTS ile Türkçe konuşma sentezi ve MP3 oynatma."""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

logger = logging.getLogger("jarvis.voice.tts")

class TTSService:
    """Metni sese çevirir ve çalar; iptal edilebilir."""

    def __init__(self, tmp_dir: Path | None = None, *,
                 lang: str = "tr", rate: float = 1.0) -> None:
        self._cancel = threading.Event()
        self._speaking = threading.Event()
        self._tmp_dir = tmp_dir
        # Madde 14: kullanıcıya özel TTS ses/hız tercihleri.
        self._lang = lang if lang in ("tr", "en") else "tr"
        try:
            self._rate = min(2.0, max(0.5, float(rate)))
        except (TypeError, ValueError):
            self._rate = 1.0

    def configure(self, lang: str | None = None, rate: float | None = None) -> None:
        """TTS ses/hız tercihini çalışma anında günceller."""
        if lang in ("tr", "en"):
            self._lang = lang
        if rate is not None:
            try:
                self._rate = min(2.0, max(0.5, float(rate)))
            except (TypeError, ValueError):
                pass

    @property
    def settings(self) -> dict[str, float | str]:
        return {"lang": self._lang, "rate": self._rate}

    @property
    def speaking(self) -> bool:
        return self._speaking.is_set()

    def cancel(self) -> None:
        """Kullanıcı konuşmaya başladı — mevcut konuşmayı kes (barge-in)."""
        self._cancel.set()

    async def speak(self, text: str, owner_id: str = "local") -> bool:
        """Metni seslendirir. İptal edilirse False döner.

        ``owner_id``: madde 7 — TTS ses/hız tercihi sahibine göre okunur.
        """
        text = (text or "").strip()
        if not text:
            return False
        self._cancel.clear()
        self._speaking.set()
        try:
            return await self._speak_inner(text, owner_id)
        finally:
            self._speaking.clear()

    def _apply_owner_settings(self, owner_id: str = "local") -> None:
        """Madde 14: sahibinin tts_voice/tts_rate tercihini her okumada uygular."""
        try:
            from ..store import database

            row = database.get_user_settings(owner_id)
            self.configure(lang=row.get("tts_voice"), rate=row.get("tts_rate"))
        except Exception:
            logger.debug("TTS ayarları okunamadı; mevcut değerler korunuyor")

    async def _speak_inner(self, text: str, owner_id: str = "local") -> bool:
        path: Path | None = None
        self._apply_owner_settings(owner_id)
        try:
            from gtts import gTTS

            with NamedTemporaryFile(
                suffix=".mp3", delete=False, dir=self._tmp_dir
            ) as tmp:
                tmp_path = Path(tmp.name)
            path = tmp_path
            tts = gTTS(text=text, lang=self._lang, slow=self._rate < 0.95)
            await asyncio.to_thread(tts.save, str(path))
            if self._cancel.is_set():
                path.unlink(missing_ok=True)
                return False
            return await asyncio.to_thread(self._play_mp3_blocking, path)
        except Exception:
            logger.exception("gTTS konuşma üretimi veya oynatması başarısız")
            if path is not None:
                path.unlink(missing_ok=True)
            return False

    def _play_mp3_blocking(self, path: Path) -> bool:
        """MP3'ü çalar; hız tercihi 1.0'dan farklıysa ffmpeg atempo uygular."""
        try:
            from playsound import playsound

            if abs(self._rate - 1.0) <= 0.05:
                playsound(str(path))
            else:
                adjusted = self._render_rate(path)
                try:
                    playsound(str(adjusted if adjusted is not None else path))
                finally:
                    if adjusted is not None:
                        adjusted.unlink(missing_ok=True)
            return not self._cancel.is_set()
        finally:
            path.unlink(missing_ok=True)

    def _render_rate(self, path: Path) -> Path | None:
        """Hız düzenlenmiş MP3 üretir; ffmpeg yoksa None (orijinal hız)."""
        import shutil
        import subprocess

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            logger.debug("ffmpeg bulunamadı; TTS hız ayarı uygulanamadı")
            return None
        out = path.with_name(f"{path.stem}_{self._rate:.2f}x.mp3")
        try:
            subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-i", str(path),
                 "-filter:a", f"atempo={self._rate:.2f}", str(out)],
                check=True, timeout=60,
            )
            return out
        except Exception:
            logger.exception("TTS hız düzenleme başarısız; orijinal hız kullanılıyor")
            out.unlink(missing_ok=True)
            return None
