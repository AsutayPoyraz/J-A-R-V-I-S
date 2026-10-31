"""Kamera servisi — OpenCV ile açma/kapama ve fotoğraf çekme.

Güvenlik: kamera yalnızca kullanıcının açık isteğiyle açılır (UI'daki Open
butonu); arayüzde her zaman görünür bir durum göstergesi (LIVE) vardır.
"""
from __future__ import annotations

import base64
import datetime
import logging
import os
import platform
import threading
from typing import Any, Optional

logger = logging.getLogger("jarvis.camera")

try:
    import cv2  # type: ignore
except ImportError:  # opencv yüklü değil — modül düzgün biçimde devre dışı kalır
    cv2 = None


class CameraError(RuntimeError):
    """Kamera işlemi başarısız."""


_install_lock = threading.Lock()
_install_progress: dict[str, Any] = {"running": False, "last_error": "", "done": False}


def opencv_installed() -> bool:
    """opencv-python import edilebiliyor mu? (her çağrıda taze kontrol)."""
    if cv2 is not None:
        return True
    try:
        import importlib

        importlib.import_module("cv2")
        return True
    except Exception:  # noqa: BLE001
        return False


def install_progress() -> dict[str, Any]:
    return dict(_install_progress)


def install_opencv() -> dict[str, Any]:
    """Özellik 3: pip ile opencv-python kurar (JARVIS_CAMERA_AUTO_INSTALL).

    Kurulum başarısızsa JARVIS_CAMERA_DISABLED=1 geçici set edilir ve
    kullanıcıya manuel komut döner. Bloklayan çağrı — endpoint'te thread'de
    çalıştırılır.
    """
    import os
    import subprocess
    import sys

    if opencv_installed():
        return {"ok": True, "detail": "opencv-python zaten kurulu."}
    with _install_lock:
        if _install_progress.get("running"):
            return {"ok": False, "detail": "Kurulum zaten çalışıyor."}
        _install_progress.update({"running": True, "last_error": "", "done": False})
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "opencv-python"],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0 and opencv_installed():
                _install_progress.update({"running": False, "done": True})
                return {"ok": True, "detail": "opencv-python kuruldu."}
            error = (result.stderr or "pip başarısız")[-400:]
        except (subprocess.TimeoutExpired, OSError) as exc:
            error = f"Kurulum çalıştırılamadı: {exc}"
        # Başarısızlık: oturum için kamerayı devre dışı bırak + net hata döndür.
        os.environ["JARVIS_CAMERA_DISABLED"] = "1"
        _install_progress.update({"running": False, "done": True, "last_error": error})
        return {
            "ok": False,
            "detail": error,
            "manual_command": "pip install opencv-python",
        }


class CameraService:
    """Tek kamera cihazını yöneten, iş parçacığı güvenli servis."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cap: Optional[Any] = None
        self._width = 0
        self._height = 0

    # ── Yardımcılar ──
    @staticmethod
    def _disabled_by_env() -> bool:
        return os.getenv("JARVIS_CAMERA_DISABLED", "").strip().lower() in ("1", "true", "yes")

    def _ensure_cv2(self) -> None:
        if cv2 is None:
            raise CameraError("opencv-python kurulu değil: pip install opencv-python")

    def _capture_backend(self) -> int:
        # Windows'ta DSHOW arka ucu kamerayı çok daha hızlı açar.
        if platform.system() == "Windows" and cv2 is not None:
            try:
                return int(cv2.CAP_DSHOW)
            except Exception:  # pragma: no cover
                return 0
        return 0

    # ── Genel API ──
    def open(self, index: int = 0) -> dict[str, Any]:
        with self._lock:
            if self._disabled_by_env():
                raise CameraError("Kamera bu oturumda devre dışı (JARVIS_CAMERA_DISABLED=1).")
            self._ensure_cv2()
            if self._cap is not None:
                return self.status()

            cap = cv2.VideoCapture(index, self._capture_backend())
            if not cap.isOpened():
                cap.release()
                raise CameraError(f"Kamera açılamadı (index {index}). Bağlı bir kamera var mı?")
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                raise CameraError("Kameradan görüntü alınamadı.")
            self._cap = cap
            self._height, self._width = frame.shape[:2]
            logger.info("Kamera açıldı: %sx%s", self._width, self._height)
            return self.status()

    def close(self) -> dict[str, Any]:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("Kamera kapatıldı")
            return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            live = self._cap is not None
            return {
                "status": "live" if live else "off",
                "width": self._width if live else None,
                "height": self._height if live else None,
                # Özellik 3.2: zenginleştirilmiş durum alanları
                "opencv_installed": opencv_installed(),
                "camera_available": live or (opencv_installed() and not self._disabled_by_env()),
                "disabled_by_env": self._disabled_by_env(),
                "error": "" if opencv_installed() else (
                    "opencv-python kurulu değil: pip install opencv-python"
                ),
                "install_progress": install_progress(),
            }

    def capture(self) -> dict[str, Any]:
        with self._lock:
            if self._disabled_by_env():
                raise CameraError("Kamera bu oturumda devre dışı (JARVIS_CAMERA_DISABLED=1).")
            if self._cap is None:
                raise CameraError("Kamera kapalı; önce açın.")
            ok, frame = self._cap.read()
            if not ok or frame is None:
                raise CameraError("Fotoğraf çekilemedi; kamera yanıt vermiyor.")
            success, buffer = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )
            if not success:
                raise CameraError("Görüntü JPEG'e dönüştürülemedi.")
            encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
            return {
                "image": f"data:image/jpeg;base64,{encoded}",
                "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
