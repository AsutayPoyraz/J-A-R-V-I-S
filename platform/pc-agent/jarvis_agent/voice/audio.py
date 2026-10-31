"""Mikrofon yakalama — sounddevice tabanlı, donanım yokluğunda zarif degrade.

Tüm ses katmanı 16 kHz mono float32 örnekleriyle çalışır (STT için
Whisper'ın beklediği biçim).
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger("jarvis.voice.audio")

SAMPLE_RATE = 16000
BLOCK_SIZE = 1600  # 100 ms — VAD için yeterince ince, CPU dostu
AUDIO_QUEUE_MAX_BLOCKS = 50  # En fazla 5 saniyelik ses; tüketici geride kalırsa düşür.

try:
    import sounddevice as sd  # type: ignore
    _SD_AVAILABLE = True
except (ImportError, OSError):
    sd = None  # type: ignore
    _SD_AVAILABLE = False


class MicrophoneError(RuntimeError):
    """Mikrofon açılamadı veya donanım yok."""


def has_audio_backend() -> bool:
    """sounddevice + en az bir giriş cihazı var mı?

    JARVIS_VOICE_DISABLED=1 ile tamamen kapatılabilir (test/CI ortamı).
    """
    import os

    if os.getenv("JARVIS_VOICE_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return False
    if not _SD_AVAILABLE:
        return False
    try:
        return any(
            d["max_input_channels"] > 0 for d in sd.query_devices()
        )
    except Exception:
        return False


def list_input_devices() -> list[dict]:
    """Özellik 14.3: sistemdeki tüm ses cihazları (giriş/çıkış ayrıntısı)."""
    if not _SD_AVAILABLE:
        return []
    try:
        raw = sd.query_devices()
    except Exception:
        return []
    devices = []
    try:
        default_input = int(sd.default.device[0])
    except Exception:  # noqa: BLE001
        default_input = -1
    for index, dev in enumerate(raw):
        devices.append(
            {
                "index": index,
                "name": str(dev.get("name") or ""),
                "max_input_channels": int(dev.get("max_input_channels") or 0),
                "max_output_channels": int(dev.get("max_output_channels") or 0),
                "default_samplerate": float(dev.get("default_samplerate") or 0),
                "is_default_input": index == default_input,
            }
        )
    return devices


def resolve_input_device() -> Optional[int]:
    """JARVIS_AUDIO_INPUT_DEVICE override'ını çözer (index veya isim).

    Özellik 14.2: hiçbir giriş cihazı yoksa JARVIS_VOICE_DISABLED=1 geçici
    set edilir ve MicrophoneError fırlatılır.
    """
    import os

    devices = list_input_devices()
    inputs = [d for d in devices if d["max_input_channels"] > 0]
    if not inputs:
        if _SD_AVAILABLE:
            os.environ["JARVIS_VOICE_DISABLED"] = "1"
        raise MicrophoneError(
            "Bu cihazda mikrofon (giriş) bulunamadı. JARVIS_VOICE_DISABLED=1 ayarlandı."
        )
    override = os.getenv("JARVIS_AUDIO_INPUT_DEVICE", "").strip()
    if not override:
        default = [d for d in inputs if d["is_default_input"]]
        return default[0]["index"] if default else inputs[0]["index"]
    if override.isdigit():
        index = int(override)
        if any(d["index"] == index and d["max_input_channels"] > 0 for d in inputs):
            return index
        raise MicrophoneError(
            f"JARVIS_AUDIO_INPUT_DEVICE={override} geçerli bir giriş cihazı değil."
        )
    lowered = override.lower()
    for dev in inputs:
        if lowered in dev["name"].lower():
            return dev["index"]
    raise MicrophoneError(
        f"İsimle eşleşen giriş cihazı bulunamadı: {override}"
    )


class MicrophoneStream:
    """Arka plan iş parçacığında blok okuyan, kuyruk temelli mikrofon akışı."""

    def __init__(self, device: Optional[int] = None) -> None:
        self.device = device
        self._stream = None
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=AUDIO_QUEUE_MAX_BLOCKS)
        self._lock = threading.Lock()
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            if not _SD_AVAILABLE:
                raise MicrophoneError(
                    "sounddevice kurulu değil (pip install sounddevice)."
                )
            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=BLOCK_SIZE,
                    device=self.device,
                    callback=self._on_block,
                )
                self._stream.start()
                self._active = True
                logger.info("Mikrofon akışı başladı (16 kHz mono)")
            except Exception as exc:
                self._active = False
                raise MicrophoneError(f"Mikrofon açılamadı: {exc}") from exc

    def stop(self) -> None:
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._active = False
            # kuyruğu boşalt
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def _on_block(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            logger.debug("Ses akışı uyarısı: %s", status)
        try:
            self._queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(indata[:, 0].copy())
            except queue.Empty:
                pass

    def read_block(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Bir blok (100 ms) okur; timeout'ta None döner."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
