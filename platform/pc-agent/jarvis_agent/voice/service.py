"""VoiceService — sesli modun orkestrasyonu (Faz 3).

Görevleri (gereksinim 5.4):
- Wake word / uyandırma cümlesi dinleme — TAMAMEN YEREL (faster-whisper)
- Çift alkış algılama (clap.py) → "Buyrun efendim..." + pencere öne
- Sesli sohbet döngüsü: dinle → STT → sohbet çekirdeği → TTS
- Barge-in: JARVIS konuşurken kullanıcı konuşursa susma
- "sesli moddan çık" komutu → wake dinlemeye dönüş

Threading modeli: ses döngüsü kendi iş parçacığında; async parçalar
(STT online, chat, TTS) asyncio.run_coroutine_threadsafe ile ana loop'a
yollanır. UI durum değişimlerini ``on_state`` callback'i ile WebSocket
yayınına aktarır (app.py bağlar).
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import numpy as np

from .. import config
from ..chat.service import run_chat
from ..core.stats import StatsMonitor
from ..llm import ChatProvider
from ..store import database
from . import stt as stt_module
from . import textmatch
from .audio import MicrophoneError, MicrophoneStream, has_audio_backend
from .clap import ClapDetector, EnergyVAD, rms
from .focus_window import bring_jarvis_to_front
from .tts import TTSService

logger = logging.getLogger("jarvis.voice")

SAMPLE_RATE = 16000

# ── VAD / segment parametreleri ────────────────────────────────────────────
SEGMENT_SILENCE_S = 0.6      # konuşma sonu: bu kadar sessizlik
SEGMENT_MIN_S = 0.25          # daha kısası gürültüdür
SEGMENT_MAX_S = 6.0           # kesme güvenliği
BARGE_IN_FACTOR = 3.5         # konuşma sırasında daha yüksek eşik (ekolayzır koruması)

# ── Ayar anahtarları (DB: settings tablosu) ────────────────────────────────
DEFAULT_WAKE_PHRASES = [
    "hey jarvis",
    "hey jarvis ne zaman",
    "uyan bakalım baba eve geldi",
]
DEFAULT_WAKE_RESPONSES = {
    "hey jarvis": "Sizi dinliyorum efendim.",
    "uyan bakalım baba eve geldi": (
        "Hoş geldiniz efendim, size nasıl yardımcı olabilirim?"
    ),
}
DEFAULT_EXIT_PHRASES = [
    "sesli moddan çık",
    "sesli modu kapat",
    "görüşürüz jarvis",
    "kapat jarvis",
]
CLAP_RESPONSE = "Buyrun efendim, size nasıl yardımcı olabilirim?"
VOICE_ENTER_RESPONSE = "Tamamdır."

STATES = ("off", "wake", "voice")       # mic/oturum kapsamı
SESSIONS = ("listening", "thinking", "speaking")


def _setting_json(key: str, default: Any) -> Any:
    raw = database.get_setting(key)
    if raw is None:
        return default
    try:
        parsed = json.loads(raw)
        return parsed if parsed else default
    except (ValueError, TypeError):
        return default


@dataclass
class VoiceSettings:
    wake_phrases: list[str]
    wake_responses: dict[str, str]
    exit_phrases: list[str]
    clap_enabled: bool
    clap_sensitivity: float

    @classmethod
    def load(cls) -> "VoiceSettings":
        return cls(
            wake_phrases=_setting_json("voice_wake_phrases", DEFAULT_WAKE_PHRASES),
            wake_responses=_setting_json("voice_wake_responses", DEFAULT_WAKE_RESPONSES),
            exit_phrases=_setting_json("voice_exit_phrases", DEFAULT_EXIT_PHRASES),
            clap_enabled=database.get_setting("voice_clap_enabled", "1") == "1",
            clap_sensitivity=float(database.get_setting("voice_clap_sensitivity", "5.0")),
        )

    def persist(self) -> None:
        database.set_setting("voice_wake_phrases", json.dumps(self.wake_phrases, ensure_ascii=False))
        database.set_setting("voice_wake_responses", json.dumps(self.wake_responses, ensure_ascii=False))
        database.set_setting("voice_exit_phrases", json.dumps(self.exit_phrases, ensure_ascii=False))
        database.set_setting("voice_clap_enabled", "1" if self.clap_enabled else "0")
        database.set_setting("voice_clap_sensitivity", str(self.clap_sensitivity))


class VoiceService:
    """Tek mikrofon, tek thread, üç durum: off / wake / voice."""

    def __init__(
        self,
        provider: ChatProvider,
        monitor: Optional[StatsMonitor] = None,
        on_state: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        self._provider = provider
        self._monitor = monitor
        self._on_state = on_state

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._cmd = threading.Event()          # "wake" → "voice" geçiş sinyali
        self._cmd_response: Optional[str] = None  # geçişte söylenecek karşılama
        self._exit_flag = threading.Event()    # sesli oturumdan çıkış sinyali

        self._lock = threading.RLock()   # status() _set içinde de çağrılır → reentrant olmalı
        self._state = "off"
        self._session: Optional[str] = None   # listening|thinking|speaking
        self._mic: Optional[MicrophoneStream] = None
        self._vad: Optional[EnergyVAD] = None
        self._clap: Optional[ClapDetector] = None
        self._error: Optional[str] = None
        self._last_heard: str = ""
        self._last_reply: str = ""
        self._tts = TTSService()
        self._barge_in_enabled = database.get_setting("voice_barge_in", "1") == "1"

        self.settings = VoiceSettings.load()

    # ── Bağlama ──
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # ── Durum ──
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mic": self._state,
                "session": self._session,
                "mic_available": has_audio_backend(),
                "local_stt": stt_module.local_stt_available(),
                "clap_enabled": self.settings.clap_enabled,
                "clap_sensitivity": self.settings.clap_sensitivity,
                "wake_phrases": self.settings.wake_phrases,
                "exit_phrases": self.settings.exit_phrases,
                "last_heard": self._last_heard,
                "last_reply": self._last_reply,
                "error": self._error,
            }

    def _set(self, state: Optional[str] = None, session: Optional[str] = None,
             error: Optional[str] = None) -> None:
        """Durumu güncelle ve UI'ya (varsa WS broadcast) bildir."""
        with self._lock:
            if state is not None:
                self._state = state
            if session is not None or state == "wake":
                self._session = session if state != "wake" else None
            if error is not None:
                self._error = error
            snapshot = self.status()
        logger.debug("Voice state: %s / %s", self._state, self._session)
        if self._on_state and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._on_state(snapshot), self._loop)

    # ── Kontrol (REST'ten) ──
    def start(self) -> dict[str, Any]:
        """Mikrofonu açar ve wake+alkış dinlemeye başlar."""
        with self._lock:
            if self._state != "off":
                return self.status()
        if not has_audio_backend():
            self._set(error="Mikrofon bulunamadı (giriş cihazı yok).")
            return self.status()
        self._stop.clear()
        self._cmd.clear()
        self._thread = threading.Thread(target=self._run, name="jarvis-voice", daemon=True)
        self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        self._cmd.clear()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._mic is not None:
            self._mic.stop()
            self._mic = None
        stt_module.unload_local_model()
        self._set(state="off", session=None, error=None)
        return self.status()

    def start_voice_mode(self, reason: str = "manual",
                         response: Optional[str] = None) -> dict[str, Any]:
        """Sesli sohbet oturumu başlat (UI butonu, yazılı komut, alkış, wake).

        ``response``: oturum açılınca söylenecek karşılama; None → sessiz.
        """
        with self._lock:
            off = self._state == "off"
        self._exit_flag.clear()
        if response is not None:
            self._cmd_response = response
        self._cmd.set()
        if off:
            return self.start()  # thread yoksa önce kaldır; cmd işaretli → doğrudan voice
        database.audit("voice.mode_enter", detail=reason)
        return self.status()

    def exit_voice_mode(self, speak: bool = True) -> None:
        """UI "Çık" butonu — sesli oturumu kapatıp wake dinlemeye dön."""
        self._cmd.clear()
        self._exit_flag.set()   # sesli döngü bir sonraki adımda kırılır
        database.audit("voice.mode_exit", detail="ui_button")

    # ── Seslendirme (REST + hatırlatıcılar) ──
    def speak(self, text: str, owner_id: str = "local") -> bool:
        """Metni TTS ile oku; servis thread'i çalışmasa da kullanılabilir.

        Async TTS'i bağlı event loop üzerinde zamanlar ve bitmesini bekler
        (maks. 120 sn — çok uzun metinlerde UI kilitlenmesin).
        ``owner_id``: madde 7/14 — ses/hız tercihi sahibine göre okunur.
        """
        if not self._loop or not self._loop.is_running():
            logger.warning("TTS atlandı: event loop bağlı değil")
            return False
        future = asyncio.run_coroutine_threadsafe(
            self._tts.speak(text, owner_id), self._loop
        )
        try:
            return bool(future.result(timeout=120.0))
        except Exception:
            logger.exception("TTS okuma başarısız")
            return False

    def apply_settings(self) -> None:
        """Ayar değişikliklerini çalışan thread'e canlı uygula."""
        with self._lock:
            if self._clap is not None:
                self._clap.sensitivity = self.settings.clap_sensitivity

    # ── Segment kaydedici (VAD) ──
    def _record_segment(self, mic: MicrophoneStream, vad: EnergyVAD,
                        max_s: float, barge_in: bool = False,
                        clap: Optional[ClapDetector] = None) -> Optional[np.ndarray]:
        """VAD ile tek konuşma segmenti toplar; sessizlik/limit sonunda döner."""
        chunks: list[np.ndarray] = []
        voiced = False
        silence_ms = 0
        total_ms = 0
        limit_ms = int(max_s * 1000)

        while not self._stop.is_set() and not self._cmd.is_set():
            block = mic.read_block(timeout=0.25)
            if block is None:
                if voiced and silence_ms >= SEGMENT_SILENCE_S * 1000:
                    break
                silence_ms += 250
                total_ms += 250
                if total_ms >= limit_ms:
                    break
                continue

            if clap is not None and self.settings.clap_enabled:
                clap.feed(block, SAMPLE_RATE)

            e = rms(block)
            factor = BARGE_IN_FACTOR if barge_in else vad.threshold_factor
            is_speech = e > max(vad.noise_floor * factor, 1e-5)
            vad.update_noise(e, is_speech)

            total_ms += 100
            if is_speech:
                voiced = True
                silence_ms = 0
                chunks.append(block)
            elif voiced:
                silence_ms += 100
                chunks.append(block)  # sessizliği de ekle (doğal bitiş)
                if silence_ms >= SEGMENT_SILENCE_S * 1000:
                    break
            if total_ms >= limit_ms:
                break

        if not chunks:
            return None
        pcm = np.concatenate(chunks)
        if pcm.size < int(SAMPLE_RATE * SEGMENT_MIN_S):
            return None
        return pcm

    # ── Async köprü ──
    def _run_async(self, coro: Any) -> Any:
        """Ana event loop'ta coroutine çalıştır ve sonucu bekle."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("Event loop bağlı değil (bind_loop çağrılmalı).")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def _transcribe(self, pcm: np.ndarray) -> str:
        try:
            result = self._run_async(stt_module.transcribe(pcm, SAMPLE_RATE))
        except Exception:
            logger.exception("STT çağrısı başarısız")
            return ""
        if not result.ok:
            if result.error:
                logger.warning("STT: %s", result.error)
            return ""
        self._last_heard = result.text
        return result.text.strip()

    def _speak_with_barge_in(self, text: str, mic: MicrophoneStream,
                             vad: EnergyVAD) -> None:
        """TTS oynatırken mikrofonu dinler; kullanıcı konuşursa susar (5.4)."""
        if not text:
            return
        if not self._barge_in_enabled:
            self._run_async(self._tts.speak(text))
            return
        future = asyncio.run_coroutine_threadsafe(self._tts.speak(text), self._loop)
        threshold = max(vad.noise_floor, 1e-6) * BARGE_IN_FACTOR
        while not future.done() and not self._stop.is_set():
            block = mic.read_block(timeout=0.1)
            if block is None:
                continue
            if rms(block) > threshold:
                logger.info("Barge-in: kullanıcı konuşmaya başladı, JARVIS susuyor")
                self._tts.cancel()
                break
        try:
            future.result(timeout=5.0)
        except Exception:
            future.cancel()

    def _wake_turn(self, mic: MicrophoneStream, vad: EnergyVAD,
                   clap: ClapDetector) -> tuple[str, str]:
        """('none', '') | ('wake', yanıt) döner; alkış da burada beslenir."""
        pcm = self._record_segment(mic, vad, max_s=4.0, clap=clap)
        if pcm is None:
            return "none", ""
        # Wake algılama TAMAMEN YEREL — küçük Whisper, internet yok (5.4)
        try:
            result = stt_module.transcribe_local(pcm, SAMPLE_RATE)
        except Exception:
            logger.exception("Yerel STT başarısız")
            return "none", ""
        text = result.text.strip()
        if not text:
            return "none", ""
        self._last_heard = text
        logger.debug("Wake dinleme duydu: %r", text)
        for phrase in self.settings.wake_phrases:
            if textmatch.match_phrase(text, phrase):
                response = self.settings.wake_responses.get(
                    phrase, "Sizi dinliyorum efendim."
                )
                return "wake", response
        return "none", ""

    # ── Ana döngü ──
    def _run(self) -> None:
        """Ses thread'i: wake dinleme ↔ sesli oturum durum makinesi."""
        logger.info("Voice thread başladı")
        try:
            mic = MicrophoneStream()
            mic.start()
        except MicrophoneError as exc:
            self._set(error=str(exc))
            logger.error("Mikrofon açılamadı: %s", exc)
            return
        self._mic = mic
        vad = EnergyVAD()
        clap = ClapDetector(
            sensitivity=self.settings.clap_sensitivity,
            on_double_clap=self._on_clap,
        )
        self._clap = clap

        self._set(state="wake")
        try:
            while not self._stop.is_set():
                if self._cmd.is_set():
                    self._cmd.clear()
                    response = self._cmd_response
                    self._cmd_response = None
                    self._exit_flag.clear()
                    self._voice_session(mic, vad, clap, greeting=response)
                else:
                    kind, response = self._wake_turn(mic, vad, clap)
                    if kind == "wake":
                        self._cmd_response = None
                        self._voice_session(mic, vad, clap, greeting=response)
        finally:
            try:
                mic.stop()
            except Exception:
                pass
            self._mic = None
            self._clap = None
            logger.info("Voice thread sonlandı")

    def _on_clap(self) -> None:
        """Çift alkış — ses thread'inden çağrılır (feed sırasında)."""
        logger.info("Çift alkış → sesli mod")
        database.audit("voice.double_clap")
        try:
            bring_jarvis_to_front()
        except Exception:
            logger.exception("Pencere öne getirilemedi")
        self._cmd_response = CLAP_RESPONSE
        self._cmd.set()

    # ── Sesli oturum: dinle → düşün → konuş ──
    def _voice_session(self, mic: MicrophoneStream, vad: EnergyVAD,
                       clap: ClapDetector, greeting: Optional[str] = None) -> None:
        logger.info("Sesli oturum açıldı")
        self._set(state="voice", session="listening")
        if greeting:
            self._set(session="speaking")
            self._speak_with_barge_in(greeting, mic, vad)
            if self._stop.is_set():
                return
        idle_ms = 0

        while not self._stop.is_set() and not self._exit_flag.is_set():
            if self._cmd.is_set():
                # Oturum zaten açıkken yeni tetik (ör. yazılı "sesli moda geç")
                self._cmd.clear()
                self._cmd_response = None
                idle_ms = 0
                continue

            self._set(session="listening")
            pcm = self._record_segment(mic, vad, max_s=SEGMENT_MAX_S, clap=clap)
            if pcm is None:
                # VAD sessizlikte limit dolana dek bekler → ~SEGMENT_MAX_S
                idle_ms += int(SEGMENT_MAX_S * 1000)
                if idle_ms >= 45_000:
                    logger.info("Sesli oturum boşta süresi doldu → wake")
                    break
                continue

            idle_ms = 0
            text = self._transcribe(pcm)
            if not text:
                continue
            database.audit("voice.heard", detail=text[:200])

            # Çıkış komutu (5.4: sesli çıkış)
            if any(textmatch.match_phrase(text, p) for p in self.settings.exit_phrases):
                self._speak_with_barge_in("Sesli modu kapatıyorum efendim.", mic, vad)
                break

            self._set(session="thinking")
            try:
                # Madde 1/3: sesli mod da sahibinin dil ve mod tercihini kullanır.
                _prefs = database.get_user_settings("local")
                chat_result = self._run_async(
                    run_chat(
                        text,
                        self._provider,
                        self._monitor,
                        source="voice",
                        owner_id="local",
                        language=_prefs.get("language") or "tr",
                        mode=_prefs.get("conversation_mode") or "adaptive",
                    )
                )
                reply = chat_result.get("reply", "")
            except Exception:
                logger.exception("Sesli sohbet çekirdeği hata verdi")
                reply = "Üzgünüm efendim, bir sorun oluştu."
            if not reply:
                reply = "Anlayamadım efendim, tekrar eder misiniz?"
            self._last_reply = reply

            self._set(session="speaking")
            self._speak_with_barge_in(reply, mic, vad)

        self._set(state="wake", session=None)
        logger.info("Sesli oturum kapandı → wake dinleme")

