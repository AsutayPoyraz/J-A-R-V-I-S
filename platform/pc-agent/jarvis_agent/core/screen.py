"""Bölüm E (madde 9): ekran analizi ve sınırlı GUI otomasyonu.

Güvenlik notları:
- Uygulama açma YALNIZCA sabit beyaz listeden çalışır; kullanıcı girdisi
  asla kabuğa aktarılmaz (injection yüzeyi yok).
- Klavye/fare otomasyonu (pyautogui) yalnızca JARVIS_GUI_AUTOMATION=1 iken
  çalışır; varsayılan KAPALIDIR.
- Ekran analizi, yapılandırılmış LLM sağlayıcısına (OpenAI uyumlu vision)
  JPEG ekran görüntüsü gönderir; anahtar yoksa zarifçe ``available=False``
  döner.
"""
from __future__ import annotations

import base64
import io
import logging
import subprocess
from typing import Any, Optional

import httpx

from .. import config

logger = logging.getLogger("jarvis.screen")

# Madde 9: izin verilen uygulamalar — değerler sabittir, kullanıcı girdisi taşımaz.
APP_COMMANDS: dict[str, str] = {
    "chrome": "start chrome",
    "edge": "start msedge",
    "notepad": "start notepad",
    "calculator": "start calc",
    "explorer": "start explorer",
    "files": "start explorer",
    "paint": "start mspaint",
}


def list_apps() -> list[str]:
    """Beyaz liste anahtarlarını sıralı döndürür."""
    return sorted(APP_COMMANDS)


def _popen(cmd: str) -> None:
    """Beyaz liste komutunu başlatır (testlerde mock'lanır)."""
    subprocess.Popen(cmd, shell=True)  # noqa: S602 — cmd yalnızca sabit listeden gelir


def open_app(name: str) -> dict[str, Any]:
    """Beyaz listedeki bir uygulamayı başlatır; bilinmeyen ad ValueError."""
    key = (name or "").strip().lower()
    if key not in APP_COMMANDS:
        raise ValueError(f"uygulama beyaz listede yok: {key}")
    _popen(APP_COMMANDS[key])
    logger.info("Uygulama başlatıldı: %s", key)
    return {"opened": key}


def capture_screenshot_jpeg() -> Optional[bytes]:
    """Tam ekran JPEG görüntüsü (Pillow ImageGrab); alınamazsa None."""
    try:
        from PIL import ImageGrab
    except ImportError:
        logger.warning("Pillow kurulu değil; ekran görüntüsü alınamıyor")
        return None
    try:
        img = ImageGrab.grab()
    except Exception:
        logger.exception("Ekran görüntüsü alınamadı")
        return None
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _vision_request(image_b64: str, question: str, model: str) -> str:
    """OpenAI uyumlu vision sohbet çağrısı (sağlayıcıya göre taban URL seçilir)."""
    provider = config.active_provider()
    api_key = {"groq": config.GROQ_API_KEY, "openai": config.OPENAI_API_KEY}.get(provider, "")
    if not api_key:
        raise RuntimeError("no_api_key")
    base = "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.openai.com/v1"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": question},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 600,
                },
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("vision_network_error") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"vision_http_{resp.status_code}")
    try:
        return str(resp.json()["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError("vision_parse_error") from exc


def analyze_screen(
    question: str | None = "Bu ekranda ne görüyorsun? Kısa ve maddeler halinde özetle.",
) -> dict[str, Any]:
    """Ekranı yakalar ve vision modeliyle analiz eder (madde 9)."""
    question = (question or "").strip() or "Bu ekranda ne görüyorsun? Kısa ve maddeler halinde özetle."
    raw = capture_screenshot_jpeg()
    if raw is None:
        return {"available": False, "reason": "capture_unavailable"}
    model = config.VISION_MODEL or config.active_model()
    image_b64 = base64.b64encode(raw).decode("ascii")
    try:
        analysis = _vision_request(image_b64, question, model)
    except RuntimeError as exc:
        logger.warning("Ekran analizi başarısız: %s", exc)
        return {"available": False, "reason": str(exc)}
    return {"available": True, "analysis": analysis, "model": model}


# ── Sınırlı GUI otomasyonu (varsayılan KAPALI — madde 9 KISMEN notu) ─────────

def _automation_ready() -> None:
    """Otomasyon önkoşulları; değilse RuntimeError (uç bunu 409'a çevirir)."""
    if not config.GUI_AUTOMATION:
        raise RuntimeError("automation_disabled")
    try:
        import pyautogui  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("pyautogui_missing") from exc


def scroll(delta: int = -600) -> dict[str, Any]:
    """Aktif pencerede kaydırma (negatif = aşağı)."""
    _automation_ready()
    import pyautogui

    pyautogui.scroll(int(delta))
    return {"scrolled": int(delta)}


def type_text(text: str) -> dict[str, Any]:
    """Aktif pencereye metin yazar (en fazla 200 karakter)."""
    _automation_ready()
    import pyautogui

    pyautogui.typewrite(text[:200], interval=0.02)
    return {"typed": len(text[:200])}
