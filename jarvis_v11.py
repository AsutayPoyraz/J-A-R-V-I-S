#!/usr/bin/env python3
"""
J.A.R.V.I.S. v11.0 'Apex'
Just A Rather Very Intelligent System
Stark Industries — 2026 Edition

v9 Yenilikleri:
  • FinCore: Canlı döviz, borsa, teknik analiz (MA/RSI)
  • Daily Briefing: Haber özetleme motoru
  • LongMemory: Kullanıcı profili + context manager
  • CoreWidget: Fütüristik renk geçişli animasyon (data-flow efekti)
  • TTS: Profesyonel finans tonlaması
  • Güçlü exception handling tüm API bağlantıları için
"""

import asyncio
import datetime
import importlib.util
import json
import math
import os
import random
import re
import shutil
import smtplib
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from automation_engine import AutomationEngine
from config import (
    APP_DISPLAY_VERSION,
    CONTACTS_FILE,
    DB_PATH,
    EPSON_EMAIL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OWM_API_KEY,
    PDF_STORE,
    PROFILE_FILE,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
    STYLE_PATH,
    safe_read_json,
    safe_write_json,
)
from curriculum import (
    curriculum_context,
    estimate_grade,
    is_education_query,
    subject_of,
    verify_answer,
)
from device_prefs import (
    get_local_ip,
    get_machine_id,
    load_device_pref,
    save_device_pref,
)
from file_converter import convert_file
from intent_detection import requires_atlas
from logger_setup import logger
from overlay_ui import AtlasOverlay
from platform_service import get_platform_service, maybe_show_permissions_guide
from presentation_builder import PresentationResult, build_presentation
from prompt_architect import build_fallback_prompt, generate_prompt, is_prompt_request
from research_engine import MODES, get_research_engine, parse_requested_pages
from research_ui import RoundCountdownWidget, should_show_countdown
from services.ai_client import (
    create_gemini_client,
    create_groq_client,
    gemini_grounded_search,
)
from services.ai_engine import AIEngine as _ServiceAIEngine
from services.ai_intent import AIRequestType, classify_ai_request
from services.answer_feedback import format_answer_feedback
from services.atlas_memory import add_fact as atlas_memory_add_fact
from services.atlas_memory import build_context as atlas_memory_build_context
from services.atlas_memory import delete_source as atlas_memory_delete_source
from services.atlas_memory import index_document as atlas_memory_index_document
from services.atlas_memory import list_sources as atlas_memory_list_sources
from services.atlas_memory import search as atlas_memory_search
from services.browser import find_local_item, open_google, open_youtube, system_summary
from services.computer_control import (
    active_window_title,
    analyze_screen,
    capture_screen,
    click_screen,
    edit_text_file,
    list_open_windows,
    move_mouse,
    open_allowed_app,
    open_windows_settings,
    preview_text_edit,
    system_processes,
    type_text,
    undo_last_text_edit,
)
from services.currency import (
    convert_currency as _convert_currency,
)
from services.currency import (
    format_currency_board as _format_currency_board,
)
from services.currency import (
    get_exchange_rates as _get_exchange_rates,
)
from services.currency import (
    is_currency_query as _is_currency_query,
)
from services.currency import (
    parse_currency_query as _parse_currency_query,
)
from services.data_backup import create_backup, restore_backup
from services.database import (
    db_claim_due_reminders,
    db_clear_all_history,
    db_clear_session,
    db_get_messages,
    db_get_sessions,
    db_init,
    db_log_finance,
    db_new_session,
    db_save_msg,
    db_search_messages,
)
from services.local_context import extract_context_query, format_local_context
from services.network import (
    DEFAULT_HTTP_TIMEOUT,
    HTTP_SESSION,
    get_weather,
)
from services.offline_commands import handle_offline_command
from services.performance import detect_low_resource_mode
from services.permissions import (
    CATEGORY_LABELS,
    ActionCategory,
    PermissionManager,
    category_for_request,
)
from services.routines import (
    add_daily_briefing,
    claim_due_routines,
    list_routines,
    remove_routine,
)
from services.skill_registry import create_builtin_skill_registry
from services.startup_diagnostics import format_startup_diagnostics
from services.task_center import StepStatus, TaskCenter, TaskStatus
from services.task_planner import build_task_plan, format_task_plan
from services.update_check import check_for_update, is_update_check_configured
from services.user_data import (
    LongMemory,
)
from services.user_data import (
    settings_load as _settings_load,
)
from services.user_data import (
    settings_save as _settings_save,
)
from services.verification import CommandVerifier, VerificationResult
from services.web_automation import (
    close_marketplace_browser,
    marketplace_search,
)
from services.web_automation import (
    interact as web_interact,
)
from services.web_automation import (
    open_url as open_web_url,
)
from services.whatsapp import send_message as send_whatsapp_message
from status_border import AppState, StatusBorderWidget, StatusColorController
from troubleshoot_flow import FlowState, create_flow
from window_manager import ActiveWindow, WindowManager

REMOTE_CONTEXT_ENABLED = os.getenv("JARVIS_SHARE_CONTEXT", "").strip().lower() in {
    "1", "true", "yes", "on"
}

def _optional_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False

# ── Qt (PySide6 is required by the application and its UI modules) ────────
from PySide6.QtCore import QPointF, Qt, QThread, QTimer, QUrl
from PySide6.QtCore import Signal as pyqtSignal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except ImportError:
    QMediaPlayer = QAudioOutput = None
PYQT_OK = True

# ── Opsiyonel kütüphaneler ────────────────────────────────────────────────
try:
    import psutil; PSUTIL_OK = True
except Exception:
    psutil = None
    PSUTIL_OK = False

try:
    import requests; REQUESTS_OK = True
except Exception: REQUESTS_OK = False

GROQ_OK = _optional_module_available("groq")
GTTS_OK = _optional_module_available("gtts")

try:
    import speech_recognition as sr; SR_OK = True
except Exception: SR_OK = False

try:
    from bs4 import BeautifulSoup; BS4_OK = True
except Exception: BS4_OK = False

fitz = None
PYMUPDF_OK = (
    _optional_module_available("pymupdf")
    or _optional_module_available("fitz")
)
WA_OK = _optional_module_available("pywhatkit")

# Finance dependencies are discovered without importing their large stacks.
try:
    YFINANCE_OK = importlib.util.find_spec("yfinance") is not None
except (ImportError, ValueError):
    YFINANCE_OK = False

os.makedirs(PDF_STORE, exist_ok=True)

# ── Renkler (v9: Apex palette - daha derin ve canlı) ──────────────────────
C = {
    "bg": "#050810", "bg2": "#090d16", "panel": "#0d1220",
    "border": "#1a2540", "blue": "#00b4ff", "orange": "#ff8800",
    "red": "#ff1a44", "green": "#00ffaa", "dim": "#304060",
    "text": "#c8d8f0", "subtext": "#4a6080",
    # v9: Yeni finans renkleri
    "gold": "#ffd700", "purple": "#9944ff", "cyan": "#00ffee",
    "profit": "#00ff88", "loss": "#ff3355",
}

# ── Ayarlar ───────────────────────────────────────────────────────────────
def safe_user_text(value: str | None, max_len: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = text[:max_len]
    return re.sub(r"[\x00-\x1f\x7f]", "", text)


def safe_path_under_root(path: str | os.PathLike, root: str | os.PathLike) -> Path | None:
    try:
        candidate = Path(path).expanduser().resolve(strict=False)
        base = Path(root).expanduser().resolve(strict=False)
        if candidate == base or base in candidate.parents:
            return candidate
        return None
    except (TypeError, ValueError, OSError):
        return None


def safe_file_target(path: str | os.PathLike, root: str | os.PathLike) -> Path | None:
    """Belirli bir kökün altında kalan dosya veya dizin yolunu doğrular."""
    candidate = safe_path_under_root(path, root)
    if candidate is None:
        return None
    return candidate


SETTINGS_LOCK = threading.RLock()
PROFILE_LOCK = threading.RLock()


def settings_load() -> dict:
    with SETTINGS_LOCK:
        return _settings_load()


def settings_save(s: dict):
    with SETTINGS_LOCK:
        _settings_save(s)


def profile_update(path: str, value):
    """Profil değişiklikleri için tekil kilit sağlar; eşzamanlı yazımları önler."""
    with PROFILE_LOCK:
        PROFILE.set(path, value)


def _machine_short() -> str:
    """Günlük için kısa makine kimliği (Özellik 4 tanılama)."""
    return get_machine_id()[:8]


def get_clean_client():
    """Groq istemcisini güvenli şekilde hazırlar."""
    if not GROQ_OK:
        return None
    api_key = (os.getenv("GROQ_API_KEY") or os.getenv("JARVIS_GROQ_API_KEY") or GROQ_API_KEY or "").strip()
    if not api_key:
        return None
    try:
        return create_groq_client(api_key)
    except Exception as exc:
        logger.warning("Groq istemcisi oluşturulamadı: %s", type(exc).__name__)
        return None


def _research_summarize(query: str, instruction: str, context: str) -> str:
    """Özellik 10: Groq ile kaynak derlemesi (yoksa boş → şablon fallback)."""
    if not context:
        return ""
    client = get_clean_client()
    if not client:
        return ""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"Soru: {query}\n\nKaynaklar:\n{context}"},
            ],
            max_tokens=1024,
            temperature=0.4,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("[Research] LLM özet alınamadı: %s", exc)
        return ""


def _prompt_llm(task: str, instruction: str, context: str) -> str:
    """Özellik 9: Prompt Mimarı için Groq çağrısı (yoksa boş → şablon)."""
    client = get_clean_client()
    if not client:
        return ""
    try:
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": task},
            ],
            max_tokens=1600,
            temperature=0.6,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("[PromptArchitect] LLM yok: %s", exc)
        return ""


SETTINGS = settings_load()

# Global profil nesnesi
PROFILE = LongMemory()

# ── JARVIS Kişiliği (v9: 2026 güncellemeli) ───────────────────────────────
def build_persona() -> str:
    name = PROFILE.get("name", "Efendim")
    tone = PROFILE.get("preferred_tone", "casual")
    tone_note = "TDK uyumlu İstanbul Türkçesi kullan, resmi ve profesyonel ol." if tone == "formal" else \
                "Doğal, samimi ve insan gibi konuş. Yapay zeka gibi resmi kalıplar kullanma."
    return f"""Sen J.A.R.V.I.S. v{APP_DISPLAY_VERSION} 'Apex' olarak çalışıyorsun. Yıl 2026.
Kullanıcıya \"{name}\" diye hitap et. Türkçe konuş.
ÖNEMLİ: {tone_note}
Kısa ve öz ol. Bazen hafifçe espri yapabilirsin.
Emoji kullanma. Veri odaklı konuş.

YENİ v9 YETENEKLERİN:
- Canlı döviz kurları (USD, EUR, GBP ve diğerleri)
- Anlık hisse senedi fiyatları (BIST, NYSE, NASDAQ)
- Teknik analiz: Hareketli ortalama ve RSI (YATırım tavsiyesi değildir)
- Günlük brifing: Özetlenmiş haberler
- Uzun süreli bellek: Kullanıcı profilini hatırlama
- Favori hisse takibi

ESKİ YETENEKLERİN (hepsi aktif):
- Sohbet, analiz, soru cevaplama
- Hava durumu, saat, takvim
- İnternet hız testi, WhatsApp
- PDF okuma, kod yazma
- Sistem takibi ve temizliği
- TC kanunları ve sağlık bilgisi

DİKKAT — ARAMA KURALLARI:
1. Kullanıcının doğal dil komutunu doğrudan arama kutusuna YAZMA.
   Önce "search_on_site" tool'unu çağır, temiz anahtar kelimeyi "query" alanına koy.
   Örnek: "sahibindende bmw bakalım bana" → search_on_site(site="sahibinden.com", query="bmw")
2. Özel isimleri (sanatçı, şarkı, marka) ASLA İngilizceye çevirme veya "düzeltme".
   "uzi" → "uzi" (NOT "uzun", NOT "Uzi rapper").
3. Kullanıcının kastettiği anahtar kelimeyi çıkart, kendi yorum/varsayımını EKLEME."""

# ══════════════════════════════════════════════════════════════════════════
# VERİTABANI (v9: kullanıcı profili tablosu eklendi)
# ══════════════════════════════════════════════════════════════════════════
def _db_execute(query: str, params: tuple = (), fetch: bool = False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(query, params)
        if fetch:
            rows = cur.fetchall()
            result = [dict(row) for row in rows]
        else:
            con.commit()
            result = cur.lastrowid
        return result
    finally:
        con.close()



# ══════════════════════════════════════════════════════════════════════════
# HAVA DURUMU
# ══════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════
# DONANIM
# ══════════════════════════════════════════════════════════════════════════
def get_hw() -> dict:
    if not PSUTIL_OK:
        return {"cpu": 0, "ram": 0, "bat": None, "charging": False, "ram_gb": 0}
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        bat = psutil.sensors_battery()
        return {
            "cpu": cpu, "ram": mem.percent,
            "ram_gb": round(mem.used / 1024**3, 1),
            "bat": round(bat.percent) if bat else None,
            "charging": bat.power_plugged if bat else False,
        }
    except Exception:
        return {"cpu": 0, "ram": 0, "bat": None, "charging": False, "ram_gb": 0}

# ══════════════════════════════════════════════════════════════════════════
# v9: FİNANS MODÜLܼ (FinCore)
# ══════════════════════════════════════════════════════════════════════════

def get_exchange_rates(base: str = "USD") -> dict:
    return _get_exchange_rates(base)

def is_currency_query(text: str) -> bool:
    return _is_currency_query(text)


def convert_currency(amount: float, from_cur: str, to_cur: str) -> str:
    return _convert_currency(amount, from_cur, to_cur, get_exchange_rates)

def parse_currency_query(text: str) -> str | None:
    return _parse_currency_query(text, get_exchange_rates)

def get_multi_currency_board() -> str:
    currencies = PROFILE.get("favorite_currencies", ["USD", "EUR", "GBP"])
    return _format_currency_board(currencies, get_exchange_rates)

# ── Hisse Senedi Modülü ───────────────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """yfinance ile anlık hisse fiyatı al."""
    if not YFINANCE_OK:
        return {"error": "yfinance kurulu değil: pip install yfinance"}
    try:
        import yfinance as yf

        t = ticker.upper().strip()
        stock = yf.Ticker(t)
        info = stock.info
        hist = stock.history(period="5d")
        if hist.empty:
            return {"error": f"'{t}' için veri bulunamadı. Ticker doğru mu?"}

        current = float(hist["Close"].iloc[-1])
        prev    = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
        change  = current - prev
        change_pct = (change / prev * 100) if prev else 0

        db_log_finance(t, current, info.get("currency", "?"))

        return {
            "ticker":     t,
            "name":       info.get("longName", t),
            "price":      current,
            "change":     change,
            "change_pct": change_pct,
            "currency":   info.get("currency", "?"),
            "market":     info.get("exchange", "?"),
            "volume":     info.get("regularMarketVolume", 0),
            "pe":         info.get("trailingPE", None),
            "52w_high":   info.get("fiftyTwoWeekHigh", None),
            "52w_low":    info.get("fiftyTwoWeekLow", None),
        }
    except Exception as e:
        return {"error": f"Hisse verisi alınamadı: {e}"}

def format_stock_result(data: dict) -> str:
    if "error" in data:
        return data["error"]
    sign = "+" if data["change"] >= 0 else ""
    trend = "▲" if data["change"] >= 0 else "▼"
    lines = [
        f"{'='*40}",
        f"  {data['ticker']} — {data['name'][:28]}",
        f"{'='*40}",
        f"  Fiyat:      {data['price']:.2f} {data['currency']}",
        f"  Değişim:    {sign}{data['change']:.2f} ({sign}{data['change_pct']:.2f}%) {trend}",
    ]
    if data.get("52w_high"):
        lines.append(f"  52H Yüksek: {data['52w_high']:.2f}")
    if data.get("52w_low"):
        lines.append(f"  52H Düşük:  {data['52w_low']:.2f}")
    if data.get("pe"):
        lines.append(f"  F/K Oranı:  {data['pe']:.2f}")
    lines.append(f"  Borsa:      {data['market']}")
    lines.append(f"{'='*40}")
    lines.append(f"  Güncelleme: {datetime.datetime.now().strftime('%H:%M')}")
    lines.append(f"  (Yatırım tavsiyesi değildir.)")
    return "\n".join(lines)

# ── Teknik Analiz (MA + RSI) ──────────────────────────────────────────────

def compute_rsi(prices: list, period: int = 14) -> float | None:
    """RSI hesapla."""
    if period < 1 or len(prices) < period + 1:
        return None
    try:
        changes = [
            float(prices[index]) - float(prices[index - 1])
            for index in range(1, len(prices))
        ][-period:]
        avg_gain = sum(max(change, 0.0) for change in changes) / period
        avg_loss = sum(max(-change, 0.0) for change in changes) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)
    except Exception:
        return None

def technical_analysis(ticker: str) -> str:
    """MA5, MA20, MA50 ve RSI14 ile teknik analiz."""
    if not YFINANCE_OK:
        return "Teknik analiz için yfinance gerekli: pip install yfinance"
    try:
        import yfinance as yf

        t = ticker.upper().strip()
        stock  = yf.Ticker(t)
        hist   = stock.history(period="3mo")
        if hist.empty or len(hist) < 20:
            return f"'{t}' için yeterli geçmiş veri yok."

        closes = list(hist["Close"])
        current = closes[-1]

        ma5  = sum(closes[-5:])  / 5  if len(closes) >= 5  else None
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        rsi  = compute_rsi(closes)

        lines = [
            f"{'='*42}",
            f"  TEKNİK ANALİZ — {t}",
            f"  {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}",
            f"{'='*42}",
            f"  Güncel Fiyat: {current:.2f}",
        ]
        if ma5:  lines.append(f"  MA5:          {ma5:.2f}  {'▲ Üstünde' if current > ma5 else '▼ Altında'}")
        if ma20: lines.append(f"  MA20:         {ma20:.2f}  {'▲ Üstünde' if current > ma20 else '▼ Altında'}")
        if ma50: lines.append(f"  MA50:         {ma50:.2f}  {'▲ Üstünde' if current > ma50 else '▼ Altında'}")
        if rsi is not None:
            rsi_comment = "Aşırı Alım ⚠" if rsi > 70 else "Aşırı Satım ⚠" if rsi < 30 else "Nötr Bölge"
            lines.append(f"  RSI (14):     {rsi:.1f}  — {rsi_comment}")

        # Sinyal yorumu
        signals = []
        if ma5 and ma20:
            if ma5 > ma20:
                signals.append("Kısa vadeli momentum pozitif (MA5 > MA20).")
            else:
                signals.append("Kısa vadeli momentum negatif (MA5 < MA20).")
        if rsi is not None:
            if rsi > 70:
                signals.append("RSI aşırı alım bölgesinde, düzeltme riski var.")
            elif rsi < 30:
                signals.append("RSI aşırı satım bölgesinde, tepki yükselişi olabilir.")
            else:
                signals.append("RSI nötr bölgede.")

        lines.append(f"{'='*42}")
        lines.append("  SİNYAL:")
        for s in signals:
            lines.append(f"  • {s}")
        lines.append(f"{'='*42}")
        lines.append("  ⚠ Bu analiz YATırım tavsiyesi değildir.")
        lines.append("  Geçmiş performans gelecekteki getiriyi")
        lines.append("  garanti etmez.")
        return "\n".join(lines)

    except Exception as e:
        return f"Teknik analiz hatası: {e}"

def get_watchlist_summary() -> str:
    """Favori hisselerin özet tablosu."""
    stocks = PROFILE.get("favorite_stocks", [])
    if not stocks:
        return ("Takip listesi boş, Efendim.\n"
                "'takip ekle THYAO.IS' ile hisse ekleyebilirsiniz.")
    lines = [f"{'='*42}", "  TAKİP LİSTESİ",
             f"  {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}",
             f"{'='*42}"]
    for ticker in stocks:
        data = get_stock_price(ticker)
        if "error" in data:
            lines.append(f"  {ticker:<12} Veri alınamadı")
        else:
            sign = "+" if data["change"] >= 0 else ""
            trend = "▲" if data["change"] >= 0 else "▼"
            lines.append(f"  {ticker:<12} {data['price']:>8.2f} {data['currency']} "
                         f"{sign}{data['change_pct']:.2f}% {trend}")
    lines.append(f"{'='*42}")
    lines.append("  (Yatırım tavsiyesi değildir.)")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════
# v9: DAILY BRIEFING MODÜLܼ
# ══════════════════════════════════════════════════════════════════════════
DAILY_BRIEFING_HEADLINE_CACHE = {}
DAILY_BRIEFING_CACHE_LOCK = threading.Lock()

def get_daily_briefing() -> str:
    """
    Günün önemli olaylarını haber sitelerinden çek,
    Groq AI ile özetle ve yapılandırılmış brifing oluştur.
    """
    if not BS4_OK or not REQUESTS_OK:
        return "Brifing için beautifulsoup4 ve requests gerekli."

    sources = [
        {"name": "Sözcü",      "url": "https://www.sozcu.com.tr/",       "domain": "sozcu.com.tr"},
        {"name": "Habertürk",  "url": "https://www.haberturk.com/",      "domain": "haberturk.com"},
        {"name": "Ekonomi",    "url": "https://www.ekonomim.com/",       "domain": "ekonomim.com"},
    ]

    all_headlines = []
    year_patterns = ["/2024/", "/2025/", "/2026/", "/gundem/", "/ekonomi/", "/dunya/", "/borsa/"]

    def fetch_source(src):
        with DAILY_BRIEFING_CACHE_LOCK:
            cached_entry = DAILY_BRIEFING_HEADLINE_CACHE.get(src["domain"])
        if cached_entry and time.time() - cached_entry["ts"] < 180:
            return cached_entry["headlines"]
        try:
            session = HTTP_SESSION or requests
            resp = session.get(
                src["url"],
                timeout=DEFAULT_HTTP_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JARVIS/9.0)"},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            headlines = []
            count = 0
            for a_tag in soup.find_all("a", href=True):
                title = a_tag.get_text(strip=True)
                href  = a_tag["href"]
                if (len(title) > 25 and src["domain"] in href and
                        any(p in href for p in year_patterns) and count < 4):
                    headlines.append(f"[{src['name']}] {title}")
                    count += 1
            with DAILY_BRIEFING_CACHE_LOCK:
                DAILY_BRIEFING_HEADLINE_CACHE[src["domain"]] = {
                    "ts": time.time(),
                    "headlines": headlines,
                }
            return headlines
        except requests.exceptions.Timeout:
            logger.warning("[Briefing] %s zaman aşımına uğradı", src["name"])
            return cached_entry["headlines"] if cached_entry else [
                f"[{src['name']}] Bağlantı zaman aşımına uğradı."
            ]
        except Exception:
            logger.exception("[Briefing] %s kaynağı alınamadı", src["name"])
            return cached_entry["headlines"] if cached_entry else []

    # Independent news sources are fetched concurrently; the short TTL also
    # prevents repeated briefing requests from re-downloading the same pages.
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        for headlines in executor.map(fetch_source, sources):
            all_headlines.extend(headlines)

    if not all_headlines:
        return "Günlük brifing alınamadı. İnternet bağlantısını kontrol edin, Efendim."

    now = datetime.datetime.now()
    date_str = now.strftime("%d %B %Y, %A")
    lines = [
        f"{'═'*44}",
        f"  GÜNLÜK BRİFİNG — {date_str}",
        f"  J.A.R.V.I.S. v{APP_DISPLAY_VERSION} Apex — Hafıza: Aktif",
        f"{'═'*44}",
        "",
        "  HABERLER:",
    ]
    for i, h in enumerate(all_headlines[:10], 1):
        lines.append(f"  {i:>2}. {h}")

    # Finans özeti ekle
    try:
        lines.append("")
        lines.append("  FİNANS ÖZETİ:")
        with ThreadPoolExecutor(max_workers=2) as executor:
            usd_future = executor.submit(get_exchange_rates, "USD")
            eur_future = executor.submit(get_exchange_rates, "EUR")
            usd_rates = usd_future.result()
            eur_rates = eur_future.result()
        if usd_rates:
            try_rate = usd_rates.get("TRY", 0)
            eur_try = eur_rates.get("TRY", 0) if eur_rates else 0
            if try_rate: lines.append(f"  USD/TRY: {try_rate:.4f}")
            if eur_try:  lines.append(f"  EUR/TRY: {eur_try:.4f}")
    except Exception:
        logger.exception("[Briefing] Finans özeti alınamadı")

    lines.append("")
    lines.append(f"{'═'*44}")
    lines.append("  (Yatırım tavsiyesi değildir.)")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════
# TTS - SES (v9: Profesyonel finans tonlaması)
# ══════════════════════════════════════════════════════════════════════════
_tts_lock = threading.Lock()

def _smart_truncate(text: str, max_chars: int = 400) -> str:
    text = re.sub(r'[*_`#•→═=▲▼⚠]', '', text)
    text = re.sub(r'\n+', ' ', text).strip()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    for punct in ['. ', '! ', '? ', ', ']:
        idx = truncated.rfind(punct)
        if idx > max_chars // 2:
            return truncated[:idx+1]
    return truncated + "..."

def _is_finance_content(text: str) -> bool:
    """Metnin finans içeriği olup olmadığını kontrol et."""
    finance_keywords = ["TRY", "USD", "EUR", "GBP", "fiyat", "kur", "borsa",
                        "hisse", "MA5", "MA20", "RSI", "yatırım", "analiz"]
    return any(kw in text for kw in finance_keywords)

def speak_async(text: str, finance_mode: bool = False):
    """v9: finance_mode=True ise daha profesyonel, yavaş ses."""
    if not GTTS_OK or not SETTINGS.get("tts_enabled", True):
        return
    clean_text = _smart_truncate(text, 400)
    finance_mode = finance_mode or (_is_finance_content(text) and
                                    SETTINGS.get("finance_voice_pro", True))

    def _run():
        with _tts_lock:
            try:
                tmp_root = Path(tempfile.gettempdir())
                tmp_dir = safe_file_target(tmp_root / "jarvis_secure", tmp_root)
                if tmp_dir is None:
                    logger.warning("[TTS] Geçersiz geçici dosya hedefi; ses üretimi atlandı.")
                    return
                tmp_dir.mkdir(parents=True, exist_ok=True)
                tmp_path = safe_file_target(tmp_dir / "jarvis_tts_v9.mp3", tmp_root)
                if tmp_path is None:
                    logger.warning("[TTS] Geçici dosya hedef doğrulanamadı; ses üretimi atlandı.")
                    return
                slow = finance_mode
                asyncio.run(_tts_save(clean_text, str(tmp_path), slow=slow))
                if tmp_path.exists():
                    os.chmod(tmp_path, 0o600)
                from playsound import playsound

                playsound(str(tmp_path))
            except Exception as e:
                logger.exception("TTS hatası: %s", e)
    threading.Thread(target=_run, daemon=True).start()

async def _tts_save(text, path, slow=False):
    from gtts import gTTS

    await asyncio.to_thread(gTTS(text=text, lang="tr", slow=slow).save, path)

# ══════════════════════════════════════════════════════════════════════════
# UYANDIRMA KELİMESİ (v8'den korundu)
# ══════════════════════════════════════════════════════════════════════════
class WakeWordListener(QThread):
    triggered = pyqtSignal()
    status    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._active = True

    def stop(self):
        self._active = False

    def run(self):
        if not SR_OK:
            return
        r = sr.Recognizer()
        r.energy_threshold = 250
        r.dynamic_energy_threshold = True
        r.pause_threshold = 0.6
        try:
            mic = sr.Microphone()
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=1.5)
        except Exception as e:
            self.status.emit(f"Mikrofon hatası: {e}")
            return

        while self._active:
            try:
                with mic as source:
                    audio = r.listen(source, timeout=4, phrase_time_limit=4)
                text = r.recognize_google(audio, language="tr-TR").lower()
                wake_words = ["jarvis", "hey jarvis", "ey jarvis", "merhaba jarvis",
                              "tamam jarvis", "haydi jarvis", "apex"]  # v9: apex eklendi
                if any(w in text for w in wake_words):
                    self.triggered.emit()
                    time.sleep(2)
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception:
                time.sleep(1)

# ══════════════════════════════════════════════════════════════════════════
# SES KOMUTLARI
# ══════════════════════════════════════════════════════════════════════════
class VoiceWorker(QThread):
    result  = pyqtSignal(str)
    error   = pyqtSignal(str)
    partial = pyqtSignal(str)

    def run(self):
        if not SR_OK:
            self.error.emit("SpeechRecognition kurulu değil.")
            return
        try:
            r = sr.Recognizer()
            r.pause_threshold = 0.8
            r.phrase_threshold = 0.3
            r.energy_threshold = 300
            r.dynamic_energy_threshold = True
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=8, phrase_time_limit=15)
            self.partial.emit("Ses işleniyor...")
            text = r.recognize_google(audio, language="tr-TR")
            self.result.emit(text)
        except sr.WaitTimeoutError:
            self.error.emit("Ses algılanamadı. Lütfen tekrar deneyin.")
        except sr.UnknownValueError:
            self.error.emit("Anlaşılamadı. Daha net konuşun.")
        except Exception as e:
            self.error.emit(str(e))

# ══════════════════════════════════════════════════════════════════════════
# HIZLI İNTERNET TESTİ
# ══════════════════════════════════════════════════════════════════════════
def run_speedtest() -> str:
    if SETTINGS.get("low_bandwidth_mode", True):
        try:
            start = time.time()
            if HTTP_SESSION is not None:
                response = HTTP_SESSION.get(
                    "https://www.google.com/generate_204",
                    timeout=(30, 300),
                    stream=True,
                )
                try:
                    response.raise_for_status()
                finally:
                    response.close()
            else:
                with urllib.request.urlopen(
                    "https://www.google.com/generate_204",
                    timeout=30,
                ) as response:
                    response.read(1)
            return (
                "Düşük internet modu açık: büyük indirme/yükleme testi "
                "çalıştırılmadı. Bağlantı yanıt süresi yaklaşık "
                f"{round((time.time() - start) * 1000)} ms."
            )
        except Exception as exc:
            logger.warning(
                "[Speedtest] Hafif bağlantı kontrolü başarısız: %s",
                type(exc).__name__,
            )
            return "Hafif bağlantı kontrolü başarısız; internet bağlantısı kullanılamıyor olabilir."
    try:
        import speedtest as st
        s = st.Speedtest()
        s.get_best_server()
        down = round(s.download() / 1_000_000, 1)
        up   = round(s.upload()   / 1_000_000, 1)
        ping = round(s.results.ping, 1)
        return f"İndirme: {down} Mbps | Yükleme: {up} Mbps | Ping: {ping} ms"
    except Exception as e:
        try:
            start = time.time()
            session = HTTP_SESSION
            if session is None and REQUESTS_OK:
                session = requests
            if session is None:
                with urllib.request.urlopen(
                    "https://www.google.com/generate_204",
                    timeout=DEFAULT_HTTP_TIMEOUT[0],
                ) as response:
                    response.read(1)
            else:
                response = session.get(
                    "https://www.google.com/generate_204",
                    timeout=DEFAULT_HTTP_TIMEOUT,
                    stream=True,
                )
                try:
                    response.raise_for_status()
                finally:
                    response.close()
            elapsed = time.time() - start
            return (
                "Hız testi tamamlanamadı; internet bağlantısı erişilebilir "
                f"(yanıt süresi ~{round(elapsed * 1000)} ms)."
            )
        except Exception as fallback_error:
            logger.warning(
                "[Speedtest] Hafif bağlantı kontrolü başarısız: %s",
                type(fallback_error).__name__,
            )
            return f"Speedtest hatası: {e}"

# ══════════════════════════════════════════════════════════════════════════
# FORUM HATA ARAMA
# ══════════════════════════════════════════════════════════════════════════
def search_error_forums(error_text: str) -> str:
    if not REQUESTS_OK:
        return "İnternet bağlantısı gerekli."
    query = urllib.parse.quote(error_text[:100])

    def search_stack_overflow() -> list[str]:
        url = (f"https://api.stackexchange.com/2.3/search/advanced"
               f"?order=desc&sort=relevance&q={query}&site=stackoverflow"
               f"&pagesize=3&filter=withbody")
        session = HTTP_SESSION or requests
        response = session.get(url, timeout=DEFAULT_HTTP_TIMEOUT)
        response.raise_for_status()
        return [
            f"[Stack Overflow] {item.get('title', '')}\n  → {item.get('link', '')}"
            for item in response.json().get("items", [])[:2]
        ]

    def search_github() -> list[str]:
        gh_url = (f"https://api.github.com/search/issues"
                  f"?q={query}&sort=reactions&order=desc&per_page=2")
        session = HTTP_SESSION or requests
        response = session.get(
            gh_url, timeout=DEFAULT_HTTP_TIMEOUT,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        response.raise_for_status()
        return [
            f"[GitHub] {item.get('title', '')}\n  → {item.get('html_url', '')}"
            for item in response.json().get("items", [])[:2]
        ]

    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        searches = [
            ("Stack Overflow", executor.submit(search_stack_overflow)),
            ("GitHub", executor.submit(search_github)),
        ]
        for source, future in searches:
            try:
                results.extend(future.result())
            except Exception:
                logger.exception("%s hata araması başarısız", source)

    if not results:
        return "Forum sonucu bulunamadı. Hatayı daha açık yazar mısınız, Efendim?"
    return "Hata için bulunan çözümler:\n\n" + "\n\n".join(results)

# ══════════════════════════════════════════════════════════════════════════
# SİSTEM TEMİZLİĞİ
# ══════════════════════════════════════════════════════════════════════════
def find_junk_files() -> str:
    if not PSUTIL_OK:
        return "psutil gerekli."
    junk_dirs = [
        os.environ.get("TEMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
    ]
    total_size = 0
    file_list  = []
    for d in junk_dirs:
        if not os.path.exists(d):
            continue
        for f in Path(d).rglob("*"):
            try:
                if f.is_file():
                    sz = f.stat().st_size
                    total_size += sz
                    mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                    age = (datetime.datetime.now() - mtime).days
                    if age > 7 and sz > 100_000:
                        file_list.append((age, sz, str(f)))
            except Exception:
                pass
    file_list.sort(reverse=True)
    top = file_list[:10]
    mb = round(total_size / 1024**2, 1)
    sonuc = f"Temp klasörlerinde toplam {mb} MB gereksiz dosya.\n\nEn eski büyük dosyalar:\n"
    for age, sz, path in top:
        sonuc += f"  • {age} gün önce | {round(sz/1024**2,1)} MB | {Path(path).name}\n"
    sonuc += "\nSilmemi ister misiniz? 'gereksizleri sil onayla' yazın."
    return sonuc

def delete_junk_files() -> str:
    deleted = 0; freed = 0
    max_age_days = 7
    max_files = 100
    temp_dirs = [
        os.environ.get("TEMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
    ]
    for d in temp_dirs:
        if not os.path.exists(d):
            continue
        for f in Path(d).rglob("*"):
            try:
                if f.is_file():
                    sz = f.stat().st_size
                    mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                    if (datetime.datetime.now() - mtime).days > max_age_days and sz > 100_000:
                        f.unlink(); deleted += 1; freed += sz
                        if deleted >= max_files:
                            break
            except Exception:
                pass
        if deleted >= max_files:
            break
    return f"{deleted} dosya silindi, {round(freed/1024**2,1)} MB alan açıldı, Efendim."

# ══════════════════════════════════════════════════════════════════════════
# PDF OKUMA
# ══════════════════════════════════════════════════════════════════════════
PDF_CONTENT = {}
PDF_MAX_CHARS = 50_000
PDF_MAX_FILES = 5
PDF_MAX_BYTES = 10 * 1024 * 1024
PDF_CONTENT_LOCK = threading.Lock()

def load_pdf(path: str) -> str:
    try:
        resolved = safe_path_under_root(path, Path.home())
        if resolved is None or resolved.suffix.lower() != ".pdf":
            return "Geçersiz PDF dosyası. Yalnızca kullanıcı alanındaki PDF dosyaları kabul edilir."
        if not resolved.exists():
            return "PDF dosyası bulunamadı."
        if resolved.stat().st_size > PDF_MAX_BYTES:
            return "PDF dosyası 10 MB sınırını aşıyor."
        if not PYMUPDF_OK:
            return "PDF okumak için 'pip install PyMuPDF' gerekli."
        text_parts = []
        text_length = 0
        try:
            import pymupdf as pdf_library
        except ImportError:
            import fitz as pdf_library

        with pdf_library.open(str(resolved)) as doc:
            for page in doc:
                remaining = PDF_MAX_CHARS - text_length
                if remaining <= 0:
                    break
                page_text = page.get_text()[:remaining]
                text_parts.append(page_text)
                text_length += len(page_text)
        text = "".join(text_parts)
        name = resolved.stem
        with PDF_CONTENT_LOCK:
            PDF_CONTENT[name] = text
            while len(PDF_CONTENT) > PDF_MAX_FILES:
                PDF_CONTENT.pop(next(iter(PDF_CONTENT)))
        try:
            atlas_memory_index_document(f"PDF: {resolved.name}", text)
        except Exception:
            logger.exception("[ATLAS][Memory] PDF yerel hafızaya eklenemedi: %s", resolved.name)
        dest = Path(PDF_STORE) / resolved.name
        try:
            shutil.copy2(resolved, dest)
            os.chmod(dest, 0o600)
            stored_pdfs = sorted(
                Path(PDF_STORE).glob("*.pdf"), key=lambda item: item.stat().st_mtime, reverse=True
            )
            for old_pdf in stored_pdfs[PDF_MAX_FILES:]:
                try:
                    old_pdf.unlink()
                except OSError:
                    pass
        except OSError as exc:
            logger.warning("[PDF] Saklanan kopya oluşturulamadı: %s", type(exc).__name__)
        return (f"'{resolved.name}' yüklendi ({len(text)} karakter okundu).\n"
                f"Bu PDF hakkında soru sorabilirsiniz, Efendim.")
    except ImportError:
        return "PDF okumak için 'pip install PyMuPDF' gerekli."
    except Exception as e:
        return f"PDF okunamadı: {e}"

def get_pdf_context() -> str:
    with PDF_CONTENT_LOCK:
        pdf_snapshot = list(PDF_CONTENT.items())
    if not pdf_snapshot:
        return ""
    texts = []
    for name, content in pdf_snapshot:
        texts.append(f"[PDF: {name}]\n{content[:10000]}")
    return "\n\n".join(texts)

# ══════════════════════════════════════════════════════════════════════════
# WHATSAPP
# ══════════════════════════════════════════════════════════════════════════
def contacts_load() -> dict:
    data = safe_read_json(CONTACTS_FILE, {})
    return data if isinstance(data, dict) else {}


def contacts_save(c: dict):
    if not isinstance(c, dict):
        return
    safe_write_json(CONTACTS_FILE, c)

def contacts_find(name: str) -> str | None:
    c = contacts_load()
    for k, v in c.items():
        if k.lower() == name.lower().strip():
            return v
    return None

def whatsapp_send(phone: str, message: str) -> str:
    result = send_whatsapp_message(phone, safe_user_text(message, 500))
    if result.get("ok"):
        provider = result.get("provider", "WhatsApp")
        scheduled = result.get("scheduled")
        return (
            f"Mesaj {scheduled}'de gönderilecek, Efendim."
            if scheduled
            else f"WhatsApp mesajı gönderildi ({provider}), Efendim."
        )
    return str(result.get("error") or "WhatsApp mesajı gönderilemedi.")

# ══════════════════════════════════════════════════════════════════════════
# MASAÜSTÜ KISAYOLU
# ══════════════════════════════════════════════════════════════════════════
def create_desktop_shortcut():
    try:
        home_root = Path.home()
        desktop = safe_file_target(home_root / "Desktop", home_root)
        if desktop is None:
            return "Masaüstü hedefi doğrulanamadı; güvenlik kuralı nedeniyle istek reddedildi."
        script = Path(__file__).resolve()
        bat = desktop / "JARVIS_v9.bat"
        safe_dir = str(script.parent).replace('"', '""')
        safe_script = str(script).replace('"', '""')
        with open(bat, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\ncd /d "{safe_dir}"\r\npy -3.11 "{safe_script}"\r\n')
        try:
            os.chmod(bat, 0o600)
        except OSError:
            pass
        return f"Masaüstü kısayolu oluşturuldu: {bat}"
    except Exception as e:
        return f"Kısayol oluşturulamadı: {e}"

# ══════════════════════════════════════════════════════════════════════════
# HABERLER (v8'den iyileştirildi)
# ══════════════════════════════════════════════════════════════════════════
def get_news(detailed: bool = False) -> str:
    if not BS4_OK or not REQUESTS_OK:
        return "Haber için beautifulsoup4 ve requests gerekli."

    haberler = []
    try:
        session = HTTP_SESSION or requests
        r = session.get(
            "https://www.sozcu.com.tr/",
            timeout=DEFAULT_HTTP_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            title = a_tag.get_text(strip=True)
            href  = a_tag["href"]
            parsed_href = urllib.parse.urlparse(href)
            if (len(title) > 30 and parsed_href.hostname in {"www.sozcu.com.tr", "sozcu.com.tr"} and
                    any(x in href for x in ["/2024/", "/2025/", "/2026/",
                                            "/gundem/", "/ekonomi/", "/dunya/"])):
                full_url = href if parsed_href.scheme else urllib.parse.urljoin(
                    "https://www.sozcu.com.tr/", href)
                parsed_full_url = urllib.parse.urlparse(full_url)
                if parsed_full_url.scheme != "https" or parsed_full_url.hostname not in {
                    "www.sozcu.com.tr", "sozcu.com.tr"
                }:
                    continue
                if (title, full_url) not in haberler:
                    haberler.append((title, full_url))
            if len(haberler) >= 6:
                break
    except requests.exceptions.Timeout:
        return "Haber sitesine bağlanılamadı (zaman aşımı), Efendim."
    except Exception as e:
        return f"Haber sitesine ulaşılamadı: {e}"

    if not haberler:
        return "Haber bulunamadı, Efendim."

    if not detailed:
        sonuc = "Güncel haberler (detay için 'haber detay' yazın):\n\n"
        for i, (title, link) in enumerate(haberler):
            sonuc += f"{i+1}. {title}\n"
        return sonuc

    def fetch_detail(item: tuple[str, str]) -> tuple[str, str]:
        title, link = item
        try:
            parsed_link = urllib.parse.urlparse(link)
            if parsed_link.scheme != "https" or parsed_link.hostname not in {
                "www.sozcu.com.tr", "sozcu.com.tr"
            }:
                return title, "İçerik adresi doğrulanamadı."
            session = HTTP_SESSION or requests
            response = session.get(
                link,
                timeout=DEFAULT_HTTP_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all("p")
            icerik = " ".join(p.get_text(strip=True) for p in paragraphs[:5]
                              if len(p.get_text(strip=True)) > 40)
            return title, f"{icerik[:500]}..." if icerik else "İçerik alınamadı."
        except requests.exceptions.Timeout:
            return title, "İçerik zaman aşımına uğradı."
        except Exception as exc:
            logger.warning("Haber içeriği alınamadı (%s): %s", link, exc)
            return title, "İçerik alınamadı."

    with ThreadPoolExecutor(max_workers=3) as executor:
        details = list(executor.map(fetch_detail, haberler[:3]))
    sonuc = "Haberler ve içerikleri:\n\n"
    for i, (title, content) in enumerate(details):
        sonuc += f"{'='*50}\n{i+1}. {title}\n{content}\n\n"
    return sonuc

# ══════════════════════════════════════════════════════════════════════════
# ÖZEL GÜNLER & TATİLLER
# ══════════════════════════════════════════════════════════════════════════
OZEL_GUNLER = {
    "01-01": "Yeni Yıl",
    "04-23": "Ulusal Egemenlik ve Çocuk Bayramı",
    "05-01": "İşçi Bayramı",
    "05-19": "Atatürk'ü Anma, Gençlik ve Spor Bayramı",
    "07-15": "Demokrasi ve Millî Birlik Günü",
    "08-30": "Zafer Bayramı",
    "10-28": "Cumhuriyet Bayramı arifesi",
    "10-29": "Cumhuriyet Bayramı",
}

def check_upcoming_holidays() -> str:
    yarin = datetime.datetime.now() + datetime.timedelta(days=1)
    key = yarin.strftime("%m-%d")
    if key in OZEL_GUNLER:
        return f"Yarın {OZEL_GUNLER[key]}! ({yarin.strftime('%d %B %Y')})"
    return ""

def get_all_holidays() -> str:
    yil = datetime.datetime.now().year
    sonuc = "Resmî tatiller ve özel günler:\n"
    for tarih, isim in sorted(OZEL_GUNLER.items()):
        sonuc += f"  • {tarih.replace('-', '.')}.{yil} — {isim}\n"
    return sonuc

# ══════════════════════════════════════════════════════════════════════════
# YAZI TARZI
# ══════════════════════════════════════════════════════════════════════════
def style_update(text: str):
    s = safe_read_json(STYLE_PATH, {})
    if not isinstance(s, dict):
        s = {}
    safe_text = safe_user_text(text, 10000)
    s["total"] = s.get("total", 0) + 1
    s["avg_len"] = (s.get("avg_len", 0) * (s["total"]-1) + len(safe_text)) / s["total"]
    safe_write_json(STYLE_PATH, s)

# ══════════════════════════════════════════════════════════════════════════
# AI MOTORU (v9: kişisel bağlam entegrasyonu)
# ══════════════════════════════════════════════════════════════════════════
class AIEngine(_ServiceAIEngine):
    @staticmethod
    def _create_groq_client(api_key):
        return create_groq_client(api_key)

    @staticmethod
    def _create_gemini_client(api_key):
        return create_gemini_client(api_key)

    @staticmethod
    def _groq_available():
        return GROQ_OK

    @staticmethod
    def _groq_model():
        return GROQ_MODEL

    @staticmethod
    def _gemini_model():
        return GEMINI_MODEL

    @staticmethod
    def _classify_request(text):
        return classify_ai_request(text)

    @staticmethod
    def _requires_atlas(text):
        return requires_atlas(text)

    @staticmethod
    def _is_remote_context_enabled():
        return REMOTE_CONTEXT_ENABLED

    @staticmethod
    def _persona():
        return build_persona()

    @staticmethod
    def _profile_context():
        return PROFILE.get_context_string()

    @staticmethod
    def _grounded_search(prompt, model, **kwargs):
        return gemini_grounded_search(prompt, model, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# v9: ÇEKIRDEK GRAFİĞİ — Fütüristik renk geçişli + data-flow efekti
# ══════════════════════════════════════════════════════════════════════════
class CoreWidget(QWidget):
    """
    v9 Apex CoreWidget:
    - Renk geçişli (hue rotation) idle animasyonu
    - Data-flow: Veri çekilirken dışarıdan içe akan parçacıklar
    - Finans modu: Altın rengi aura
    - Thinking modu: Spin etkili turuncu halkalar
    """
    STATES = {
        "idle":      QColor("#00b4ff"),
        "thinking":  QColor("#ff8800"),
        "error":     QColor("#ff1a44"),
        "done":      QColor("#00ffaa"),
        "listening": QColor("#aa44ff"),
        "atlas":     QColor("#00ffee"),
        "finance":   QColor("#ffd700"),    # v9: Finans modu
        "briefing":  QColor("#00ffee"),    # v9: Brifing modu
    }

    state_changed = pyqtSignal(str)  # Özellik 7: StatusBorder çerçevesine yansır

    def __init__(self, low_resource_mode: bool = False):
        super().__init__()
        self.state = "idle"
        self.phase = 0.0
        self.vol   = 0.0
        self._hue_shift = 0.0        # v9: Renk kaydırma
        self._data_flow  = []         # v9: Data-flow parçacıkları
        self._spin_angle = 0.0        # v9: Thinking spin açısı
        self._pulse = 0.0
        self._low_resource_mode = bool(low_resource_mode)
        self.particles = [] if self._low_resource_mode else [
            [random.uniform(0, 6.28), random.uniform(55, 120),
             random.uniform(0.005, 0.02), random.uniform(0, 6.28)]
            for _ in range(40)
        ]
        for _ in range(0 if self._low_resource_mode else 15):
            self._data_flow.append({
                "angle": random.uniform(0, 6.28),
                "r":     random.uniform(80, 130),
                "speed": random.uniform(-1.5, -0.8),  # içe doğru
                "alpha": random.randint(40, 120),
                "size":  random.uniform(1, 3),
            })
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._tick)
        self._animation_timer.start(120 if self._low_resource_mode else 28)

    def set_low_resource_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._low_resource_mode:
            return
        self._low_resource_mode = enabled
        if enabled:
            self.particles.clear()
            self._data_flow.clear()
        else:
            self.particles = [
                [random.uniform(0, 6.28), random.uniform(55, 120),
                 random.uniform(0.005, 0.02), random.uniform(0, 6.28)]
                for _ in range(40)
            ]
            self._data_flow = [
                {
                    "angle": random.uniform(0, 6.28),
                    "r": random.uniform(80, 130),
                    "speed": random.uniform(-1.5, -0.8),
                    "alpha": random.randint(40, 120),
                    "size": random.uniform(1, 3),
                }
                for _ in range(15)
            ]
        self._animation_timer.setInterval(120 if enabled else 28)
        self.update()

    def set_state(self, s):
        new = s if s in self.STATES else "idle"
        if new == self.state:
            return
        self.state = new
        self.state_changed.emit(new)  # Özellik 7: durum çerçevesine yansıt
        self.update()

    def set_volume(self, v):
        self.vol = max(0, min(1, v))

    def _tick(self):
        self.phase      += 0.035
        self._pulse     += 0.09
        self._hue_shift += 0.3   # v9: renk geçişi hızı
        self._spin_angle += 2.5  # v9: spin hızı (derece)
        for p in self.particles:
            p[0] += p[2]
            p[3] += 0.012

        # v9: Data-flow parçacıkları (sadece thinking/finance/briefing modunda hızlanır)
        active = self.state in ("thinking", "finance", "briefing")
        for df in self._data_flow:
            speed = df["speed"] * (2.5 if active else 0.6)
            df["r"] += speed
            if df["r"] < 20:
                df["r"] = random.uniform(100, 140)
                df["angle"] = random.uniform(0, 6.28)
                df["alpha"] = random.randint(40, 120)
        self.update()

    def _hue_rotate(self, base_color: QColor, degrees: float) -> QColor:
        """Rengi hue ekseninde döndür."""
        h = (base_color.hue() + int(degrees)) % 360
        return QColor.fromHsv(h, base_color.saturation(), base_color.value())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            not self._low_resource_mode,
        )
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base_c = self.STATES[self.state]

        # v9: Idle modda yavaş hue geçişi
        if self.state == "idle":
            bc = self._hue_rotate(base_c, self._hue_shift * 0.4)
        else:
            bc = base_c

        p.fillRect(0, 0, w, h, QColor(C["bg"]))
        pulse = 1.0 + (0.08 if self.state in ("listening", "thinking", "done") else 0.025) * (0.5 + 0.5 * math.sin(self._pulse))
        rx_base, ry_base = min(w, h) * 0.34 * pulse, min(w, h) * 0.25 * pulse

        # v9: Dıştan içe akan data-flow çizgicikleri
        if self.state in ("thinking", "finance", "briefing", "idle"):
            for df in self._data_flow:
                px = cx + math.cos(df["angle"]) * df["r"]
                py = cy + math.sin(df["angle"]) * df["r"]
                c2 = QColor(bc); c2.setAlpha(df["alpha"])
                p.setPen(Qt.NoPen); p.setBrush(QBrush(c2))
                p.drawEllipse(QPointF(px, py), df["size"], df["size"])

        # Orbital parçacıklar
        for pt in self.particles:
            px = cx + math.cos(pt[0]) * pt[1]
            py = cy + math.sin(pt[0]) * pt[1]
            c2 = QColor(bc); c2.setAlpha(int(60 + 55 * math.sin(pt[3])))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(c2))
            sz = 2 + self.vol * 3
            p.drawEllipse(QPointF(px, py), sz, sz)

        # v9: Thinking modunda dönen halkalar
        if self.state == "thinking":
            for i in range(3):
                angle_offset = math.radians(self._spin_angle + i * 120)
                rx = cx + math.cos(angle_offset) * (35 + i * 10)
                ry = cy + math.sin(angle_offset) * (35 + i * 10)
                c2 = QColor(bc); c2.setAlpha(180 - i * 40)
                p.setPen(QPen(c2, 2)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(rx, ry), 5, 5)

        # Halka katmanları
        for i in range(5, 0, -1):
            r2 = 28 + i * 16 + self.vol * 18 * math.sin(self.phase + i)
            # v9: Finance modunda altın gradient halka
            if self.state == "finance":
                c2 = self._hue_rotate(bc, i * 8)
            else:
                c2 = QColor(bc)
            c2.setAlpha(max(0, 165 - i * 26))
            p.setPen(QPen(c2, 1.4)); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r2 * 1.18 * pulse, r2 * 0.78 * pulse)

        # v9: Merkez çekirdek - gradient
        g = QRadialGradient(cx, cy, max(rx_base, ry_base))
        g.setColorAt(0, QColor(bc).lighter(200))
        g.setColorAt(0.4, bc)
        g.setColorAt(1, QColor(bc.red(), bc.green(), bc.blue(), 0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), rx_base, ry_base)

        # v9: Daha bilgilendirici durum etiketi
        lbl = {
            "idle":     "APEX HAZIR",
            "thinking": "İŞLENİYOR",
            "error":    "HATA",
            "done":     "TAMAM",
            "listening":"DİNLİYOR",
            "atlas":    "ATLAS AKTİF",
            "finance":  "FİNANS",
            "briefing": "BRİFİNG",
        }.get(self.state, "")
        p.setPen(QPen(QColor(C["text"])))
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(0, h - 16, w, 16, Qt.AlignCenter, lbl)
        p.end()

# ══════════════════════════════════════════════════════════════════════════
# SOL PANEL (v9: Finans widget eklendi)
# ══════════════════════════════════════════════════════════════════════════
class LeftPanel(QWidget):
    session_selected = pyqtSignal(int)
    weather_ready = pyqtSignal(object)
    fx_ready = pyqtSignal(object)
    hardware_ready = pyqtSignal(object)

    def __init__(
        self,
        low_bandwidth_mode: bool = False,
        low_resource_mode: bool = False,
    ):
        super().__init__()
        self._closing = False
        self._low_bandwidth_mode = bool(low_bandwidth_mode)
        self._low_resource_mode = bool(low_resource_mode)
        self._side_refresh_active = False
        self._side_worker = None
        self._hardware_worker = None
        self.weather_ready.connect(self._apply_weather)
        self.fx_ready.connect(self._apply_fx)
        self.setFixedWidth(235)
        self.setStyleSheet(
            f"background:{C['panel']}; border-right:1px solid {C['border']};"
            " border-top-left-radius:18px; border-bottom-left-radius:18px;")
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 12, 10, 10); lay.setSpacing(6)

        self.clock_lbl = QLabel(); self.clock_lbl.setAlignment(Qt.AlignCenter)
        self.clock_lbl.setStyleSheet(f"color:{C['blue']};font:bold 22px 'Consolas';background:transparent;")
        self.date_lbl = QLabel(); self.date_lbl.setAlignment(Qt.AlignCenter)
        self.date_lbl.setStyleSheet(f"color:{C['subtext']};font:10px 'Consolas';background:transparent;")
        lay.addWidget(self.clock_lbl); lay.addWidget(self.date_lbl)

        # Hava durumu
        wf = QFrame()
        wf.setStyleSheet(f"background:{C['bg2']};border-radius:14px;border:1px solid {C['border']};")
        wl = QVBoxLayout(wf); wl.setContentsMargins(8, 6, 8, 6)
        self.temp_lbl = QLabel("-- °C")
        self.temp_lbl.setStyleSheet(f"color:{C['blue']};font:bold 18px 'Consolas';background:transparent;border:none;")
        self.desc_lbl = QLabel()
        self.desc_lbl.setStyleSheet(f"color:{C['text']};font:10px 'Consolas';background:transparent;border:none;")
        self.hum_lbl = QLabel()
        self.hum_lbl.setStyleSheet(f"color:{C['subtext']};font:9px 'Consolas';background:transparent;border:none;")
        self.rain_lbl = QLabel()
        self.rain_lbl.setStyleSheet(f"color:{C['subtext']};font:9px 'Consolas';background:transparent;border:none;")
        for l in [self.temp_lbl, self.desc_lbl, self.hum_lbl, self.rain_lbl]:
            wl.addWidget(l)
        lay.addWidget(wf)

        # v9: Mini döviz paneli
        ff = QFrame()
        ff.setStyleSheet(f"background:{C['bg2']};border-radius:14px;border:1px solid {C['gold']}30;")
        fl = QVBoxLayout(ff); fl.setContentsMargins(8, 6, 8, 6)
        fx_title = QLabel("KUR PANELİ")
        fx_title.setStyleSheet(f"color:{C['gold']};font:bold 9px 'Consolas';background:transparent;border:none;")
        fl.addWidget(fx_title)
        self.fx_labels = {}
        for cur in ["USD", "EUR", "GBP"]:
            lbl = QLabel(f"{cur}/TRY: --")
            lbl.setStyleSheet(f"color:{C['cyan']};font:10px 'Consolas';background:transparent;border:none;")
            fl.addWidget(lbl)
            self.fx_labels[cur] = lbl
        self.fx_ts = QLabel("")
        self.fx_ts.setStyleSheet(f"color:{C['subtext']};font:8px 'Consolas';background:transparent;border:none;")
        fl.addWidget(self.fx_ts)
        lay.addWidget(ff)

        # Donanım
        hf = QFrame()
        hf.setStyleSheet(f"background:{C['bg2']};border-radius:14px;border:1px solid {C['border']};")
        hl = QVBoxLayout(hf); hl.setContentsMargins(8, 6, 8, 6)
        self.cpu_lbl = QLabel("CPU: --%")
        self.ram_lbl = QLabel("RAM: --%")
        self.bat_lbl = QLabel("Pil: --")
        for l in [self.cpu_lbl, self.ram_lbl, self.bat_lbl]:
            l.setStyleSheet(f"color:{C['subtext']};font:9px 'Consolas';background:transparent;border:none;")
            hl.addWidget(l)
        lay.addWidget(hf)

        hl2 = QLabel("SOHBET GEÇMİŞİ")
        hl2.setStyleSheet(f"color:{C['dim']};font:bold 9px 'Consolas';background:transparent;")
        lay.addWidget(hl2)
        self.hist = QListWidget()
        self.hist.setStyleSheet(f"""
            QListWidget{{background:{C['bg2']};border:1px solid {C['border']};
                border-radius:12px;color:{C['text']};font:10px 'Consolas';}}
            QListWidget::item:hover{{background:{C['border']};}}
            QListWidget::item:selected{{background:{C['blue']}20;color:{C['blue']};}}
        """)
        self.hist.itemClicked.connect(
            lambda i: self.session_selected.emit(i.data(Qt.UserRole)))
        lay.addWidget(self.hist, 1)

        self._clock_timer = QTimer(self, timeout=self._clock)
        self._clock_timer.start(5000 if self._low_resource_mode else 1000)
        self._side_refresh_timer = QTimer(
            self, timeout=self._refresh_side_panels
        )
        if not self._low_bandwidth_mode:
            self._side_refresh_timer.start(300000)
        self._hardware_timer = QTimer(self, timeout=self._hw)
        self._hardware_timer.start(30000 if self._low_resource_mode else 10000)

        self._clock()
        if self._low_bandwidth_mode:
            self.desc_lbl.setText("Veri tasarrufu — istek üzerine")
            self.fx_ts.setText("Otomatik ağ kapalı")
        else:
            self._refresh_side_panels()

    def set_low_bandwidth_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._low_bandwidth_mode:
            if enabled:
                self._side_refresh_timer.stop()
            return
        self._low_bandwidth_mode = enabled
        if enabled:
            self._side_refresh_timer.stop()
            self.desc_lbl.setText("Veri tasarrufu — istek üzerine")
            self.fx_ts.setText("Otomatik ağ kapalı")
            return
        self._side_refresh_timer.start(300000)
        self._refresh_side_panels()

    def set_low_resource_mode(self, enabled: bool) -> None:
        self._low_resource_mode = bool(enabled)
        self._clock_timer.setInterval(5000 if enabled else 1000)
        self._hardware_timer.setInterval(30000 if enabled else 10000)

    def _refresh_side_panels(self):
        """Hava ve kur verilerini tek bir kısa akışta yenile."""
        if self._closing or self._side_refresh_active:
            return
        self._side_refresh_active = True
        worker = SidePanelWorker()
        self._side_worker = worker
        worker.result.connect(self._apply_side_panel_data)
        worker.error.connect(self._on_side_panel_error)
        worker.finished.connect(lambda: self._release_side_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _release_side_worker(self, worker):
        if self._side_worker is worker:
            self._side_worker = None
        self._side_refresh_active = False

    def prepare_for_shutdown(self):
        self._closing = True
        for timer in self.findChildren(QTimer):
            timer.stop()

    def resume_after_shutdown(self):
        self._closing = False
        self._clock_timer.start()
        self._hardware_timer.start(
            30000 if self._low_resource_mode else 10000
        )
        if self._low_bandwidth_mode:
            self._side_refresh_timer.stop()
        else:
            self._side_refresh_timer.start(300000)

    @property
    def side_worker_running(self) -> bool:
        return any(
            worker is not None and worker.isRunning()
            for worker in (self._side_worker, self._hardware_worker)
        )

    def _apply_side_panel_data(self, data):
        if self._closing:
            return
        self._apply_weather(data["weather"])
        self._apply_fx(data["fx"])

    def _on_side_panel_error(self, error: str):
        logger.error("[SidePanel] Yenileme hatası: %s", error)
        if not self._closing:
            self.desc_lbl.setText("Hava verisi yenilenemedi")

    def _clock(self):
        now = datetime.datetime.now()
        self.clock_lbl.setText(now.strftime("%H:%M:%S"))
        self.date_lbl.setText(now.strftime("%d %B %Y"))
        color = "#ff9944" if 0 <= now.hour < 6 else C["blue"]
        self.clock_lbl.setStyleSheet(f"color:{color};font:bold 22px 'Consolas';background:transparent;")

    def _apply_weather(self, w):
        self.temp_lbl.setText(f"{w['temp']} °C")
        self.desc_lbl.setText(str(w.get("desc", "")))
        self.hum_lbl.setText(f"Nem: %{w.get('humidity','?')}")
        self.rain_lbl.setText(f"Yağmur: {w.get('rain_prob','?')}")

    def _apply_fx(self, values):
        for cur, try_rate in values.items():
            if cur in self.fx_labels:
                self.fx_labels[cur].setText(f"{cur}/TRY: {try_rate:.4f}")
        self.fx_ts.setText(datetime.datetime.now().strftime("%H:%M"))

    def _hw(self):
        if self._closing or (
            self._hardware_worker is not None
            and self._hardware_worker.isRunning()
        ):
            return
        worker = HardwareWorker()
        self._hardware_worker = worker
        worker.result.connect(self._apply_hardware)
        worker.error.connect(self._on_hardware_error)
        worker.finished.connect(lambda: self._release_hardware_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _apply_hardware(self, hw):
        if self._closing:
            return
        self.cpu_lbl.setText(f"CPU: {hw['cpu']}%")
        self.ram_lbl.setText(f"RAM: {hw['ram']}% ({hw.get('ram_gb', 0)} GB)")
        if hw["bat"] is not None:
            color = C["red"] if hw["bat"] < 10 else C["subtext"]
            self.bat_lbl.setText(f"Pil: {hw['bat']}% {'⚡' if hw['charging'] else ''}")
            self.bat_lbl.setStyleSheet(
                f"color:{color};font:9px 'Consolas';background:transparent;border:none;"
            )
        self.hardware_ready.emit(hw)

    def _on_hardware_error(self, error: str):
        logger.error("[Hardware] Sol panel ölçümü başarısız: %s", error)

    def _release_hardware_worker(self, worker):
        if self._hardware_worker is worker:
            self._hardware_worker = None

    def refresh_history(self):
        self.hist.clear()
        for sid, title, _ in db_get_sessions():
            item = QListWidgetItem(f"◈ {title[:24]}")
            item.setData(Qt.UserRole, sid)
            self.hist.addItem(item)

# ══════════════════════════════════════════════════════════════════════════
# SOHBET ALANI
# ══════════════════════════════════════════════════════════════════════════
class ChatBubble(QFrame):
    def __init__(self, role, text, font_size=13):
        super().__init__()
        is_user = role == "user"
        color = C["blue"] if is_user else C["green"]
        self.setStyleSheet(
            f"background:{color}12;border:1px solid {color}35;border-radius:14px;margin:2px;")
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6)
        align = Qt.AlignRight if is_user else Qt.AlignLeft
        who = QLabel("SEN" if is_user else "J.A.R.V.I.S. v9 APEX")
        who.setStyleSheet(f"color:{color};font:bold 9px 'Consolas';background:transparent;")
        who.setAlignment(align); lay.addWidget(who)
        msg = QLabel(text); msg.setWordWrap(True)
        self.message_label = msg
        msg.setStyleSheet(f"color:{C['text']};font:{font_size}px 'Consolas';background:transparent;")
        msg.setAlignment(align); lay.addWidget(msg)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def append_text(self, text: str):
        self.message_label.setText(self.message_label.text() + text)

class ChatArea(QScrollArea):
    def __init__(self, font_size=13):
        super().__init__()
        self.font_size = font_size
        self.setWidgetResizable(True)
        self.setStyleSheet(f"background:{C['bg']};border:none;")
        self._c = QWidget(); self._c.setStyleSheet(f"background:{C['bg']};")
        self._l = QVBoxLayout(self._c)
        self._l.setAlignment(Qt.AlignTop); self._l.setSpacing(4)
        self.setWidget(self._c)

    def add_bubble(self, role, text):
        b = ChatBubble(role, text, self.font_size); self._l.addWidget(b)
        QTimer.singleShot(50, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()))
        return b

    def clear_chat(self):
        while self._l.count():
            item = self._l.takeAt(0)
            if item.widget(): item.widget().deleteLater()

# ══════════════════════════════════════════════════════════════════════════
# İŞ PARÇACIKLARI
# ══════════════════════════════════════════════════════════════════════════
class AIWorker(QThread):
    finished  = pyqtSignal(str)
    token     = pyqtSignal(str)
    error     = pyqtSignal(str)
    tool_call = pyqtSignal(str)
    progress  = pyqtSignal(str)
    cancelled = pyqtSignal()
    def __init__(self, engine, history, msg, extra="", feedback_text=""):
        super().__init__()
        self.engine  = engine
        self.history = history
        self.msg     = msg
        self.extra   = extra
        self.feedback_text = feedback_text
        self._cancel_event = threading.Event()
        self._stream_lock = threading.Lock()
        self._active_stream = None

    def _register_stream(self, stream) -> None:
        with self._stream_lock:
            self._active_stream = stream
            should_close = stream is not None and self._cancel_event.is_set()
        if should_close:
            close = getattr(stream, "close", None)
            if close is not None:
                close()

    def cancel(self) -> None:
        self.requestInterruption()
        self._cancel_event.set()
        with self._stream_lock:
            stream = self._active_stream
        close = getattr(stream, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                logger.exception("[AIWorker] İptal sırasında ağ akışı kapatılamadı")

    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set() or self.isInterruptionRequested()

    def run(self):
        stream = None
        try:
            chunks = []
            stream = iter(self.engine.stream(
                self.history,
                self.msg,
                self.extra,
                cancel_event=self._cancel_event,
                stream_callback=self._register_stream,
            ))
            self.progress.emit("Yanıt hazırlanıyor...")
            for chunk in stream:
                if self._is_cancelled():
                    self.cancelled.emit()
                    return
                if chunk.startswith("__TOOL_CALL__:"):
                    self.tool_call.emit(chunk[len("__TOOL_CALL__:"):])
                else:
                    chunks.append(chunk)
                    self.token.emit(chunk)
                    self.progress.emit("Yanıt alınıyor...")
            if self._is_cancelled():
                self.cancelled.emit()
                return
            if chunks:
                reply = "".join(chunks)
                if self.feedback_text:
                    reply += f"\n\nGüven ve kaynak durumu:\n{self.feedback_text}"
                self.finished.emit(reply)
            else:
                self.finished.emit("")
        except Exception as exc:
            if self._is_cancelled():
                self.cancelled.emit()
            else:
                logger.exception("[AIWorker] Yanıt akışı başarısız")
                self.error.emit(_friendly_ai_error(exc))
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    logger.exception("[AIWorker] Akış kapatılamadı")


def _friendly_ai_error(error: Exception) -> str:
    """Map common provider/network failures to clear, actionable UI text."""
    message = str(error).strip()
    normalized = message.casefold()
    if any(term in normalized for term in ("timeout", "timed out", "zaman aşımı")):
        return "AI yanıtı zamanında alınamadı. Bağlantınızı kontrol edip tekrar deneyin."
    if any(term in normalized for term in ("connection", "network", " bağlantı", "offline")):
        return "AI sağlayıcısına bağlanılamadı. İnternet bağlantınızı kontrol edin."
    if any(term in normalized for term in ("api key", "api anahtarı", "unauthorized", "401", "403")):
        return "AI sağlayıcısı kimlik doğrulamasını reddetti. API anahtarını ve sağlayıcı ayarlarını kontrol edin."
    if any(term in normalized for term in ("429", "rate limit", "too many requests")):
        return "AI sağlayıcısının istek sınırına ulaşıldı. Biraz bekleyip yeniden deneyin."
    return f"AI isteği tamamlanamadı: {message or type(error).__name__}"

class SpeedtestWorker(QThread):
    finished = pyqtSignal(str)
    def run(self): self.finished.emit(run_speedtest())

class NewsWorker(QThread):
    finished = pyqtSignal(str)
    def __init__(self, detailed=False):
        super().__init__(); self.detailed = detailed
    def run(self): self.finished.emit(get_news(self.detailed))


class CurrencyWorker(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            result = parse_currency_query(self.query)
            if result is None:
                result = "Kur sorgusu anlaşılamadı."
            self.result.emit(result)
        except Exception as exc:
            logger.exception("[Finance] Kur sorgusu başarısız")
            self.error.emit(str(exc))


class ForumSearchWorker(QThread):
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            self.result.emit(search_error_forums(self.query))
        except Exception as exc:
            logger.exception("[Research] Hata forumu araması başarısız")
            self.error.emit(str(exc))


class SidePanelWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            weather = get_weather()
            currencies = ("USD", "EUR", "GBP")
            values = {}
            with ThreadPoolExecutor(max_workers=len(currencies)) as executor:
                for currency, rates in zip(
                    currencies, executor.map(get_exchange_rates, currencies)
                ):
                    try_rate = rates.get("TRY", 0)
                    if try_rate:
                        values[currency] = try_rate
            self.result.emit({"weather": weather, "fx": values})
        except Exception as exc:
            logger.exception("[SidePanel] Yenileme başarısız")
            self.error.emit(str(exc))


class ReminderCheckWorker(QThread):
    result = pyqtSignal(object)

    def run(self):
        due_reminders = []
        due_routines = []
        errors = []
        try:
            due_reminders = db_claim_due_reminders()
        except Exception as exc:
            logger.exception("[Reminder] Hatırlatıcılar kontrol edilemedi")
            errors.append(f"Hatırlatıcılar: {exc}")
        try:
            due_routines = claim_due_routines()
        except Exception as exc:
            logger.exception("[Routines] Zamanlanmış rutinler kontrol edilemedi")
            errors.append(f"Rutinler: {exc}")
        self.result.emit((due_reminders, due_routines, errors))


class PdfLoadWorker(QThread):
    result = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        self.result.emit(load_pdf(self.path))


class HardwareWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.result.emit(get_hw())
        except Exception as exc:
            logger.exception("[Hardware] Donanım bilgisi alınamadı")
            self.error.emit(str(exc))


# v9: Finans iş parçacıkları
class StockWorker(QThread):
    finished = pyqtSignal(str)
    def __init__(self, ticker: str):
        super().__init__(); self.ticker = ticker
    def run(self):
        data = get_stock_price(self.ticker)
        self.finished.emit(format_stock_result(data))

class TechAnalysisWorker(QThread):
    finished = pyqtSignal(str)
    def __init__(self, ticker: str):
        super().__init__(); self.ticker = ticker
    def run(self): self.finished.emit(technical_analysis(self.ticker))

class BriefingWorker(QThread):
    finished = pyqtSignal(str)
    def run(self): self.finished.emit(get_daily_briefing())

class FxBoardWorker(QThread):
    finished = pyqtSignal(str)
    def run(self): self.finished.emit(get_multi_currency_board())

class WatchlistWorker(QThread):
    finished = pyqtSignal(str)
    def run(self): self.finished.emit(get_watchlist_summary())


class ResearchWorker(QThread):
    """Özellik 10: arka plan araştırması (ResearchEngine + mod parametreleri)."""

    result = pyqtSignal(object)      # ResearchReport
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # (bulunan, planlanan)
    cancelled = pyqtSignal()

    def __init__(self, query: str, mode: str, requested_pages, show_filters: bool):
        super().__init__()
        self.query = query
        self.mode = mode
        self.requested_pages = requested_pages
        self.show_filters = show_filters
        self.cancel_event = threading.Event()
        self._response_lock = threading.Lock()
        self._active_response = None

    def cancel(self) -> None:
        self.cancel_event.set()
        with self._response_lock:
            response = self._active_response
        close = getattr(response, "close", None)
        if close is not None:
            try:
                close()
            except Exception:
                logger.exception("[Research] İptal sırasında HTTP yanıtı kapatılamadı")

    def _register_response(self, response) -> None:
        with self._response_lock:
            self._active_response = response
            should_close = response is not None and self.cancel_event.is_set()
        if should_close:
            response.close()

    def run(self):
        try:
            engine = get_research_engine()
            engine.llm_fn = _research_summarize
            report = engine.research(
                self.query, self.mode,
                requested_pages=self.requested_pages,
                show_filters=self.show_filters,
                progress_cb=self.progress.emit,
                cancel=self.cancel_event,
                response_callback=self._register_response)
            if self.cancel_event.is_set():
                self.cancelled.emit()
                return
            self.result.emit(report)
        except Exception as exc:
            if self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                logger.exception("[Research] Worker hatası")
                self.error.emit(str(exc))


class FlowWorker(QThread):
    """Özellik 3: flow adımını arka planda çalıştır (araştırma/uygulama/test)."""

    done = pyqtSignal(object)   # FlowStep
    error = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as exc:
            logger.exception("[Troubleshoot] Adım hatası")
            self.error.emit(str(exc))


class PresentationWorker(QThread):
    """Özellik 1: sunum üretimini (pptx→canva→görsel) arka planda çalıştırır."""

    result = pyqtSignal(object)   # PresentationResult

    def __init__(self, topic, num_slides, tone, audience, content):
        super().__init__()
        self._args = (topic, num_slides, tone, audience, content)

    def run(self):
        try:
            topic, num, tone, audience, content = self._args
            result = build_presentation(
                topic, num, tone=tone, audience=audience, content=content,
                llm_fn=_research_summarize)
            self.result.emit(result)
        except Exception as exc:
            logger.exception("[Present] Worker hatası")
            self.result.emit(
                PresentationResult(False, "none", "", str(exc), 0))


class PromptWorker(QThread):
    """Özellik 9: Prompt Mimarı üretimini arka planda çalıştırır."""

    result = pyqtSignal(str)

    def __init__(self, task: str):
        super().__init__()
        self._task = task

    def run(self):
        try:
            text, report = generate_prompt(self._task, llm_fn=_prompt_llm)
            if not all(report.values()):
                logger.warning("[PromptArchitect] Eksik bölümler: %s", report)
            self.result.emit(text)
        except Exception:
            logger.exception("[PromptArchitect] Worker hatası")
            self.result.emit(build_fallback_prompt(self._task))


class VerifyWorker(QThread):
    """Özellik 8: 3 saniyelik doğrulamayı (self-check) arka planda çalıştırır."""

    done = pyqtSignal(object)   # VerifyResult
    error = pyqtSignal(str)

    def __init__(self, question: str, answer: str):
        super().__init__()
        self._question = question
        self._answer = answer

    def run(self):
        try:
            vr = verify_answer(self._question, self._answer,
                               llm_fn=_research_summarize)
            self.done.emit(vr)
        except Exception as exc:
            logger.exception("[Curriculum] Doğrulama worker hatası")
            self.error.emit(str(exc))

# ══════════════════════════════════════════════════════════════════════════
# ANA PENCERE
class UpdateCheckWorker(QThread):
    """Güncelleme denetimini arka planda çalıştırır (UI thread'ini bloklamaz)."""

    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.result.emit(check_for_update())
        except Exception as exc:  # ağ/JSON hataları tek mesaj olarak kullanıcıya döner
            self.error.emit(str(exc))


# ══════════════════════════════════════════════════════════════════════════
class JarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        db_init()
        self.low_bandwidth_mode = bool(
            SETTINGS.get("low_bandwidth_mode", True)
        )
        configured_low_resource = SETTINGS.get("low_resource_mode")
        if isinstance(configured_low_resource, bool):
            self.low_resource_mode = configured_low_resource
        else:
            memory_bytes = (
                psutil.virtual_memory().total
                if PSUTIL_OK and psutil is not None else None
            )
            self.low_resource_mode = detect_low_resource_mode(
                os.cpu_count(), memory_bytes
            )
        self.engine     = AIEngine()
        self.engine.response_depth = SETTINGS.get("response_depth", "balanced")
        self.engine.low_bandwidth_mode = self.low_bandwidth_mode
        self.session_id = db_new_session()
        self.history    = []
        self.attached   = None
        self.night_mode = False
        self._worker    = None
        self._active_ai_worker = None
        self._active_research_worker = None
        self._update_worker = None
        self._threads   = set()
        self._reminder_check_active = False
        self._closing = False
        self._shutdown_complete = False
        self._shutdown_started_at = None
        self._shutdown_timeout_seconds = 30
        self._session_summary_saved = False
        self._prev_charging = None
        self._wake_listening = False
        self._wake = None
        self.verifier = CommandVerifier()
        self.permission_manager = PermissionManager(
            SETTINGS,
            lambda category, description, result: logger.info(
                "[PermissionAudit] %s: %s — %s", category, description, result
            ),
        )
        self._pending_ui_action = None
        self._pending_task_plan = None
        self._pending_permission_category = None
        self._pending_risk_request = None
        self._authorized_risk_request = None
        self._authorized_task_plan = None
        self._active_task_steps = None
        self._active_task_index = 0
        self._active_task_id = None
        self.task_center = TaskCenter()
        self.skill_registry = create_builtin_skill_registry()
        self.skill_registry.bind("presentation", self._dispatch_presentation_skill)
        self.skill_registry.bind("file_conversion", self._try_convert_file)
        self.skill_registry.bind("local_memory", self._run_local_memory_skill)
        self._awaiting_task_step = False
        self._pending_action_preview = None
        self._stream_bubble = None
        self._theme_dark = True
        self.atlas_enabled = False
        self._atlas_overlay = None
        # Özellik 3: arıza giderme akışı (None = aktif değil).
        self._troubleshoot = None
        self._flow_busy = False  # bir flow adımı çalışıyor mu (çift başlatma koruması)
        # Merkezi pencere yöneticisi (Özellik 6): ATLAS ↔ JARVIS dışlayıcı.
        self._window_manager = WindowManager()
        self._window_manager.register(ActiveWindow.JARVIS, self)
        self._automation = AutomationEngine(self)

        self.setWindowTitle(
            f"J.A.R.V.I.S. v{APP_DISPLAY_VERSION} Apex — Stark Industries 2026"
        )
        self.resize(1340, 850)
        self.setStyleSheet(f"QMainWindow{{background:{C['bg']};}}")
        self.setMinimumSize(960, 620)

        # Özellik 7: durum çerçevesi controller'ı (JARVIS + ATLAS paylaşır).
        self._state_controller = StatusColorController(self)
        # Özellik 10: Deep Research yuvarlak geri sayımı (≥5 dk'da görünür).
        self._countdown = RoundCountdownWidget()
        self._build_ui()
        self._start_monitors()
        self._start_wake_word()
        self._system_tray()
        if not (GROQ_API_KEY or GEMINI_API_KEY):
            QTimer.singleShot(1200, self._show_missing_provider_warning)

        holiday = check_upcoming_holidays()
        if holiday:
            QTimer.singleShot(2000, lambda: self.chat.add_bubble("assistant", holiday))

        # v9: Otomatik brifing (sabah 8-10 arası)
        if (
            SETTINGS.get("briefing_auto", True)
            and not self.low_bandwidth_mode
        ):
            h = datetime.datetime.now().hour
            if 7 <= h <= 10:
                QTimer.singleShot(4000, self._auto_briefing)

        # Otomatik güncelleme denetimi: ~6 sn sonra sessiz, arka planda;
        # ⚙ menüsündeki tercih/kaynak/kip korumaları _maybe_auto_check_updates içinde.
        QTimer.singleShot(6000, self._maybe_auto_check_updates)

    def _build_ui(self):
        fs = SETTINGS.get("font_size", 13)
        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.left = LeftPanel(
            low_bandwidth_mode=self.low_bandwidth_mode,
            low_resource_mode=self.low_resource_mode,
        )
        self.left.session_selected.connect(self._load_session)
        self.left.hardware_ready.connect(self._check_hardware_alerts)
        root.addWidget(self.left)

        mid = QWidget(); mid.setStyleSheet(f"background:{C['bg']};")
        ml = QVBoxLayout(mid); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)

        top = QWidget(); top.setFixedHeight(195)
        top.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};border-radius:28px;")
        tl = QHBoxLayout(top); tl.setContentsMargins(20, 10, 20, 10)
        self.core = CoreWidget(self.low_resource_mode)
        self.core.setFixedSize(220, 175)
        tl.addWidget(self.core)

        ti = QWidget(); ti.setStyleSheet("background:transparent;")
        tv = QVBoxLayout(ti); tv.setContentsMargins(20, 0, 0, 0)
        t1 = QLabel("J.A.R.V.I.S.")
        t1.setStyleSheet(f"color:{C['blue']};font:bold 32px 'Consolas';background:transparent;")
        t2 = QLabel(
            f"v{APP_DISPLAY_VERSION}  'Apex'  —  Stark Industries AI  |  2026"
        )
        t2.setStyleSheet(f"color:{C['subtext']};font:11px 'Consolas';background:transparent;")
        self.status_lbl = QLabel("● SİSTEM AKTİF")
        self.status_lbl.setStyleSheet(
            f"color:{C['green']};font:bold 10px 'Consolas';background:transparent;")
        self.wake_lbl = QLabel(
            "● Hey Jarvis / Apex: Aktif" if SETTINGS.get("wake_word", True) and SR_OK
            else "● Uyandırma: Kapalı")
        self.wake_lbl.setStyleSheet(
            f"color:{C['subtext']};font:9px 'Consolas';background:transparent;")
        # v9: Finans durumu
        self.fin_lbl = QLabel(
            f"● FinCore: {'Aktif (yfinance)' if YFINANCE_OK else 'Sınırlı (yfinance yok)'}")
        self.fin_lbl.setStyleSheet(
            f"color:{C['gold'] if YFINANCE_OK else C['orange']};font:9px 'Consolas';background:transparent;")
        self.atlas_btn = QPushButton("ATLAS")
        self.atlas_btn.setCheckable(True)
        self.atlas_btn.setFixedSize(82, 28)
        self.atlas_btn.setToolTip("ATLAS bilgisayar kontrolünü aç/kapat")
        self.atlas_btn.setStyleSheet(
            f"QPushButton{{background:{C['border']};color:{C['cyan']};border:1px solid {C['cyan']}60;"
            f"border-radius:14px;padding:0;font:bold 9px 'Consolas';}}"
            f"QPushButton:hover{{background:{C['cyan']}20;}}"
            f"QPushButton:checked{{background:{C['cyan']}30;color:#fff;border:1px solid {C['cyan']};}}")
        self.atlas_btn.clicked.connect(self._toggle_atlas)
        tv.addWidget(t1); tv.addWidget(t2); tv.addSpacing(4)
        # status_lbl UI'dan kaldırıldı (Özellik 7); mevcut setText çağrıları
        # patlamasın diye nesne korunur ama gösterilmez.
        self.status_lbl.hide()
        tv.addWidget(self.wake_lbl)
        tv.addWidget(self.fin_lbl)
        tv.addStretch()
        tl.addWidget(ti, 1)
        tl.addWidget(self.atlas_btn, 0, Qt.AlignTop | Qt.AlignRight)
        ml.addWidget(top)

        self.chat = ChatArea(fs); ml.addWidget(self.chat, 1)

        bot = QWidget(); bot.setFixedHeight(116)
        bot.setStyleSheet(
            f"background:{C['panel']};border-top:1px solid {C['border']};"
            "border-bottom-left-radius:18px;border-bottom-right-radius:18px;")
        bl = QVBoxLayout(bot); bl.setContentsMargins(12, 8, 12, 8); bl.setSpacing(4)

        self.operation_status = QLabel("Hazır")
        self.operation_status.setStyleSheet(
            f"color:{C['subtext']};font:9px 'Consolas';background:transparent;")
        bl.addWidget(self.operation_status)

        self.file_lbl = QLabel()
        self.file_lbl.setStyleSheet(
            f"color:{C['orange']};font:9px 'Consolas';background:transparent;")
        bl.addWidget(self.file_lbl)

        ir = QHBoxLayout(); ir.setSpacing(6)

        # Özellik 10: araştırma modu seçici (dropdown).
        self.mode_box = QComboBox()
        self.mode_box.addItem("Normal", "normal")
        self.mode_box.addItem("⚡ Flash Lite", "flash_lite")
        self.mode_box.addItem("⚡ Flash", "flash")
        self.mode_box.addItem("⭐ Pro", "pro")
        self.mode_box.addItem("🔬 Deep Research", "deep")
        self.mode_box.setToolTip("Araştırma modu (Özellik 10)")
        self.mode_box.setFixedHeight(38)
        self.mode_box.setFixedWidth(152)
        self.mode_box.setStyleSheet(
            f"QComboBox{{background:{C['bg']};color:{C['text']};"
            f"border:1px solid {C['border']};border-radius:14px;"
            f"padding:4px 10px;font:11px 'Consolas';}}"
            f"QComboBox:hover{{border:1px solid {C['blue']}80;}}"
            f"QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};"
            f"selection-background-color:{C['blue']}40;}}")
        ir.addWidget(self.mode_box)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setFixedSize(38, 38)
        self.attach_btn.setStyleSheet(
            f"QPushButton{{background:{C['border']};color:{C['blue']};border:1px solid {C['blue']}40;"
            f"border-radius:19px;font:bold 18px;}}"
            f"QPushButton:hover{{background:{C['blue']}30;}}")
        self.attach_btn.clicked.connect(self._show_attach_menu)
        ir.addWidget(self.attach_btn)

        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setFixedSize(38, 38)
        self.mic_btn.setStyleSheet(
            f"QPushButton{{background:{C['border']};color:{C['text']};border:1px solid {C['border']};"
            f"border-radius:19px;font:16px;}}"
            f"QPushButton:hover{{background:{C['blue']}30;}}")
        self.mic_btn.clicked.connect(self._voice_input)
        ir.addWidget(self.mic_btn)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText(
            "Komut verin, Efendim...  |  'brifing', 'döviz', 'hisse THYAO.IS', 'teknik analiz THYAO.IS'")
        self.input_box.setStyleSheet(
            f"QLineEdit{{background:{C['bg']};color:{C['text']};border:1px solid {C['border']};"
            f"border-radius:22px;padding:8px 16px;font:{fs}px 'Consolas';}}"
            f"QLineEdit:focus{{border:1px solid {C['blue']}80;}}")
        self.input_box.returnPressed.connect(self._send)
        ir.addWidget(self.input_box, 1)

        self.cancel_btn = QPushButton("■")
        self.cancel_btn.setFixedSize(38, 38)
        self.cancel_btn.setToolTip(
            "AI yanıtını veya web araştırmasını iptal et. Devam eden ağ okuması "
            "yanıt gelene veya zaman aşımına ulaşana kadar sürebilir."
        )
        self.cancel_btn.setStyleSheet(
            f"QPushButton{{background:{C['red']}30;color:{C['red']};border:1px solid {C['red']}80;"
            "border-radius:19px;font:bold 14px;}"
            f"QPushButton:hover{{background:{C['red']}60;}}")
        self.cancel_btn.clicked.connect(self._cancel_active_operation)
        self.cancel_btn.hide()
        ir.addWidget(self.cancel_btn)

        self.send_btn = QPushButton("▶"); self.send_btn.setFixedSize(44, 38)
        self.send_btn.setStyleSheet(
            f"QPushButton{{background:{C['blue']};color:#fff;border:none;border-radius:19px;font:bold 14px;}}"
            f"QPushButton:hover{{background:{C['blue']}cc;}}")
        self.send_btn.clicked.connect(self._send)
        ir.addWidget(self.send_btn)

        # Özellik 4: sağ alt Ayarlar butonu (en köşe) — kalıcı tercih menüsü.
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(38, 38)
        self.settings_btn.setToolTip("Ayarlar")
        self.settings_btn.setStyleSheet(
            f"QPushButton{{background:{C['border']};color:{C['text']};border:1px solid {C['border']};"
            f"border-radius:19px;font:16px;}}"
            f"QPushButton:hover{{background:{C['blue']}30;}}")
        self.settings_btn.clicked.connect(self._show_settings_menu)
        ir.addWidget(self.settings_btn)

        bl.addLayout(ir); ml.addWidget(bot); root.addWidget(mid, 1)
        # Özellik 7: içeriği ince durum çerçevesiyle sar (üst durum çubuğu yerine).
        self._status_border = StatusBorderWidget(self._state_controller)
        self._status_border.set_content(central)
        self.setCentralWidget(self._status_border)
        self.core.state_changed.connect(self._sync_border)
        self.left.refresh_history()

        name = PROFILE.get("name", "Efendim")
        sessions = PROFILE.get("total_sessions", 1)
        self.chat.add_bubble("assistant",
            f"J.A.R.V.I.S. v{APP_DISPLAY_VERSION} Apex çevrimiçi. Sistemler nominal.\n"
            f"Hoş geldiniz, {name}. Oturum #{sessions}.\n\n"
            f"v{APP_DISPLAY_VERSION} Yenilikleri: ATLAS Arıza Giderme, 4 Kademeli "
            f"Akıllı Arama (Flash Lite/Flash/Pro/Deep), Otomatik Sunum, Dosya "
            f"Dönüştürücü, Müfredat Asistanı (1-12), Prompt Mimarı.\n"
            f"Buyurun.")

    def _toggle_atlas(self, enabled: bool):
        self.atlas_enabled = bool(enabled)
        self.atlas_btn.setText("ATLAS ON" if self.atlas_enabled else "ATLAS")
        self.atlas_btn.setChecked(self.atlas_enabled)
        self.core.set_state("atlas" if self.atlas_enabled else "idle")
        self.status_lbl.setText("● ATLAS MODU AKTİF" if self.atlas_enabled else "● SİSTEM AKTİF")
        if self.atlas_enabled:
            if self._atlas_overlay is None:
                self._atlas_overlay = AtlasOverlay(self._state_controller)
                self._atlas_overlay.pause_requested.connect(self._automation.pause)
                self._atlas_overlay.resume_requested.connect(self._automation.resume)
                self._atlas_overlay.stop_requested.connect(self._stop_atlas_automation)
                self._automation.state_changed.connect(self._atlas_overlay.update_state)
                self._automation.message.connect(self._on_atlas_message)
                # Overlay chat → JarvisWindow köprüsü
                self._atlas_overlay.message_sent.connect(self._on_overlay_message)
                # Manuel kapatma (✕) → JARVIS'e dön
                self._atlas_overlay.close_requested.connect(self._close_atlas)
                # Özellik 3: araştırma modeli Flash/Pro seçimi
                self._atlas_overlay.research_mode_changed.connect(
                    self._on_research_mode)
                self._window_manager.register(ActiveWindow.ATLAS, self._atlas_overlay)
            self.chat.add_bubble(
                "assistant",
                "Atlas modu aktif. Bilgisayar/web otomasyonu ve yerel hafıza hazır.",
            )
            if self._atlas_overlay:
                self._atlas_overlay.add_message(
                    "jarvis",
                    "ATLAS aktif. Otomasyon ve yerel hafıza komutlarınızı buradan da yazabilirsiniz.",
                )
            # Karşılıklı dışlayıcı: ATLAS açılınca JARVIS gizlenir.
            self._window_manager.open_atlas()
        else:
            if self._atlas_overlay is not None:
                self._automation.stop()
            self._cancel_troubleshoot()  # Özellik 3: ATLAS kapanınca akış da biter
            # ATLAS kapanınca JARVIS geri açılır; ikisi birden görünmez.
            self._window_manager.open_jarvis()

    def _stop_atlas_automation(self):
        """Overlay '■ Bitir': otomasyonu durdurup ATLAS'ı kapatır, JARVIS'e döner."""
        self._toggle_atlas(False)

    def _close_atlas(self):
        """ATLAS başlık çubuğundaki ✕: JARVIS penceresine dön."""
        logger.info("[ATLAS] Manuel kapatma istendi.")
        self._toggle_atlas(False)

    def _on_atlas_message(self, message: str):
        """Otomasyon motoru mesajı → hem ana chat hem overlay log."""
        if not message:
            return
        # Ana chat'e küçük log notu olarak değil, sadece önemli mesajlar
        if any(kw in message for kw in ("✓", "hata", "başlatılamadı", "tamamlandı", "bulunamadı")):
            self.chat.add_bubble("assistant", message)
        # Her otomasyon logu overlay'e düşsün
        if self._atlas_overlay:
            self._atlas_overlay.add_log(message)

    def _on_overlay_message(self, text: str):
        """Overlay panel'den gelen kullanıcı mesajını işle, cevabı overlay'e yaz."""
        if not text:
            return
        context_directive = text
        context_query = extract_context_query(text)
        if context_query is not None and not context_query:
            if self._atlas_overlay:
                self._atlas_overlay.add_message(
                    "jarvis",
                    "İki nokta üst üste işaretinden sonra isteğinizi yazın.",
                )
            return
        if context_query is not None:
            text = context_query
        # Özellik 3: arıza akışı aktifse mesaj akış kanalına gider (AI'ya değil).
        if self._route_troubleshoot(text):
            return
        try:
            memory_reply = self._handle_atlas_memory_command(text)
        except Exception as exc:
            logger.exception("[ATLAS][Memory] Yerel hafıza işlemi başarısız")
            if self._atlas_overlay:
                self._atlas_overlay.add_message(
                    "jarvis", f"Yerel hafıza işlemi tamamlanamadı: {exc}"
                )
            return
        if memory_reply is not None:
            self.history.extend([
                {"role": "user", "content": text},
                {"role": "assistant", "content": memory_reply},
            ])
            self.history = self.history[-40:]
            db_save_msg(self.session_id, "user", text)
            db_save_msg(self.session_id, "assistant", memory_reply)
            if self._atlas_overlay:
                self._atlas_overlay.add_message("jarvis", memory_reply)
            return
        local_context = ""
        if context_query is not None:
            _, local_context, authorized = self._authorize_local_context(
                context_directive
            )
            if not authorized:
                if self._atlas_overlay:
                    self._atlas_overlay.add_message(
                        "jarvis",
                        "İstek gönderilmedi; yerel sohbet alıntıları paylaşılmadı.",
                    )
                return
        # Ana chat geçmişine de ekle (senkronize)
        self.history.append({"role": "user", "content": text})
        if len(self.history) > 40:
            self.history = self.history[-40:]
        db_save_msg(self.session_id, "user", text)

        extra = get_pdf_context() if REMOTE_CONTEXT_ENABLED else ""
        if REMOTE_CONTEXT_ENABLED:
            memory_context = atlas_memory_build_context(text)
            if memory_context:
                extra = f"{extra}\n\n{memory_context}".strip()
        if local_context:
            extra = f"{extra}\n\n{local_context}".strip()
        feedback_text = (
            ""
            if classify_ai_request(text) is AIRequestType.WEB_SEARCH
            else format_answer_feedback(
                text, local_sources_shared=REMOTE_CONTEXT_ENABLED
            )
        )
        worker = AIWorker(
            self.engine, self.history.copy(), text, extra, feedback_text
        )

        def _on_finish(reply: str):
            if reply:
                self.history.append({"role": "assistant", "content": reply})
                db_save_msg(self.session_id, "assistant", reply)
                if self._atlas_overlay:
                    self._atlas_overlay.add_message("jarvis", reply)

        def _on_tool(tc_str: str):
            self._on_tool_call(tc_str)

        worker.finished.connect(_on_finish)
        worker.tool_call.connect(_on_tool)
        worker.error.connect(lambda e: self._atlas_overlay.add_log(f"Hata: {e}") if self._atlas_overlay else None)
        self._prepare_ai_worker(worker)
        self._start_worker(worker)

    # ── Menü ──────────────────────────────────────────────────────────────
    def _prepare_ai_worker(self, worker: AIWorker) -> None:
        if self._active_task_id is not None:
            worker._jarvis_task_id = self._active_task_id
            worker._jarvis_task_owned = False
        else:
            task_id = self.task_center.create(
                f"AI: {worker.msg[:90]}",
                [(worker.msg[:180] or "AI yanıtı", "conversation")],
                cancel_callback=worker.cancel,
            )
            self.task_center.start(task_id, "AI isteği gönderiliyor.")
            worker._jarvis_task_id = task_id
            worker._jarvis_task_owned = True
        self._active_ai_worker = worker
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.show()
        self.operation_status.setText("AI isteği gönderiliyor...")
        worker.progress.connect(self.operation_status.setText)
        worker.progress.connect(
            lambda status, task_id=worker._jarvis_task_id:
            self._update_task_message(task_id, status)
            if worker._jarvis_task_owned else None
        )
        worker.finished.connect(
            lambda reply: self._finish_ai_worker(
                worker,
                TaskStatus.SUCCEEDED if reply else TaskStatus.FAILED,
                "Yanıt tamamlandı." if reply else "Boş yanıt.",
            )
        )
        worker.error.connect(
            lambda error: self._on_ai_worker_error(worker, error)
        )
        worker.cancelled.connect(lambda: self._on_ai_cancelled(worker))

    def _finish_ai_worker(
        self,
        worker: AIWorker,
        task_status: TaskStatus | None = None,
        message: str = "",
    ) -> None:
        if self._active_ai_worker is not worker:
            return
        if worker._jarvis_task_owned and task_status is not None:
            try:
                self.task_center.update_step(
                    worker._jarvis_task_id,
                    0,
                    (
                        StepStatus.SUCCEEDED
                        if task_status is TaskStatus.SUCCEEDED
                        else StepStatus.FAILED
                    ),
                    message,
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] AI görev sonucu kaydedilemedi.")
            self._finish_task_record(worker._jarvis_task_id, task_status, message)
        self._active_ai_worker = None
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.hide()
        self.operation_status.setText("Hazır")

    def _update_task_message(self, task_id: str, message: str) -> None:
        try:
            self.task_center.update_message(task_id, message)
        except KeyError:
            logger.warning("[TaskCenter] Güncellenemeyen görev: %s", task_id)

    def _finish_task_record(
        self, task_id: str | None, status: TaskStatus, message: str = ""
    ) -> None:
        if task_id is None:
            return
        try:
            self.task_center.finish(task_id, status, message)
        except KeyError:
            logger.warning("[TaskCenter] Tamamlanamayan görev: %s", task_id)

    def _on_ai_worker_error(self, worker: AIWorker, message: str) -> None:
        if worker._jarvis_task_owned:
            try:
                self.task_center.update_step(
                    worker._jarvis_task_id, 0, StepStatus.FAILED, message[:300]
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] AI hatası kaydedilemedi.")
            self._finish_task_record(
                worker._jarvis_task_id, TaskStatus.FAILED, message
            )
        self._finish_ai_worker(worker)
        self._on_error(message)

    def _cancel_task_from_center(self, task_id: str) -> None:
        if self._pending_task_plan and self._pending_task_plan[2] == task_id:
            self._pending_task_plan = None
            self._authorized_task_plan = None
            self._active_task_id = None
            record = next(
                (item for item in self.task_center.snapshot()
                 if item.task_id == task_id),
                None,
            )
            if record:
                for index, step in enumerate(record.steps):
                    if step.status is StepStatus.QUEUED:
                        self.task_center.update_step(
                            task_id, index, StepStatus.CANCELLED, "Plan iptal edildi."
                        )
            self._finish_task_record(
                task_id, TaskStatus.CANCELLED, "Plan iptal edildi; adımlar başlatılmadı."
            )
            return

        worker = self._active_ai_worker
        if worker is not None and getattr(worker, "_jarvis_task_id", None) == task_id:
            worker.cancel()
        else:
            research_worker = self._active_research_worker
            if research_worker is not None and getattr(
                research_worker, "_jarvis_task_id", None
            ) == task_id:
                research_worker.cancel()
            else:
                uncancellable_worker = next(
                    (
                        candidate for candidate in self._threads
                        if getattr(candidate, "_jarvis_task_id", None) == task_id
                        and candidate.isRunning()
                    ),
                    None,
                )
                if uncancellable_worker is not None:
                    raise RuntimeError(
                        "Bu adım güvenli biçimde kesilemez; mevcut adım devam eder."
                    )

        if self._active_task_id == task_id and self._awaiting_task_step:
            try:
                self.task_center.update_step(
                    task_id,
                    self._active_task_index,
                    StepStatus.CANCELLED,
                    "Kullanıcı iptal etti.",
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] İptal edilen adım kaydedilemedi.")
        self._active_task_steps = None
        self._awaiting_task_step = False
        self.verifier.cancel_pending()
        self._pending_ui_action = None
        self._pending_action_preview = None
        self._pending_permission_category = None
        if worker is not None and getattr(worker, "_jarvis_task_id", None) == task_id:
            return
        research_worker = self._active_research_worker
        if research_worker is not None and getattr(research_worker, "_jarvis_task_id", None) == task_id:
            return
        self._active_task_id = None
        self._finish_task_record(
            task_id, TaskStatus.CANCELLED, "Kullanıcı tarafından iptal edildi."
        )

    def _cancel_active_operation(self) -> None:
        worker = self._active_ai_worker
        if worker is not None and worker.isRunning():
            task_id = getattr(worker, "_jarvis_task_id", None)
            if task_id is not None:
                try:
                    self.task_center.request_cancel(task_id)
                except Exception as exc:
                    logger.exception("[TaskCenter] AI görevi iptal edilemedi")
                    self.operation_status.setText(f"İptal desteklenmiyor: {exc}")
            else:
                worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.operation_status.setText(
                "İptal istendi; açık akış kapatılıyor. Bağlantı kuruluyorsa zaman aşımı beklenebilir."
            )
            return
        research_worker = self._active_research_worker
        if research_worker is not None and research_worker.isRunning():
            task_id = getattr(research_worker, "_jarvis_task_id", None)
            if task_id is not None:
                try:
                    self.task_center.request_cancel(task_id)
                except Exception as exc:
                    logger.exception("[TaskCenter] Araştırma iptal edilemedi")
                    self.operation_status.setText(f"İptal desteklenmiyor: {exc}")
            else:
                research_worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.operation_status.setText(
                "Araştırma iptali istendi; açık yanıt kapatılıyor. Bağlantı kuruluyorsa zaman aşımı beklenebilir."
            )
            return
        self.operation_status.setText("İptal edilecek işlem yok.")

    def _on_ai_cancelled(self, worker: AIWorker) -> None:
        if self._stream_bubble is not None:
            partial = self._stream_bubble.message_label.text()
            if partial:
                self._stream_bubble.message_label.setText(
                    partial + "\n\n[Yanıt iptal edildi]"
                )
            else:
                self._stream_bubble.setParent(None)
                self._stream_bubble.deleteLater()
            self._stream_bubble = None
        task_id = getattr(worker, "_jarvis_task_id", None)
        owned = getattr(worker, "_jarvis_task_owned", False)
        step_index = (
            self._active_task_index
            if self._active_task_id == task_id and not owned
            else 0
        )
        try:
            self.task_center.update_step(
                task_id, step_index, StepStatus.CANCELLED, "AI işlemi iptal edildi."
            )
        except (KeyError, IndexError):
            logger.exception("[TaskCenter] AI iptali kaydedilemedi.")
        self._finish_task_record(
            task_id,
            TaskStatus.CANCELLED,
            "AI işlemi iptal edildi.",
        )
        self._finish_ai_worker(worker)
        if self._active_task_id == task_id:
            self._active_task_id = None
            self._active_task_steps = None
            self._awaiting_task_step = False
        if self._active_ai_worker is None:
            self.operation_status.setText("AI yanıtı iptal edildi.")

    def _start_worker(self, worker):
        if (
            self._active_task_id is not None
            and getattr(worker, "_jarvis_task_id", None) is None
        ):
            worker._jarvis_task_id = self._active_task_id
            worker._jarvis_task_owned = False
        self._threads.add(worker)
        worker.finished.connect(lambda: self._release_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _release_worker(self, worker):
        self._threads.discard(worker)
        if worker is self._worker:
            self._worker = None

    # ── ARAŞTIRMA (Özellik 10) ──────────────────────────────────────────────
    def _start_research(self, mode: str, query: str) -> None:
        """Seçili modda arka plan araştırması başlat; ≥5 dk ise geri sayım göster."""
        params = MODES.get(mode)
        if params is None:
            self._add_response(f"Bilinmeyen araştırma modu: {mode}")
            return
        self.core.set_state("thinking")
        self.status_lbl.setText(f"● ARAŞTIRMA: {params.label.upper()}...")
        self.operation_status.setText(f"Araştırma başlatılıyor: {params.label}...")
        note = f"🔬 {params.label} moduyla araştırılıyor: {query}"
        self.chat.add_bubble("assistant", note)
        self._mirror_to_overlay("jarvis", note)
        show_filters = bool(SETTINGS.get("show_filters", True))
        worker = ResearchWorker(query, mode, parse_requested_pages(query), show_filters)
        if self._active_task_id is not None:
            worker._jarvis_task_id = self._active_task_id
            worker._jarvis_task_owned = False
        else:
            task_id = self.task_center.create(
                f"Araştırma: {query[:90]}",
                [(f"{params.label}: {query[:160]}", "research")],
                cancel_callback=worker.cancel,
            )
            self.task_center.start(task_id, "Araştırma başlatılıyor.")
            worker._jarvis_task_id = task_id
            worker._jarvis_task_owned = True
        self._active_research_worker = worker
        self.input_box.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.show()
        worker.result.connect(self._on_research_done)
        worker.error.connect(self._on_research_error)
        worker.cancelled.connect(lambda: self._on_research_cancelled(worker))
        worker.progress.connect(
            lambda d, t: (
                self.status_lbl.setText(
                    f"● KAYNAK {d}/{t} — {params.label.upper()}"),
                self.operation_status.setText(
                    f"Kaynaklar taranıyor: {d}/{t} — {params.label}"),
                self._update_task_message(
                    worker._jarvis_task_id,
                    f"Kaynaklar taranıyor: {d}/{t} — {params.label}",
                )
            ))
        if should_show_countdown(params.estimate_s):
            self._countdown.start_countdown(int(params.estimate_s))
        self._start_worker(worker)

    def _on_research_done(self, report) -> None:
        """Araştırma bitti → geri sayımı kapat, raporu sun (mirror dahil)."""
        self._countdown.stop_countdown()
        worker = self._active_research_worker
        if worker is not None and getattr(worker, "_jarvis_task_owned", False):
            try:
                self.task_center.update_step(
                    worker._jarvis_task_id,
                    0,
                    StepStatus.SUCCEEDED,
                    "Araştırma tamamlandı.",
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] Araştırma sonucu kaydedilemedi.")
            self._finish_task_record(
                worker._jarvis_task_id, TaskStatus.SUCCEEDED, "Araştırma tamamlandı."
            )
        self._finish_research_worker(worker)
        self.operation_status.setText("Araştırma tamamlandı.")
        self._add_response(report.text or "Araştırma bitti ancak rapor boş.")

    def _on_research_error(self, message: str) -> None:
        self._countdown.stop_countdown()
        worker = self._active_research_worker
        if worker is not None and getattr(worker, "_jarvis_task_owned", False):
            try:
                self.task_center.update_step(
                    worker._jarvis_task_id, 0, StepStatus.FAILED, message[:300]
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] Araştırma hatası kaydedilemedi.")
            self._finish_task_record(
                worker._jarvis_task_id, TaskStatus.FAILED, message
            )
        self._finish_research_worker(self._active_research_worker)
        self.operation_status.setText("Araştırma tamamlanamadı.")
        self._on_error(message)

    def _finish_research_worker(self, worker) -> None:
        if worker is None or self._active_research_worker is not worker:
            return
        self._active_research_worker = None
        self.input_box.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.hide()

    def _on_research_cancelled(self, worker: ResearchWorker) -> None:
        self._countdown.stop_countdown()
        task_id = getattr(worker, "_jarvis_task_id", None)
        owned = getattr(worker, "_jarvis_task_owned", False)
        step_index = (
            self._active_task_index
            if self._active_task_id == task_id and not owned
            else 0
        )
        try:
            self.task_center.update_step(
                task_id, step_index, StepStatus.CANCELLED, "Araştırma iptal edildi."
            )
        except (KeyError, IndexError):
            logger.exception("[TaskCenter] Araştırma iptali kaydedilemedi.")
        self._finish_task_record(
            task_id,
            TaskStatus.CANCELLED,
            "Web araştırması iptal edildi.",
        )
        self._finish_research_worker(worker)
        if self._active_task_id == getattr(worker, "_jarvis_task_id", None):
            self._active_task_id = None
            self._active_task_steps = None
            self._awaiting_task_step = False
        self.operation_status.setText("Web araştırması iptal edildi.")

    # ── ARIZA GİDERME AKIŞI (Özellik 3) ─────────────────────────────────────
    def _start_troubleshoot(self, os_name: str) -> None:
        """'+' → Arıza → OS: akışı kur ve ATLAS'ı aç (JARVIS gizlenir — Özellik 6)."""
        running = "Windows" if sys.platform.startswith("win") else "macOS"
        self._troubleshoot = create_flow(os_name, research_mode="flash")
        self._flow_busy = False
        logger.info("[Troubleshoot] Akış başlatıldı (%s)", os_name)
        self._toggle_atlas(True)
        if self._atlas_overlay is None:
            return
        self._atlas_overlay.update_state("WAITING")
        note = f"🩹 Arıza modu ({os_name}) aktif. Sorunu serbest metinle yazın."
        if os_name != running:
            note += (f"\n⚠ Bu cihaz {running}; {os_name} için yalnızca "
                     "araştırma yapılabilir.")
        note += "\nAraştırma modeli: Flash (üstteki seçimden Pro'ya geçilebilir)."
        self._atlas_overlay.add_message("jarvis", note)

    def _on_research_mode(self, mode: str) -> None:
        """Overlay Flash/Pro seçimi → aktif akışın araştırma modeli."""
        if self._troubleshoot is not None:
            self._troubleshoot.research_mode = mode
            if self._atlas_overlay:
                self._atlas_overlay.add_log(f"Araştırma modeli → {mode.upper()}")

    def _cancel_troubleshoot(self) -> None:
        if self._troubleshoot is not None:
            logger.info("[Troubleshoot] Akış iptal edildi.")
            self._troubleshoot = None
        self._flow_busy = False

    def _route_troubleshoot(self, text: str) -> bool:
        """Arıza akışı aktifse overlay mesajını akışa yönlendir (True = yutuldu)."""
        flow = self._troubleshoot
        if flow is None:
            return False
        if self._flow_busy:
            if self._atlas_overlay:
                self._atlas_overlay.add_log("İşlem devam ediyor, lütfen bekleyin.")
            return True
        t = " ".join((text or "").lower().split())
        yes = {"evet", "yes", "çözüldü", "cozuldu", "oldu", "tamam",
               "yapıldı", "yapildi", "tamamdır", "tamamdir"}
        no = {"hayır", "hayir", "no", "olmadı", "olmadi", "çözülmedi",
              "cozulmedi", "değil", "degil"}
        if flow.state is FlowState.WAITING:
            if self._atlas_overlay:
                self._atlas_overlay.update_state("RESEARCHING")
                self._atlas_overlay.add_log("Araştırma başlıyor...")
            self._run_flow(lambda: flow.submit(text))
            return True
        if flow.pending_danger:
            if t in yes:
                self._run_flow(lambda: flow.approve_danger(True))
            elif t in no:
                self._run_flow(lambda: flow.approve_danger(False))
            elif self._atlas_overlay:
                self._atlas_overlay.add_message(
                    "jarvis", "Tehlikeli adım: 'evet' veya 'hayır' yazın.")
            return True
        if flow.state is FlowState.CONFIRMING:
            if t in yes:
                self._run_flow(lambda: flow.user_verdict(True))
            elif t in no:
                self._run_flow(lambda: flow.user_verdict(False))
            elif self._atlas_overlay:
                self._atlas_overlay.add_message(
                    "jarvis", "'Bu çözüldü mü?' — lütfen 'evet' veya 'hayır'.")
            return True
        return False  # DONE/EXHAUSTED → normal sohbete düş

    def _run_flow(self, fn) -> None:
        """Flow adımını worker thread'de çalıştır; sonuç _on_flow_step'e gelir."""
        self._flow_busy = True
        worker = FlowWorker(fn)
        worker.done.connect(self._on_flow_step)
        worker.error.connect(self._on_flow_error)
        self._start_worker(worker)

    def _on_flow_step(self, step) -> None:
        """Flow adımı geldi → overlay'i güncelle, zinciri sürdür (otomatik)."""
        self._flow_busy = False
        flow = self._troubleshoot
        if flow is None or step is None:
            return
        if self._atlas_overlay:
            self._atlas_overlay.update_state(step.state.value)
            if step.state in (FlowState.APPLYING, FlowState.CONFIRMING,
                              FlowState.DONE, FlowState.EXHAUSTED):
                self._atlas_overlay.add_message("jarvis", step.message)
            else:
                self._atlas_overlay.add_log(step.message)
        if flow.pending_danger:
            return  # kullanıcı 'evet'/'hayır' bekleniyor
        if step.state is FlowState.APPLYING and flow.current is not None:
            self._run_flow(flow.apply_current)   # otomatik zincir
            return
        if step.state is FlowState.TESTING:
            self._run_flow(flow.run_test)
            return
        if step.state is FlowState.DONE:
            # Spec: çözüldü → ATLAS kapanır, JARVIS penceresi geri gelir.
            QTimer.singleShot(1500, self._close_troubleshoot)
            return
        if step.state is FlowState.EXHAUSTED:
            flow.reset()  # mesaj gösterildi; yeni problem beklenebilir

    def _on_flow_error(self, message: str) -> None:
        self._flow_busy = False
        if self._atlas_overlay:
            self._atlas_overlay.add_message("jarvis", f"⚠ Akış hatası: {message}")
            self._atlas_overlay.update_state("STOPPED")
        if self._troubleshoot is not None:
            self._troubleshoot.reset()

    def _close_troubleshoot(self) -> None:
        """Çözüldü → akışı kapat; ATLAS kapanır, JARVIS döner (Özellik 6)."""
        self._cancel_troubleshoot()
        if self.atlas_enabled:
            self._toggle_atlas(False)

    # ── SUNUM (Özellik 1) ─────────────────────────────────────────────────
    def _start_presentation(self, text: str) -> None:
        """Komuttan konu/slayt sayısı/ton/hedef kitleyi ayıkla; worker'da üret."""
        t = text.lower()
        m_num = re.search(r"(\d+)\s*(?:slayt|sayfa)", t)
        num = int(m_num.group(1)) if m_num else None
        m_tone = re.search(r"ton(?:u)?\s*[:=]\s*(\w+)", t)
        tone = m_tone.group(1) if m_tone else ""
        m_aud = re.search(r"hedef(?:\s*kitle)?\s*[:=]\s*([^,;.]+)", t)
        audience = m_aud.group(1).strip() if m_aud else ""
        topic = text
        for pat in (
            r"ton(?:u)?\s*[:=]\s*\w+",
            r"hedef(?:\s*kitle)?\s*[:=]\s*[^,;.]+",
            r"\d+\s*(?:slayt|sayfa)",
            r"(?:sunum|slayt|prezentasyon)",
            r"(?:hazırla|olustur|oluştur|yap|yarat)",
            r"[:\-]",
        ):
            topic = re.sub(pat, " ", topic, flags=re.IGNORECASE)
        topic = " ".join(topic.split()) or text
        note = f"📊 Sunum hazırlanıyor: {topic}"
        if num:
            note += f" ({num} slayt)"
        note += "\nFallback zinciri: .pptx → Canva → PNG slayt seti."
        self.chat.add_bubble("assistant", note)
        worker = PresentationWorker(topic, num, tone, audience, "")
        task_owned = self._active_task_id is None
        task_id = self._active_task_id
        if task_owned:
            task_id = self.task_center.create(
                f"Sunum: {topic[:90]}",
                [(f"{num or 'Otomatik'} slayt — {topic[:150]}", "presentation")],
            )
            self.task_center.start(task_id, "Sunum hazırlanıyor.")
        worker.result.connect(
            lambda result: self._on_presentation_done(
                result, task_id if task_owned else None
            )
        )
        self._start_worker(worker)

    def _on_presentation_done(self, result, task_id: str | None = None) -> None:
        """Sunum bitti → yöntemi bildir, dosyayı sistemle aç (Özellik 2)."""
        if not getattr(result, "ok", False):
            if task_id:
                try:
                    self.task_center.update_step(
                        task_id,
                        0,
                        StepStatus.FAILED,
                        getattr(result, "message", "Sunum üretilemedi")[:300],
                    )
                except (KeyError, IndexError):
                    logger.exception("[TaskCenter] Sunum hatası kaydedilemedi.")
                self._finish_task_record(
                    task_id, TaskStatus.FAILED,
                    getattr(result, "message", "Sunum üretilemedi"),
                )
            self._on_error(getattr(result, "message", "Sunum üretilemedi"))
            return
        if task_id:
            try:
                self.task_center.update_step(
                    task_id, 0, StepStatus.SUCCEEDED, "Sunum hazırlandı."
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] Sunum sonucu kaydedilemedi.")
            self._finish_task_record(
                task_id, TaskStatus.SUCCEEDED, "Sunum hazırlandı."
            )
        lines = [f"📊 {result.message}", f"Yöntem: {result.method.upper()}"]
        if result.method == "pptx" and result.path:
            lines.append(get_platform_service().show_file(result.path))
        elif result.method == "images" and result.path:
            lines.append(get_platform_service().show_file(
                str(Path(result.path).parent)))
        self._add_response("\n".join(lines))

    # ── PROMPT MİMARI (Özellik 9) ────────────────────────────────────────
    def _start_prompt_architect(self, text: str) -> None:
        """İstek metninden görevi çıkar; 8 maddelik checklist ile üret."""
        task = re.sub(
            r"(?:lütfen\s+)?(?:bana\s+)?(?:detaylı\s+)?prompt\s*"
            r"(?:yaz|oluştur|hazırla|üret)?",
            " ", text, flags=re.IGNORECASE)
        task = task.strip(" :-") or text
        self.chat.add_bubble(
            "assistant", "🧠 Prompt Mimarı: 8 maddelik checklist ile üretiliyor...")
        worker = PromptWorker(task)
        worker.result.connect(self._add_response)
        self._start_worker(worker)

    # ── DOSYA DÖNÜŞTÜRME (Özellik 5) ─────────────────────────────────────
    def _try_convert_file(self, text: str) -> str | None:
        """"bunu pdf yap" gibi isteği dönüştür; None → özel komut değil."""
        t = text.lower()
        pattern = (r"\b(pdf|png|jpe?g|txt|text|metin)\b\s*(?:'e|'ya|e|ya)?\s*"
                   r"(?:yap|çevir|cevir|dönüştür|donustur)")
        m = re.search(pattern, t)
        if m:
            raw = m.group(1)
        else:
            m2 = re.search(
                r"(?:yap|çevir|cevir|dönüştür|donustur)\s*(?:->|→)?\s*"
                r"(pdf|png|jpe?g|txt|text|metin)", t)
            if not m2:
                return None
            raw = m2.group(1)
        target = {"text": "txt", "metin": "txt", "jpeg": "jpg"}.get(raw, raw)
        src = self.attached
        if not src:
            m_path = re.search(
                r"([\w\s\.\:\~\/\\-]+\.(?:pdf|png|jpe?g|txt))", text,
                re.IGNORECASE)
            if m_path:
                src = m_path.group(1).strip()
        if not src:
            return ("Dönüştürmek için bir dosya ekleyin (+ → Dosya / PDF) "
                    "veya dosya yolunu yazın.\n"
                    "Desteklenen: JPG/PNG→PDF, PDF→JPG/PNG, PDF→TXT, JPG↔PNG.")
        result = convert_file(src, target)
        if self.attached:
            self.attached = None
            self.file_lbl.setText("")
        if result.outputs:
            result.message += "\n" + "\n".join(f"• {p}" for p in result.outputs)
        return result.message

    # ── EĞİTİM MODU + 3 SN DOĞRULAMA (Özellik 8) ─────────────────────────
    def _start_education(self, text: str, extra_context: str = "") -> None:
        """Eğitim sorusu: müfredat bağlamıyla cevaplat, sonra 3 sn doğrula."""
        grade = estimate_grade(text)
        subject = subject_of(text)
        ctx = curriculum_context(grade, subject)
        if extra_context:
            ctx = f"{ctx}\n\n{extra_context}"
        level = f"{grade}. sınıf" if grade else "genel seviye"
        self.chat.add_bubble(
            "assistant",
            f"🎓 Eğitim modu ({level}) — cevap sunulmadan önce 3 sn "
            f"doğrulanacak (mavi çerçeve = meşgul).")
        worker = AIWorker(self.engine, self.history.copy(), text, ctx)
        self._prepare_ai_worker(worker)
        worker.finished.connect(
            lambda draft: self._verify_education(text, draft, grade))
        worker.tool_call.connect(self._on_tool_call)
        self._start_worker(worker)

    def _verify_education(self, question: str, draft: str, grade) -> None:
        """Cevabı sunmadan ÖNCE 3 sn'lik self-check (arayüz: mavi durum)."""
        if not draft:
            self._on_error("Eğitim yanıtı boş.")
            return
        self.status_lbl.setText("● DOĞRULANIYOR...")
        self.core.set_state("thinking")
        vw = VerifyWorker(question, draft)
        vw.done.connect(lambda vr: self._finish_education(draft, grade, vr))
        vw.error.connect(self._on_error)
        self._start_worker(vw)

    def _finish_education(self, draft: str, grade, vr) -> None:
        """Doğrulama bitti → cevap + güven raporu + seviye notu birlikte sun."""
        emoji = {"doğru": "✅", "yanlış": "❌"}.get(vr.verdict, "⚠️")
        grade_note = (f"📚 {grade}. sınıf müfredatına göre ayarlandı."
                      if grade else "📚 Sınıf belirtilmedi (genel anlatım).")
        note = (
            f"\n\n—\n{emoji} Doğrulama ({vr.elapsed:.0f} sn): {vr.verdict} "
            f"· güven %{int(vr.confidence * 100)}\n{vr.reason}\n{grade_note}")
        self._add_response(draft + note)

    def _show_attach_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
            f"font:11px 'Consolas';}}"
            f"QMenu::item:selected{{background:{C['blue']}30;}}")
        # Özellik 4: ATLAS seçeneği EN ÜSTTE.
        menu.addAction("⚡ ATLAS", lambda: self._toggle_atlas(True))
        # Özellik 3: Arıza → alt menü Windows/macOS (hover ile açılır).
        ariza_menu = menu.addMenu("🩹 Arıza")
        ariza_menu.addAction("Windows", lambda: self._start_troubleshoot("Windows"))
        ariza_menu.addAction("macOS", lambda: self._start_troubleshoot("macOS"))
        menu.addSeparator()
        menu.addAction("📰 Günlük Brifing", self._fetch_briefing)
        menu.addAction("💱 Kur Paneli", self._fetch_fx_board)
        menu.addAction("📈 Takip Listesi", self._fetch_watchlist)
        menu.addSeparator()
        menu.addAction("📎 Dosya / PDF Yükle", self._attach_file)
        menu.addAction("⚡ Speedtest", self._run_speedtest)
        menu.addAction("📰 Haberler (Başlık)", lambda: self._fetch_news(False))
        menu.addAction("📰 Haberler (Detay)",  lambda: self._fetch_news(True))
        menu.addAction("🗑 Gereksiz Dosyaları Bul",
                       lambda: self._add_response(find_junk_files()))
        menu.addAction("🖥 Masaüstü Kısayolu",
                       lambda: self._add_response(create_desktop_shortcut()))
        menu.addAction("📅 Resmî Tatiller",
                       lambda: self._add_response(get_all_holidays()))
        menu.addSeparator()
        menu.addAction("👤 Profilimi Göster", self._show_profile)
        menu.exec(self.attach_btn.mapToGlobal(self.attach_btn.rect().bottomLeft()))

    def _mirror_to_overlay(self, role: str, text: str) -> None:
        """ATLAS açıkken JARVIS tarafındaki konuşmayı overlay'e yansıt (Özellik 4/6)."""
        if not text or self._atlas_overlay is None or not self._atlas_overlay.isVisible():
            return
        try:
            self._atlas_overlay.add_message(role, text)
        except Exception as exc:
            logger.warning("[ATLAS] Overlay'e yansıtılamadı: %s", exc)

    def _show_settings_menu(self):
        """Sağ alt ⚙ butonu: kalıcı tercihler (IP + makine kimliği bazlı)."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};"
            f"font:11px 'Consolas';}}"
            f"QMenu::item:selected{{background:{C['blue']}30;}}")
        auto_action = menu.addAction("ATLAS'ı Otomatik Aç")
        auto_action.setCheckable(True)
        auto_action.setChecked(bool(
            load_device_pref(SETTINGS, "atlas_auto_open", True)))

        def _toggle_auto(checked: bool) -> None:
            save_device_pref(SETTINGS, "atlas_auto_open", bool(checked))
            settings_save(SETTINGS)
            logger.info("[Settings] ATLAS otomatik aç = %s (ip=%s, machine=%s)",
                        checked, get_local_ip(), _machine_short())

        auto_action.triggered.connect(_toggle_auto)

        # Özellik 10: Filtreler bölümünü raporlarda göster/gizle.
        filt_action = menu.addAction("Filtre sonucunu göster")
        filt_action.setCheckable(True)
        filt_action.setChecked(bool(SETTINGS.get("show_filters", True)))

        def _toggle_filters(checked: bool) -> None:
            SETTINGS["show_filters"] = bool(checked)
            settings_save(SETTINGS)
            logger.info("[Settings] Filtre gösterimi = %s", checked)

        filt_action.triggered.connect(_toggle_filters)

        # Özellik 2: otomatik başlatma (PlatformService üzerinden, platforma özel).
        svc = get_platform_service()
        start_action = menu.addAction("Otomatik Başlat")
        start_action.setCheckable(True)
        start_action.setChecked(svc.auto_start_enabled())

        def _toggle_autostart(checked: bool) -> None:
            msg = svc.set_auto_start(bool(checked))
            logger.info("[Settings] %s", msg)
            start_action.setChecked(svc.auto_start_enabled())
            self.chat.add_bubble("assistant", f"⚙ {msg}")

        start_action.triggered.connect(_toggle_autostart)

        # Otomatik güncelleme denetimi (opt-out): açılışta sessiz sürüm kontrolü.
        auto_upd_action = menu.addAction("Güncellemeleri otomatik denetle")
        auto_upd_action.setCheckable(True)
        auto_upd_action.setChecked(bool(
            load_device_pref(SETTINGS, "auto_update_check", True)))
        auto_upd_action.setToolTip(
            "Açılıştan birkaç saniye sonra HTTPS yayın kaynağını sessizce "
            "denetler; dosya indirmez/kurmaz. Kaynak ayarlı değilse veya "
            "düşük internet modu açıksa hiçbir şey yapmaz."
        )

        def _toggle_auto_update(checked: bool) -> None:
            save_device_pref(SETTINGS, "auto_update_check", bool(checked))
            settings_save(SETTINGS)
            logger.info("[Settings] Otomatik güncelleme denetimi = %s", checked)

        auto_upd_action.triggered.connect(_toggle_auto_update)
        menu.addSeparator()
        low_bandwidth_action = menu.addAction("Düşük internet modu")
        low_bandwidth_action.setCheckable(True)
        low_bandwidth_action.setChecked(self.low_bandwidth_mode)
        low_bandwidth_action.setToolTip(
            "Otomatik ağ yenilemelerini durdurur, AI yanıtlarını kısaltır "
            "ve isteğe bağlı wake word dinlemesini kapatır."
        )
        low_bandwidth_action.triggered.connect(
            lambda enabled: self._save_performance_mode(
                "low_bandwidth_mode", enabled, low_bandwidth_action
            )
        )
        low_resource_action = menu.addAction("Düşük kaynak modu")
        low_resource_action.setCheckable(True)
        low_resource_action.setChecked(self.low_resource_mode)
        low_resource_action.setToolTip(
            "Animasyon ve donanım izleme yükünü azaltır. İlk kullanımda "
            "CPU/RAM bilgisine göre otomatik seçilir."
        )
        low_resource_action.triggered.connect(
            lambda enabled: self._save_performance_mode(
                "low_resource_mode", enabled, low_resource_action
            )
        )
        menu.addSeparator()
        menu.addAction("Görev Merkezi", self._show_task_center)
        menu.addAction("Beceri Kataloğu", self._show_skills_catalog)
        menu.addAction("Bellek ve Profil...", self._show_memory_controls)
        menu.addAction("İzin tercihleri...", self._show_permission_settings)
        menu.addAction("Güncellemeyi denetle...", self._check_for_updates)
        menu.addSeparator()
        menu.addAction("Bu sohbetin geçmişini sil...", self._clear_current_chat_history)
        menu.addAction("Tüm sohbet geçmişini sil...", self._clear_all_chat_history)
        menu.addSeparator()
        menu.addAction("Uygulama tanılaması", self._show_startup_diagnostics)
        menu.addAction("Verileri yedekle...", self._backup_user_data)
        menu.addAction("Yedekten geri yükle...", self._restore_user_data)
        info = menu.addAction(f"Persistence: IP {get_local_ip()} + machine ID")
        info.setEnabled(False)
        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))

    def _save_performance_mode(
        self,
        setting: str,
        enabled: bool,
        action: QAction,
    ) -> None:
        previous = SETTINGS.get(setting)
        SETTINGS[setting] = bool(enabled)
        try:
            settings_save(SETTINGS)
        except Exception as exc:
            if previous is None:
                SETTINGS.pop(setting, None)
            else:
                SETTINGS[setting] = previous
            action.setChecked(bool(
                self.low_bandwidth_mode
                if setting == "low_bandwidth_mode"
                else self.low_resource_mode
            ))
            logger.exception("[Settings] Performans tercihi kaydedilemedi")
            QMessageBox.critical(
                self, "Tercih kaydedilemedi", str(exc)
            )
            return

        if setting == "low_bandwidth_mode":
            self.low_bandwidth_mode = bool(enabled)
            self.engine.low_bandwidth_mode = self.low_bandwidth_mode
            self.left.set_low_bandwidth_mode(self.low_bandwidth_mode)
            if self.low_bandwidth_mode:
                if self._wake is not None and self._wake.isRunning():
                    self._wake.stop()
                    self.wake_lbl.setText(
                        "● Uyandırma kapalı — düşük internet modu"
                    )
            elif SETTINGS.get("wake_word", True):
                if self._wake is None or not self._wake.isRunning():
                    self._start_wake_word()
                else:
                    self.wake_lbl.setText(
                        "● Uyandırma yeniden başlatma sonrası etkinleşecek"
                    )
        else:
            self.low_resource_mode = bool(enabled)
            self.core.set_low_resource_mode(self.low_resource_mode)
            self.left.set_low_resource_mode(self.low_resource_mode)

        logger.info(
            "[Settings] %s = %s", setting, enabled
        )

    def _chat_history_is_busy(self) -> bool:
        if (
            self._active_ai_worker is not None
            or self._active_research_worker is not None
            or self._flow_busy
            or self._awaiting_task_step
        ):
            QMessageBox.information(
                self,
                "Sohbet geçmişi",
                "Geçmişi silmeden önce çalışan AI, araştırma veya görev akışının "
                "tamamlanmasını ya da iptal edilmesini bekleyin.",
            )
            return True
        return False

    def _clear_current_chat_history(self) -> None:
        if self._chat_history_is_busy():
            return
        answer = QMessageBox.question(
            self,
            "Bu sohbetin geçmişini sil",
            "Açık sohbetin kayıtlı mesajları kalıcı olarak silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            deleted_messages = db_clear_session(self.session_id)
        except Exception as exc:
            logger.exception("[ChatHistory] Açık sohbet geçmişi silinemedi")
            QMessageBox.critical(self, "Silme başarısız", str(exc))
            return
        self.history.clear()
        self.chat.clear_chat()
        self.left.refresh_history()
        QMessageBox.information(
            self,
            "Sohbet geçmişi silindi",
            f"{deleted_messages} mesaj kalıcı olarak silindi.",
        )

    def _clear_all_chat_history(self) -> None:
        if self._chat_history_is_busy():
            return
        answer = QMessageBox.question(
            self,
            "Tüm sohbet geçmişini sil",
            "Tüm sohbetlerdeki kayıtlı mesajlar ve diğer sohbet kayıtları "
            "kalıcı olarak silinecek. Bu işlem geri alınamaz. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            deleted_sessions = db_clear_all_history(self.session_id)
        except Exception as exc:
            logger.exception("[ChatHistory] Tüm sohbet geçmişi silinemedi")
            QMessageBox.critical(self, "Silme başarısız", str(exc))
            return
        self.history.clear()
        self.chat.clear_chat()
        self.left.refresh_history()
        QMessageBox.information(
            self,
            "Sohbet geçmişi silindi",
            f"Tüm kayıtlı mesajlar silindi; {deleted_sessions} eski sohbet kaldırıldı.",
        )

    def _show_task_center(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("JARVIS — Görev Merkezi")
        dialog.resize(680, 520)
        layout = QVBoxLayout(dialog)
        task_list = QListWidget(dialog)
        details = QTextEdit(dialog)
        details.setReadOnly(True)
        layout.addWidget(QLabel("Aktif ve son görevler", dialog))
        layout.addWidget(task_list, 2)
        layout.addWidget(details, 3)
        buttons = QHBoxLayout()
        refresh_button = QPushButton("Yenile", dialog)
        cancel_button = QPushButton("Görevi iptal et", dialog)
        close_button = QPushButton("Kapat", dialog)
        buttons.addWidget(refresh_button)
        buttons.addWidget(cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        status_labels = {
            TaskStatus.QUEUED: "Sırada",
            TaskStatus.RUNNING: "Çalışıyor",
            TaskStatus.CANCELLING: "İptal ediliyor",
            TaskStatus.SUCCEEDED: "Tamamlandı",
            TaskStatus.FAILED: "Hata",
            TaskStatus.CANCELLED: "İptal edildi",
        }
        current_task_id = {"value": ""}

        def render_details():
            selected = task_list.currentItem()
            if selected is None:
                details.clear()
                cancel_button.setEnabled(False)
                return
            task_id = selected.data(Qt.ItemDataRole.UserRole)
            record = next(
                (task for task in self.task_center.snapshot()
                 if task.task_id == task_id),
                None,
            )
            if record is None:
                details.setPlainText("Görev kaydı artık bulunmuyor.")
                cancel_button.setEnabled(False)
                return
            step_lines = [
                f"{index}. [{step.status.value}] "
                f"{'(' + step.skill_id + ') ' if step.skill_id else ''}{step.title}"
                + (f" — {step.message}" if step.message else "")
                for index, step in enumerate(record.steps, start=1)
            ]
            details.setPlainText(
                f"{record.title}\nDurum: {status_labels[record.status]}\n"
                f"{record.message}\n\nAdımlar:\n"
                + ("\n".join(step_lines) if step_lines else "Adım detayı yok.")
            )
            cancel_button.setEnabled(
                record.status in {TaskStatus.QUEUED, TaskStatus.RUNNING}
                and (
                    record.cancel_callback is not None
                    or record.status is TaskStatus.QUEUED
                )
            )

        def refresh():
            selected = task_list.currentItem()
            selected_id = (
                selected.data(Qt.ItemDataRole.UserRole) if selected else
                current_task_id["value"]
            )
            records = self.task_center.snapshot()
            task_list.clear()
            selected_row = -1
            for index, record in enumerate(records):
                item = QListWidgetItem(
                    f"{status_labels[record.status]} — {record.title}"
                )
                item.setData(Qt.ItemDataRole.UserRole, record.task_id)
                task_list.addItem(item)
                if record.task_id == selected_id:
                    selected_row = index
            if task_list.count():
                task_list.setCurrentRow(max(0, selected_row))
            else:
                details.setPlainText("Henüz izlenen bir görev yok.")
                cancel_button.setEnabled(False)
            render_details()

        def cancel_selected():
            selected = task_list.currentItem()
            if selected is None:
                return
            task_id = selected.data(Qt.ItemDataRole.UserRole)
            try:
                if not self.task_center.request_cancel(task_id):
                    QMessageBox.information(
                        dialog, "İptal desteklenmiyor",
                        "Bu görev güvenli biçimde iptal edilemiyor.",
                    )
            except Exception as exc:
                logger.exception("[TaskCenter] Görev iptal edilemedi")
                QMessageBox.warning(dialog, "İptal başarısız", str(exc))
            refresh()

        task_list.currentRowChanged.connect(lambda _row: render_details())
        refresh_button.clicked.connect(refresh)
        cancel_button.clicked.connect(cancel_selected)
        close_button.clicked.connect(dialog.accept)
        timer = QTimer(dialog)
        timer.timeout.connect(refresh)
        timer.start(1000)
        refresh()
        dialog.exec()
        timer.stop()

    def _show_skills_catalog(self) -> None:
        lines = ["JARVIS becerileri — mevcut çalışma alanı"]
        for skill in self.skill_registry.all():
            approval = " • işlem öncesi onay" if skill.confirmation_required else ""
            lines.append(f"\n{skill.name}{approval}\n{skill.description}")
        QMessageBox.information(self, "Beceri Kataloğu", "\n".join(lines))

    def _show_memory_controls(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("JARVIS — Yerel Bellek ve Profil")
        dialog.resize(720, 600)
        outer = QVBoxLayout(dialog)
        outer.addWidget(QLabel(
            "Bu veriler bu bilgisayarda kalır. Model bağlamına paylaşım, "
            "JARVIS_SHARE_CONTEXT ayarı kapalıyken yapılmaz.",
            dialog,
        ))
        tabs = QTabWidget(dialog)
        profile_tab = QWidget(tabs)
        profile_layout = QVBoxLayout(profile_tab)
        name_field = QLineEdit(str(PROFILE.get("name", "Efendim")), profile_tab)
        tone_field = QComboBox(profile_tab)
        tone_field.addItem("Samimi", "casual")
        tone_field.addItem("Resmi", "formal")
        tone_field.setCurrentIndex(
            1 if PROFILE.get("preferred_tone", "casual") == "formal" else 0
        )
        depth_field = QComboBox(profile_tab)
        depth_field.addItem("Kısa", "brief")
        depth_field.addItem("Dengeli (önerilen)", "balanced")
        depth_field.addItem("Detaylı", "detailed")
        saved_depth = SETTINGS.get("response_depth", "balanced")
        depth_index = depth_field.findData(saved_depth)
        depth_field.setCurrentIndex(max(0, depth_index))
        profile_layout.addWidget(QLabel("Adınız"))
        profile_layout.addWidget(name_field)
        profile_layout.addWidget(QLabel("Yanıt tonu"))
        profile_layout.addWidget(tone_field)
        profile_layout.addWidget(QLabel("Yanıt derinliği"))
        profile_layout.addWidget(depth_field)
        save_depth_button = QPushButton("Yanıt derinliğini kaydet", profile_tab)
        profile_layout.addWidget(save_depth_button)
        profile_layout.addWidget(QLabel(
            "Sohbet geçmişi yerel kalır; arama sonuçları AI sağlayıcılarına gönderilmez.",
            profile_tab,
        ))
        save_profile_button = QPushButton(
            "Profil değişikliklerini kaydet", profile_tab
        )
        profile_layout.addWidget(save_profile_button)
        profile_layout.addWidget(QLabel("Kayıtlı notlar"))
        notes = QListWidget(profile_tab)
        profile_layout.addWidget(notes, 1)
        note_key = QLineEdit(profile_tab)
        note_key.setPlaceholderText("Not başlığı")
        note_value = QTextEdit(profile_tab)
        note_value.setPlaceholderText("Yalnızca yerel olarak saklanır")
        profile_layout.addWidget(note_key)
        profile_layout.addWidget(note_value)
        note_buttons = QHBoxLayout()
        save_note = QPushButton("Notu ekle / güncelle", profile_tab)
        delete_note = QPushButton("Seçili notu sil", profile_tab)
        note_buttons.addWidget(save_note)
        note_buttons.addWidget(delete_note)
        profile_layout.addLayout(note_buttons)
        tabs.addTab(profile_tab, "Profil ve notlar")

        atlas_tab = QWidget(tabs)
        atlas_layout = QVBoxLayout(atlas_tab)
        atlas_layout.addWidget(QLabel(
            "İndekslenmiş kaynaklar. Kaynağı silmek, yalnızca yerel arama "
            "indeksini kaldırır; özgün dosyayı silmez.",
            atlas_tab,
        ))
        sources = QListWidget(atlas_tab)
        atlas_layout.addWidget(sources, 1)
        source_title = QLineEdit(atlas_tab)
        source_title.setPlaceholderText("Kaynak adı")
        source_content = QTextEdit(atlas_tab)
        source_content.setPlaceholderText("Kaydedilecek bilgi")
        atlas_layout.addWidget(source_title)
        atlas_layout.addWidget(source_content)
        atlas_buttons = QHBoxLayout()
        add_source = QPushButton("Yerel belleğe ekle", atlas_tab)
        delete_source = QPushButton("Seçili kaynağı bellekten sil", atlas_tab)
        atlas_buttons.addWidget(add_source)
        atlas_buttons.addWidget(delete_source)
        atlas_layout.addLayout(atlas_buttons)
        tabs.addTab(atlas_tab, "Atlas yerel hafızası")
        outer.addWidget(tabs)

        def refresh_notes():
            selected = note_key.text().strip()
            notes.clear()
            for key in sorted(PROFILE.list_notes(), key=str.casefold):
                item = QListWidgetItem(key)
                item.setData(Qt.ItemDataRole.UserRole, key)
                notes.addItem(item)
                if key == selected:
                    notes.setCurrentItem(item)

        def refresh_sources():
            previous = (
                sources.currentItem().data(Qt.ItemDataRole.UserRole)
                if sources.currentItem() else ""
            )
            sources.clear()
            try:
                source_records = atlas_memory_list_sources()
            except Exception as exc:
                logger.exception("[Memory] Atlas kaynakları listelenemedi")
                QMessageBox.warning(
                    dialog, "Bellek okunamadı",
                    f"Atlas kaynak listesi alınamadı:\n{exc}",
                )
                return
            for source, chunks, updated_at in source_records:
                item = QListWidgetItem(f"{source} — {chunks} parça, {updated_at}")
                item.setData(Qt.ItemDataRole.UserRole, source)
                sources.addItem(item)
                if source == previous:
                    sources.setCurrentItem(item)

        def save_profile():
            data = PROFILE.snapshot()
            data["name"] = safe_user_text(name_field.text(), 80) or "Efendim"
            data["preferred_tone"] = tone_field.currentData()
            try:
                PROFILE.replace_data(data)
            except Exception as exc:
                logger.exception("[Memory] Profil kaydedilemedi")
                QMessageBox.critical(dialog, "Profil kaydedilemedi", str(exc))
                return
            QMessageBox.information(dialog, "Profil", "Profil yerel olarak kaydedildi.")

        def save_response_depth():
            previous = SETTINGS.get("response_depth")
            SETTINGS["response_depth"] = depth_field.currentData()
            try:
                settings_save(SETTINGS)
            except Exception as exc:
                if previous is None:
                    SETTINGS.pop("response_depth", None)
                else:
                    SETTINGS["response_depth"] = previous
                logger.exception("[Settings] Yanıt derinliği kaydedilemedi")
                QMessageBox.critical(
                    dialog, "Tercih kaydedilemedi", str(exc)
                )
                return
            self.engine.response_depth = SETTINGS["response_depth"]
            QMessageBox.information(
                dialog,
                "Yanıt tercihi",
                "Yanıt derinliği bu bilgisayarda kaydedildi.",
            )

        def save_note_action():
            key = safe_user_text(note_key.text(), 120)
            value = safe_user_text(note_value.toPlainText(), 5000)
            if not key or not value:
                QMessageBox.warning(dialog, "Not", "Başlık ve içerik boş olamaz.")
                return
            try:
                PROFILE.save_note(key, value)
            except Exception as exc:
                logger.exception("[Memory] Not kaydedilemedi")
                QMessageBox.critical(dialog, "Not kaydedilemedi", str(exc))
                return
            refresh_notes()

        def select_note(item):
            key = item.data(Qt.ItemDataRole.UserRole)
            note_key.setText(key)
            note_value.setPlainText(PROFILE.get_note(key) or "")

        def delete_note_action():
            key = note_key.text().strip()
            if not key:
                QMessageBox.information(dialog, "Not", "Silinecek not bulunamadı.")
                return
            try:
                if not PROFILE.delete_note(key):
                    QMessageBox.information(
                        dialog, "Not", "Silinecek not bulunamadı."
                    )
                    return
            except Exception as exc:
                logger.exception("[Memory] Not silinemedi")
                QMessageBox.critical(dialog, "Not silinemedi", str(exc))
                return
            note_key.clear()
            note_value.clear()
            refresh_notes()

        def add_source_action():
            title = safe_user_text(source_title.text(), 250)
            content = safe_user_text(source_content.toPlainText(), 5000)
            if not title or not content:
                QMessageBox.warning(dialog, "Yerel bellek", "Kaynak adı ve içerik gerekli.")
                return
            try:
                atlas_memory_add_fact(content, title)
            except Exception as exc:
                logger.exception("[Memory] Yerel kaynağa ekleme başarısız")
                QMessageBox.critical(dialog, "Kaydetme başarısız", str(exc))
                return
            source_title.clear()
            source_content.clear()
            refresh_sources()

        def delete_source_action():
            item = sources.currentItem()
            if item is None:
                return
            source = item.data(Qt.ItemDataRole.UserRole)
            answer = QMessageBox.question(
                dialog, "Yerel kaynağı sil",
                f"'{source}' kaynağının yerel arama indeksini kaldırayım mı?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            try:
                deleted = atlas_memory_delete_source(source)
            except Exception as exc:
                logger.exception("[Memory] Kaynak silinemedi")
                QMessageBox.critical(dialog, "Silme başarısız", str(exc))
                return
            if not deleted:
                QMessageBox.information(
                    dialog, "Yerel bellek", "Kaynak zaten mevcut değil."
                )
            refresh_sources()

        save_profile_button.clicked.connect(save_profile)
        save_depth_button.clicked.connect(save_response_depth)
        save_note.clicked.connect(save_note_action)
        delete_note.clicked.connect(delete_note_action)
        notes.currentItemChanged.connect(
            lambda current, _previous: select_note(current) if current else None
        )
        add_source.clicked.connect(add_source_action)
        delete_source.clicked.connect(delete_source_action)
        refresh_notes()
        refresh_sources()
        close_buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
        close_buttons.rejected.connect(dialog.reject)
        close_buttons.accepted.connect(dialog.accept)
        outer.addWidget(close_buttons)
        dialog.exec()

    def _show_permission_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("JARVIS — İzin tercihleri")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            "Tercihler cihazda saklanır. 'Bu oturumda' bir eylem türünü "
            "ilk kez yine de onaylatır; 'Asla yapma' ilgili işlemi engeller.",
            dialog,
        ))
        choices = {
            "Her seferinde sor": "always_ask",
            "Bu oturumda bir kez": "session",
            "Asla yapma": "never",
        }
        controls = {}
        for category in ActionCategory:
            row = QHBoxLayout()
            row.addWidget(QLabel(CATEGORY_LABELS[category], dialog), 1)
            choice = QComboBox(dialog)
            for label, value in choices.items():
                choice.addItem(label, value)
            current = self.permission_manager.get_preference(category)
            choice.setCurrentIndex(max(0, choice.findData(current)))
            controls[category] = choice
            row.addWidget(choice)
            layout.addLayout(row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        previous_settings = dict(SETTINGS)
        try:
            for category, choice in controls.items():
                self.permission_manager.set_preference(
                    category, choice.currentData()
                )
            settings_save(SETTINGS)
        except Exception as exc:
            SETTINGS.clear()
            SETTINGS.update(previous_settings)
            logger.exception("[Permissions] İzin tercihleri kaydedilemedi")
            QMessageBox.critical(
                self, "Tercihler kaydedilemedi", str(exc)
            )

    def _start_update_check(self, manual: bool) -> None:
        """Güncelleme denetimini arka plan iş parçacığında başlatır."""
        current = getattr(self, "_update_worker", None)
        if current is not None and current.isRunning():
            logger.info("[Update] Denetim zaten çalışıyor; yeni istek yoksayıldı")
            if manual:
                QMessageBox.information(
                    self, "Güncelleme denetimi",
                    "Denetim hâlâ çalışıyor; lütfen birkaç saniye sonra "
                    "tekrar deneyin.",
                )
            return
        worker = UpdateCheckWorker()
        worker.result.connect(lambda info: self._on_update_result(info, manual))
        worker.error.connect(
            lambda message: self._on_update_failure(message, manual)
        )

        def _release(w=worker) -> None:
            self._threads.discard(w)
            if getattr(self, "_update_worker", None) is w:
                self._update_worker = None

        worker.finished.connect(_release)
        worker.finished.connect(worker.deleteLater)
        self._threads.add(worker)
        self._update_worker = worker
        worker.start()

    def _check_for_updates(self) -> None:
        """⚙ → 'Güncellemeyi denetle...': kullanıcı tarafından tetiklenen denetim."""
        self._start_update_check(manual=True)

    def _maybe_auto_check_updates(self) -> None:
        """Açılıştan ~6 sn sonra sessiz denetim; tercih/kaynak/kip korumalı."""
        if self._shutdown_complete or self._closing:
            return
        if not bool(load_device_pref(SETTINGS, "auto_update_check", True)):
            logger.debug("[Update] Otomatik denetim kapalı (cihaz tercihi)")
            return
        if self.low_bandwidth_mode:
            logger.debug("[Update] Düşük internet modu; otomatik denetim atlandı")
            return
        if not is_update_check_configured():
            logger.debug(
                "[Update] JARVIS_UPDATE_URL ayarlı değil; otomatik denetim atlandı"
            )
            return
        logger.info("[Update] Otomatik güncelleme denetimi başlıyor")
        self._start_update_check(manual=False)

    def _on_update_result(self, update, manual: bool) -> None:
        if update.update_available is True:
            prompt = (
                f"Yeni sürüm bulundu: {update.latest_version}\n\n"
                "JARVIS kendini otomatik güncellemez. Yayın sayfasını açıp "
                "kurulum dosyasını elle inceleyebilirsiniz."
            )
            answer = QMessageBox.question(
                self, "Güncelleme bulundu", prompt,
                QMessageBox.Open | QMessageBox.Cancel, QMessageBox.Open,
            )
            if answer == QMessageBox.Open:
                if not QDesktopServices.openUrl(QUrl(update.release_url)):
                    QMessageBox.warning(
                        self,
                        "Yayın açılamadı",
                        f"Tarayıcı açılamadı. Yayın bağlantısı:\n{update.release_url}",
                    )
            return
        if not manual:
            # Otomatik denetimde 'güncel' sonucu sessizdir; yalnızca loglanır.
            logger.info(
                "[Update] Otomatik denetim tamamlandı: sürüm güncel (%s)",
                update.latest_version,
            )
            return
        message = (
            f"Yayınlanan son sürüm: {update.latest_version}\n"
            "Mevcut sürümü otomatik karşılaştırmak için JARVIS_VERSION ayarlayın."
            if update.update_available is None
            else f"JARVIS güncel ({update.latest_version})."
        )
        if update.release_notes:
            message += f"\n\nYayın notları:\n{update.release_notes[:2000]}"
        QMessageBox.information(self, "Güncelleme denetimi", message)

    def _on_update_failure(self, message: str, manual: bool) -> None:
        logger.warning("[Update] Güncelleme denetimi yapılamadı: %s", message)
        if manual:
            QMessageBox.information(self, "Güncelleme denetimi", message)

    def _show_missing_provider_warning(self) -> None:
        QMessageBox.warning(
            self,
            "JARVIS yapılandırması",
            "Groq ve Gemini API anahtarı bulunamadı. Sohbet yanıtları "
            "çalışmayacak. ⚙ → Uygulama tanılaması bölümünden diğer "
            "özelliklerin durumunu görebilirsiniz.",
        )

    def _show_startup_diagnostics(self) -> None:
        QMessageBox.information(
            self,
            "JARVIS uygulama tanılaması",
            format_startup_diagnostics(),
        )

    def _backup_user_data(self) -> None:
        suggested = str(
            Path.home() / f"JARVIS-yedek-{datetime.datetime.now():%Y%m%d-%H%M%S}.zip"
        )
        destination, _ = QFileDialog.getSaveFileName(
            self, "JARVIS verilerini yedekle", suggested, "JARVIS yedeği (*.zip)"
        )
        if not destination:
            return
        if not destination.lower().endswith(".zip"):
            destination += ".zip"
        try:
            archive = create_backup(destination)
        except Exception as exc:
            logger.exception("[Backup] Veriler yedeklenemedi")
            QMessageBox.critical(self, "Yedekleme başarısız", str(exc))
            return
        QMessageBox.information(
            self,
            "Yedek hazır",
            f"Yerel veriler yedeklendi:\n{archive}\n\nAPI anahtarları ve loglar yedeğe eklenmedi.",
        )

    def _restore_user_data(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "JARVIS yedeğini seç", str(Path.home()), "JARVIS yedeği (*.zip)"
        )
        if not source:
            return
        answer = QMessageBox.question(
            self,
            "Verileri geri yükle",
            "Yedek içindeki oturumlar, ayarlar ve kullanıcı profili mevcut "
            "verilerin üzerine yazılacak. İşlem öncesi mevcut veriler için "
            "otomatik yedek alınacak. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            safety_backup = restore_backup(source)
            SETTINGS.clear()
            SETTINGS.update(settings_load())
            PROFILE.replace_data(safe_read_json(PROFILE_FILE, {}))
        except Exception as exc:
            logger.exception("[Backup] Yedekten geri yükleme başarısız")
            QMessageBox.critical(
                self,
                "Geri yükleme başarısız",
                f"Yedek doğrulanamadı veya uygulanamadı:\n{exc}",
            )
            return
        QMessageBox.information(
            self,
            "Geri yükleme tamamlandı",
            "Yedek geri yüklendi. Oturum geçmişi ve tüm ayarların tutarlı "
            "şekilde uygulanması için JARVIS'i yeniden başlatın.\n\n"
            f"İşlem öncesi güvenlik yedeği:\n{safety_backup}",
        )

    def _fetch_briefing(self):
        self.core.set_state("briefing")
        self.status_lbl.setText("● BRİFİNG HAZIRLANIYOR...")
        self._add_response("Günlük brifing hazırlanıyor...")
        w = BriefingWorker()
        w.finished.connect(lambda t: (self._add_response(t), self.core.set_state("idle")))
        self._start_worker(w)

    def _auto_briefing(self):
        self.chat.add_bubble("assistant",
            "Sabah brifingini hazırlıyorum, Efendim...")
        self._fetch_briefing()

    def _fetch_fx_board(self):
        self.core.set_state("finance")
        self._add_response("Döviz kurları alınıyor...")
        w = FxBoardWorker()
        w.finished.connect(lambda t: (self._add_response(t), self.core.set_state("idle")))
        self._start_worker(w)

    def _fetch_watchlist(self):
        stocks = PROFILE.get("favorite_stocks", [])
        if not stocks:
            self._add_response(
                "Takip listesi boş, Efendim.\n"
                "'takip ekle THYAO.IS' ile hisse ekleyin.")
            return
        self.core.set_state("finance")
        self._add_response("Takip listesi güncelleniyor...")
        w = WatchlistWorker()
        w.finished.connect(lambda t: (self._add_response(t), self.core.set_state("idle")))
        self._start_worker(w)

    def _fetch_news(self, detailed: bool):
        self._add_response("Haberler yükleniyor...")
        w = NewsWorker(detailed)
        w.finished.connect(self._add_response)
        self._start_worker(w)

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Dosya Seç", "",
            "Tüm Dosyalar (*);;PDF (*.pdf);;Görsel (*.jpg *.png);;Word (*.docx)")
        if path:
            self.attached = path
            self.file_lbl.setText(f"📎 {Path(path).name}")
            if path.lower().endswith(".pdf"):
                self._add_response(f"'{Path(path).name}' okunuyor ve yerel hafızaya ekleniyor...")
                worker = PdfLoadWorker(path)
                worker.result.connect(self._on_pdf_loaded)
                self._start_worker(worker)

    def _on_pdf_loaded(self, result: str):
        if not self._closing:
            self._add_response(result)

    def _run_speedtest(self):
        self._add_response("Speedtest başlatılıyor, lütfen bekleyin...")
        w = SpeedtestWorker(self)
        w.finished.connect(self._add_response)
        self._start_worker(w)

    def _voice_input(self):
        self._start_voice_listen()

    def _start_voice_listen(self):
        self.core.set_state("listening")
        self.status_lbl.setText("● DİNLİYOR — Konuşun...")
        self.mic_btn.setStyleSheet(
            f"QPushButton{{background:{C['blue']}40;color:{C['blue']};border:2px solid {C['blue']};"
            f"border-radius:19px;font:16px;}}")
        self.chat.add_bubble("assistant", "Dinliyorum, Efendim. Konuşun...")
        speak_async("Dinliyorum Efendim")
        vw = VoiceWorker(self)
        vw.result.connect(self._on_voice_result)
        vw.partial.connect(lambda t: self.status_lbl.setText(f"● {t}"))
        vw.error.connect(self._on_voice_error)
        self._start_worker(vw)

    def _on_voice_result(self, text: str):
        self.mic_btn.setStyleSheet(
            f"QPushButton{{background:{C['border']};color:{C['text']};border:1px solid {C['border']};"
            f"border-radius:19px;font:16px;}}"
            f"QPushButton:hover{{background:{C['blue']}30;}}")
        self.status_lbl.setText("● SİSTEM AKTİF")
        self.core.set_state("idle")
        self.chat.add_bubble("assistant", f"Algılandı: \"{text}\"")
        self.input_box.setText(text)
        self._send()

    def _on_voice_error(self, err: str):
        self.mic_btn.setStyleSheet(
            f"QPushButton{{background:{C['border']};color:{C['text']};border:1px solid {C['border']};"
            f"border-radius:19px;font:16px;}}"
            f"QPushButton:hover{{background:{C['blue']}30;}}")
        self.status_lbl.setText("● SİSTEM AKTİF")
        self.core.set_state("idle")
        self.chat.add_bubble("assistant", f"Ses algılanamadı: {err}")

    def _show_profile(self):
        profile_text = (
            f"KULLANICI PROFİLİ (v9 LongMemory)\n"
            f"{'='*36}\n"
            f"İsim:              {PROFILE.get('name', 'Efendim')}\n"
            f"Toplam oturum:     {PROFILE.get('total_sessions', 1)}\n"
            f"İlk görülme:       {PROFILE.get('first_seen', '?')[:10]}\n"
            f"Favori hisseler:   {', '.join(PROFILE.get('favorite_stocks', [])) or 'Yok'}\n"
            f"Favori kurlar:     {', '.join(PROFILE.get('favorite_currencies', []))}\n"
            f"Konuşma tarzı:     {PROFILE.get('preferred_tone', 'casual')}\n"
        )
        notes = PROFILE.list_notes()
        if notes:
            profile_text += f"\nNotlar:\n"
            for k, v in notes.items():
                profile_text += f"  {k}: {v}\n"
        self._add_response(profile_text)

    def _authorize_local_context(
        self,
        text: str,
        *,
        exclude_current_message: bool = False,
    ) -> tuple[str, str, bool]:
        """Require visible, per-request consent before sharing local excerpts."""
        query = extract_context_query(text)
        if query is None:
            return text, "", True
        if not query:
            QMessageBox.information(
                self,
                "Yerel sohbet bağlamı",
                "İki nokta üst üste işaretinden sonra isteğinizi yazın. "
                "Örnek: geçmiş bağlamıyla: önceki bilgisayar önerilerini özetle",
            )
            return text, "", False
        if self.mode_box.currentData() != "normal":
            QMessageBox.information(
                self,
                "Yerel sohbet bağlamı",
                "Bu açık paylaşım yalnızca Normal sohbet modunda kullanılabilir. "
                "Araştırma moduna geçiş yapılmadı.",
            )
            return text, "", False
        try:
            matches = db_search_messages(
                query,
                limit=3,
                exclude_content=query if exclude_current_message else None,
            )
        except Exception as exc:
            logger.exception("[ChatHistory] Yerel bağlam aranamadı")
            QMessageBox.critical(self, "Yerel geçmiş okunamadı", str(exc))
            return text, "", False
        local_context = format_local_context(matches)
        if not local_context:
            QMessageBox.information(
                self,
                "Yerel sohbet bağlamı",
                "İstediğiniz konuya uyan eski mesaj bulunamadı. "
                "Mesaj AI sağlayıcısına gönderilmedi.",
            )
            return text, "", False
        answer = QMessageBox.question(
            self,
            "Eski mesajları bu istek için paylaş",
            "Aşağıdaki yerel sohbet alıntıları yalnızca bu yanıtı üretmek "
            "için seçili AI sağlayıcısına gönderilecek. Bu paylaşım kalıcı "
            "bir ayarı değiştirmez. Profil/belge paylaşımı gibi diğer açık "
            "paylaşım ayarlarınız değişmeden kalır.\n\n"
            f"{local_context}\n\n"
            "Bu alıntıları bu istek için gönderelim mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return text, "", False
        return query, local_context, True

    # ── MESAJ GÖNDER ──────────────────────────────────────────────────────
    def _send(self):
        if (
            self._active_ai_worker is not None
            or self._active_research_worker is not None
        ):
            return
        text = self.input_box.text().strip()
        if not text: return
        context_directive = text
        context_query = extract_context_query(text)
        if context_query is not None and not context_query:
            QMessageBox.information(
                self,
                "Yerel sohbet bağlamı",
                "İki nokta üst üste işaretinden sonra isteğinizi yazın. "
                "Örnek: geçmiş bağlamıyla: önceki bilgisayar önerilerini özetle",
            )
            return
        if context_query is not None:
            if self.mode_box.currentData() != "normal":
                QMessageBox.information(
                    self,
                    "Yerel sohbet bağlamı",
                    "Bu açık paylaşım yalnızca Normal sohbet modunda kullanılabilir. "
                    "Araştırma moduna geçiş yapılmadı.",
                )
                return
            text = context_query
        local_context = ""
        # Yeni mesaj: 12 sn'lik yeşil (success) bekleme anında iptal → mavi.
        self._state_controller.set_state(AppState.BUSY)
        self.input_box.clear()
        normalized_text = " ".join(text.lower().split())
        confirmation_words = {"onayla", "evet", "devam", "confirm", "yes"}
        cancellation_words = {"iptal", "hayır", "vazgeç", "cancel", "no"}
        if normalized_text in {"durdur plan", "planı durdur", "plani durdur"}:
            if self._active_task_id is not None:
                try:
                    self.task_center.request_cancel(self._active_task_id)
                except Exception as exc:
                    logger.exception("[TaskCenter] Aktif plan iptal edilemedi")
                    self._add_response(f"Plan iptali başlatılamadı: {exc}")
                    return
            self._pending_task_plan = None
            self._authorized_task_plan = None
            self._active_task_steps = None
            self._awaiting_task_step = False
            self.verifier.cancel_pending()
            self._pending_ui_action = None
            self._pending_action_preview = None
            self._add_response(
                "Görev planı durduruldu; devam eden iptal edilebilir işlem durduruluyor."
            )
            return
        if self._pending_task_plan is not None:
            plan_request, created_at, task_id = self._pending_task_plan
            if time.monotonic() - created_at > 120:
                self._pending_task_plan = None
                self.task_center.finish(
                    task_id, TaskStatus.CANCELLED, "Onay süresi doldu."
                )
                self._active_task_id = None
                self._add_response("İşlem planı onay süresi doldu; hiçbir adım çalıştırılmadı.")
                return
            elif normalized_text in cancellation_words:
                self._pending_task_plan = None
                self.task_center.request_cancel(task_id)
                self._active_task_id = None
                self._add_response("İşlem planı iptal edildi; hiçbir adım çalıştırılmadı.")
                return
            elif normalized_text in confirmation_words:
                self._pending_task_plan = None
                confirmed_plan = build_task_plan(f"Planla: {plan_request}")
                if confirmed_plan is None:
                    self._finish_task_record(
                        task_id, TaskStatus.FAILED, "Onaylı plan artık geçerli değil."
                    )
                    self._active_task_id = None
                    self._add_response("Plan artık geçerli değil; tekrar oluşturun.")
                    return
                self._active_task_id = task_id
                self.task_center.start(task_id, "Kullanıcı planı onayladı.")
                self._active_task_steps = [
                    step.request for step in confirmed_plan.steps
                ]
                self._active_task_index = 0
                self._run_next_task_step()
                return
            else:
                self._pending_task_plan = None
                self.task_center.request_cancel(task_id)
                self._active_task_id = None

        authorized_plan = self._authorized_task_plan == text
        if authorized_plan:
            self._authorized_task_plan = None
        if not authorized_plan:
            plan = build_task_plan(text)
            if plan is not None:
                task_steps = []
                for step in plan.steps:
                    matched = self.skill_registry.match(step.request)
                    skill_id = matched[0].skill_id if matched else "conversation"
                    task_steps.append((step.request, skill_id))
                task_id_holder = {}
                task_id = self.task_center.create(
                    f"İş akışı: {plan.request}",
                    task_steps,
                    cancel_callback=lambda: self._cancel_task_from_center(
                        task_id_holder["task_id"]
                    ),
                )
                task_id_holder["task_id"] = task_id
                self._active_task_id = task_id
                self._pending_task_plan = (
                    plan.request, time.monotonic(), task_id
                )
                self._mirror_to_overlay("user", text)
                self.chat.add_bubble("user", text)
                self._add_response(format_task_plan(plan))
                return

        # Sohbet eylemleri (ör. "espri yap") Atlas'ı açmaz; yalnızca açıkça
        # bilgisayar/tarayıcı işlemi isteyen komutlar Atlas moduna geçirir.
        if (requires_atlas(text)
                and not self.atlas_enabled
                and load_device_pref(SETTINGS, "atlas_auto_open", True)):
            self._toggle_atlas(True)
            logger.info("[Intent] Bilgisayar işlemi → ATLAS otomatik açıldı.")
        self._mirror_to_overlay("user", text)
        if requires_atlas(text) and not self.atlas_enabled:
            self._add_response("Bu bilgisayar işlemi için önce ATLAS düğmesini açın.")
            return
        if normalized_text in cancellation_words and self.verifier.has_pending:
            self.verifier.cancel_pending()
            self._pending_ui_action = None
            self._pending_action_preview = None
            self._pending_permission_category = None
            self._pending_risk_request = None
            if self._awaiting_task_step:
                if self._active_task_id is not None:
                    self.task_center.request_cancel(self._active_task_id)
                self._add_response(
                    "Görev planı iptal edildi; kalan adımlar çalıştırılmadı."
                )
                return
            self._add_response("İşlem iptal edildi.")
            return
        if normalized_text in confirmation_words and self.verifier.has_pending:
            verification = self.verifier.inspect(normalized_text)
            action = self._pending_ui_action
            self._pending_ui_action = None
            self._pending_action_preview = None
            if verification.allowed:
                if (
                    self._pending_permission_category is not None
                    and self.permission_manager.get_preference(
                        self._pending_permission_category
                    ) == "session"
                ):
                    self.permission_manager.mark_session_approved(
                        self._pending_permission_category
                    )
                self._pending_permission_category = None
                if action is not None:
                    self._pending_risk_request = None
                    self._add_response(action())
                elif self._pending_risk_request:
                    authorized_request = self._pending_risk_request
                    self._pending_risk_request = None
                    self._authorized_risk_request = authorized_request
                    self.input_box.setText(authorized_request)
                    self._send()
                else:
                    self._add_response(
                        self.verifier.confirmation_failed().message
                    )
            else:
                self._pending_permission_category = None
                self._pending_risk_request = None
                self._add_response(self.verifier.confirmation_failed().message)
            return
        if self.verifier.has_pending:
            self.verifier.cancel_pending()
            self._pending_ui_action = None
            self._pending_action_preview = None
            self._pending_permission_category = None
            self._pending_risk_request = None
            if self._awaiting_task_step:
                if self._active_task_id is not None:
                    self.task_center.request_cancel(self._active_task_id)
                self._add_response(
                    "Görev planı durduruldu; bekleyen adım onaylanmadı."
                )
                return
        click_request = re.search(r"(?:tıkla|tikla)\s+(\d+)\s*[, ]\s*(\d+)", normalized_text)
        type_request = re.search(r"(?:aktif pencereye|klavyeye)\s+yaz\s+(.+)$", text, re.IGNORECASE)
        edit_request = re.search(r"dosya düzenle\s+(.+?)\s+\|\s*(.+?)\s*->\s*(.*)$", text, re.IGNORECASE)
        undo_request = re.fullmatch(r"geri al dosya\s+(.+)", text, re.IGNORECASE)
        routine_delete = re.fullmatch(
            r"(?:rutini sil|rutin sil)\s+(\d+)", text, re.IGNORECASE
        )
        web_click_request = re.search(
            r"(https://\S+)\s+(?:sayfasında|sayfasinda|adresinde)\s+['\"]?(.+?)['\"]?\s+tıkla$",
            text, re.IGNORECASE)
        web_fill_request = re.search(
            r"(https://\S+)\s+(?:sayfasında|sayfasinda)\s+['\"]?(.+?)['\"]?\s+alanına\s+['\"]?(.+?)['\"]?\s+yaz$",
            text, re.IGNORECASE)
        if click_request:
            x, y = int(click_request.group(1)), int(click_request.group(2))
            self._pending_ui_action = lambda: click_screen(x, y)
        elif type_request:
            typed_text = type_request.group(1)
            self._pending_ui_action = lambda: type_text(typed_text)
        elif edit_request:
            path, find_text, replacement = edit_request.groups()
            self._pending_action_preview = preview_text_edit(
                path.strip(), find_text, replacement
            )
            self._pending_ui_action = lambda: edit_text_file(path.strip(), find_text, replacement)
        elif undo_request:
            undo_path = undo_request.group(1).strip()
            self._pending_action_preview = (
                f"Dosya: {undo_path}\n"
                "Jarvis'in oluşturduğu en yeni .jarvis-*.bak yedeği geri yüklenecek. "
                "Mevcut sürüm ayrıca yedeklenecek."
            )
            self._pending_ui_action = lambda: undo_last_text_edit(undo_path)
        elif routine_delete:
            routine_id = int(routine_delete.group(1))
            self._pending_action_preview = (
                f"Zamanlanmış rutin #{routine_id} devre dışı bırakılacak."
            )
            self._pending_ui_action = lambda: self._delete_routine(routine_id)
        elif web_click_request:
            url, target = web_click_request.groups()
            self._pending_ui_action = lambda: web_interact(url, "click", target.strip())
        elif web_fill_request:
            url, target, value = web_fill_request.groups()
            self._pending_ui_action = lambda: web_interact(url, "fill", target.strip(), value.strip())
        authorized_risk_request = self._authorized_risk_request == text
        if authorized_risk_request:
            self._authorized_risk_request = None
        permission_category = category_for_request(text)
        self._pending_permission_category = permission_category
        if authorized_risk_request:
            verification = VerificationResult(True, False)
        elif permission_category is not None:
            preference = self.permission_manager.get_preference(permission_category)
            if preference == "never":
                verification = VerificationResult(
                    False,
                    False,
                    f"{CATEGORY_LABELS[permission_category]} tercihiniz "
                    "'Asla yapma'; bu eylem çalıştırılmadı.",
                )
                self._pending_permission_category = None
            elif (
                preference == "session"
                and self.permission_manager.is_session_approved(permission_category)
            ):
                self.verifier.cancel_pending()
                verification = VerificationResult(True, False)
            else:
                verification = self.verifier.inspect(text)
        else:
            verification = self.verifier.inspect(text)
        if not verification.allowed:
            message = verification.message
            if self._pending_action_preview:
                message += f"\n\nÖnizleme:\n{self._pending_action_preview}"
            self._pending_action_preview = None
            if verification.requires_confirmation:
                self._pending_risk_request = text
            self.chat.add_bubble("assistant", message)
            self.status_lbl.setText("● GÜVENLİ MOD / ONAY BEKLENİYOR")
            self.core.set_state("error" if not verification.requires_confirmation else "thinking")
            return
        self._pending_ui_action = None
        self._pending_action_preview = None
        self._pending_permission_category = None
        self._pending_risk_request = None
        style_update(text)

        self.chat.add_bubble("user", text)
        self.history.append({"role": "user", "content": text})
        if len(self.history) > 40:
            self.history = self.history[-40:]
        db_save_msg(self.session_id, "user", text)
        self.core.set_state("thinking")
        self.status_lbl.setText("● İŞLENİYOR...")

        if len([m for m in self.history if m["role"] == "user"]) == 1:
            con = sqlite3.connect(DB_PATH)
            con.execute("UPDATE sessions SET title=? WHERE id=?", (text[:40], self.session_id))
            con.commit(); con.close()
            self.left.refresh_history()

        # Özellik 10: araştırma modu seçiliyse normal sohbet yerine araştırma akışı.
        research_mode = self.mode_box.currentData()
        if research_mode and research_mode != "normal":
            self._start_research(research_mode, text)
            return

        # Özellik 8: eğitim sorusu → seviye uygun dil + 3 sn doğrulama akışı.
        if is_education_query(text):
            if context_query is not None:
                _, local_context, authorized = self._authorize_local_context(
                    context_directive,
                    exclude_current_message=True,
                )
                if not authorized:
                    self._add_response(
                        "İstek iptal edildi; yerel sohbet alıntıları paylaşılmadı."
                    )
                    return
            self._start_education(text, local_context)
            return

        try:
            result = self._handle_special(text)
        except Exception as exc:
            logger.exception("[Command] Özel komut başarısız: %s", text)
            self._add_response(f"İşlem tamamlanamadı: {exc}")
            return
        if result is not None:
            if result != "__async__":
                self._add_response(result)
            return

        if context_query is not None:
            _, local_context, authorized = self._authorize_local_context(
                context_directive,
                exclude_current_message=True,
            )
            if not authorized:
                self._add_response(
                    "İstek iptal edildi; yerel sohbet alıntıları paylaşılmadı."
                )
                return

        extra = get_pdf_context() if REMOTE_CONTEXT_ENABLED else ""
        if REMOTE_CONTEXT_ENABLED:
            memory_context = atlas_memory_build_context(text)
            if memory_context:
                extra = f"{extra}\n\n{memory_context}".strip()
        if local_context:
            extra = f"{extra}\n\n{local_context}".strip()
        if self.attached and REMOTE_CONTEXT_ENABLED:
            extra += f"\nEklenen dosya: {self.attached}"
        if self.attached:
            self.attached = None; self.file_lbl.setText("")

        feedback_text = (
            ""
            if classify_ai_request(text) is AIRequestType.WEB_SEARCH
            else format_answer_feedback(
                text, local_sources_shared=REMOTE_CONTEXT_ENABLED
            )
        )
        self._worker = AIWorker(
            self.engine, self.history.copy(), text, extra, feedback_text
        )
        self._prepare_ai_worker(self._worker)
        self._stream_bubble = self.chat.add_bubble("assistant", "")
        self._worker.token.connect(self._on_stream_token)
        self._worker.finished.connect(self._add_response)
        self._worker.tool_call.connect(self._on_tool_call)
        self._start_worker(self._worker)

    def _on_tool_call(self, tool_call_str: str):
        try:
            tool_call = json.loads(tool_call_str)
            name = tool_call.get("name")
            args = tool_call.get("arguments", {})

            latest_user_message = next(
                (
                    message.get("content", "")
                    for message in reversed(self.history)
                    if message.get("role") == "user"
                ),
                "",
            )
            if not requires_atlas(latest_user_message):
                logger.warning(
                    "[Atlas] Araç çağrısı reddedildi; kullanıcı isteği bilgisayar "
                    "işlemi değil: %s",
                    latest_user_message[:120],
                )
                self._add_response(
                    "Bu istek bilgisayar kontrolü gerektirmediği için Atlas "
                    "otomasyonu başlatılmadı."
                )
                return
            if not self.atlas_enabled:
                self._add_response(
                    "Bu işlem için önce ATLAS modunu açın; otomasyon başlatılmadı."
                )
                return

            if name == "search_on_site":
                site  = args.get("site", "youtube.com")
                query = args.get("query", "")
                msg   = f"'{query}' — {site} üzerinde aranıyor, Efendim."
                self._add_response(msg)
                if self._atlas_overlay:
                    self._atlas_overlay.add_log(f"🔍 {site}: {query}")
                self._automation.search_on_site(site, query)

            elif name == "open_youtube_and_search":
                # Geriye dönük uyumluluk — search_on_site'a yönlendir
                query = args.get("query", "")
                self._add_response(f"YouTube açılıyor: '{query}', Efendim.")
                if self._atlas_overlay:
                    self._atlas_overlay.add_log(f"▶ YouTube: {query}")
                self._automation.open_youtube_and_search(query)

            elif name == "open_url":
                url = args.get("url", "")
                self._add_response(f"{url} tarayıcıda açılıyor, Efendim.")
                if self._atlas_overlay:
                    self._atlas_overlay.add_log(f"🌐 URL: {url}")
                self._automation.open_url(url)

            else:
                self._add_response(f"Bilinmeyen fonksiyon: {name}")

        except Exception as e:
            self._add_response(f"Fonksiyon çağırma hatası: {e}")

    def _on_stream_token(self, token: str):
        if self._stream_bubble is not None:
            self._stream_bubble.append_text(token)
            self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        self.status_lbl.setText("● YANIT AKIYOR...")
        self.core.set_state("done")

    def _run_next_task_step(self):
        steps = self._active_task_steps
        if not steps:
            return
        if self._active_task_index >= len(steps):
            self._active_task_steps = None
            self._awaiting_task_step = False
            self._add_response("Görev planındaki tüm adımlar tamamlandı.")
            return

        step_index = self._active_task_index
        step_request = steps[step_index]
        try:
            self.task_center.update_step(
                self._active_task_id, step_index, StepStatus.RUNNING,
                "Onaylı istek yürütülüyor.",
            )
        except (KeyError, IndexError):
            logger.exception("[TaskCenter] İş akışı adımı başlatılamadı.")
        progress = (
            f"Plan adımı {step_index + 1}/{len(steps)} başlatılıyor: "
            f"{step_request}"
        )
        self.chat.add_bubble("assistant", progress)
        self._mirror_to_overlay("jarvis", progress)
        self._authorized_task_plan = step_request
        self._awaiting_task_step = True
        self.input_box.setText(step_request)
        try:
            self._send()
        except Exception as exc:
            logger.exception("[Planner] Adım çalıştırılamadı: %s", step_request)
            self._active_task_steps = None
            self._awaiting_task_step = False
            self._add_response(f"Plan durduruldu; adım çalıştırılamadı: {exc}")

    def _advance_task_plan(self):
        if self._active_task_steps is None or self._awaiting_task_step:
            return
        completed_index = self._active_task_index + 1
        self.chat.add_bubble(
            "assistant", f"Plan adımı {completed_index} tamamlandı."
        )
        self._mirror_to_overlay(
            "jarvis", f"Plan adımı {completed_index} tamamlandı."
        )
        self._active_task_index += 1
        if self._active_task_index >= len(self._active_task_steps):
            task_id = self._active_task_id
            self._active_task_steps = None
            self._active_task_id = None
            self._finish_task_record(
                task_id, TaskStatus.SUCCEEDED, "Tüm iş akışı adımları tamamlandı."
            )
            self._add_response("Görev planındaki tüm adımlar tamamlandı.")
            return
        QTimer.singleShot(0, self._run_next_task_step)

    def _add_response(self, text: str):
        self._mirror_to_overlay("jarvis", text)  # ATLAS açıkken yanıt da yansınsın
        if not text:
            if self._stream_bubble is not None and not self._stream_bubble.message_label.text():
                self._stream_bubble.setParent(None)
                self._stream_bubble.deleteLater()
            self._stream_bubble = None
            if self._awaiting_task_step:
                try:
                    self.task_center.update_step(
                        self._active_task_id,
                        self._active_task_index,
                        StepStatus.FAILED,
                        "Adım boş yanıt verdi.",
                    )
                except (KeyError, IndexError):
                    logger.exception("[TaskCenter] Boş yanıt durumu kaydedilemedi.")
                self._finish_task_record(
                    self._active_task_id, TaskStatus.FAILED, "İş akışı adımı boş yanıt verdi."
                )
                self._active_task_id = None
                self._awaiting_task_step = False
                self._active_task_steps = None
                self._add_response(
                    "Görev planı boş yanıt nedeniyle durduruldu; kalan adımlar çalıştırılmadı."
                )
            return

        if self._stream_bubble is not None:
            self._stream_bubble.message_label.setText(text)
            self._stream_bubble = None
        else:
            self.chat.add_bubble("assistant", text)
        self.history.append({"role": "assistant", "content": text})
        if len(self.history) > 40:
            self.history = self.history[-40:]
        db_save_msg(self.session_id, "assistant", text)
        if self._awaiting_task_step:
            self._awaiting_task_step = False
            if self._task_step_failed(text):
                failed_index = self._active_task_index + 1
                try:
                    self.task_center.update_step(
                        self._active_task_id,
                        self._active_task_index,
                        StepStatus.FAILED,
                        text[:300],
                    )
                except (KeyError, IndexError):
                    logger.exception("[TaskCenter] Başarısız adım durumu kaydedilemedi.")
                self._finish_task_record(
                    self._active_task_id,
                    TaskStatus.FAILED,
                    f"{failed_index}. adım başarısız.",
                )
                self._active_task_id = None
                self._active_task_steps = None
                self._add_response(
                    f"Plan, {failed_index}. adımda hata nedeniyle durduruldu; "
                    "sonraki adımlar çalıştırılmadı."
                )
                return
            try:
                self.task_center.update_step(
                    self._active_task_id,
                    self._active_task_index,
                    StepStatus.SUCCEEDED,
                    text[:300],
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] Tamamlanan adım durumu kaydedilemedi.")
            self._advance_task_plan()
        self.core.set_state("done")
        # Özellik 7: yanıt sunuldu → yeşil çerçeve12 sn (timer'ı yeniden başlat).
        self._state_controller.set_state(AppState.SUCCESS)
        self.status_lbl.setText("● SİSTEM AKTİF")
        is_fin = _is_finance_content(text)
        if is_fin:
            self.core.set_state("finance")
        spoken_text = text.split("\n\nGüven ve kaynak durumu:", 1)[0]
        speak_async(spoken_text, finance_mode=is_fin)
        QTimer.singleShot(2500, lambda: self.core.set_state("idle"))

    @staticmethod
    def _task_step_failed(text: str) -> bool:
        lowered = (text or "").casefold()
        return any(
            marker in lowered
            for marker in (
                "hata:",
                "başarısız",
                "başlatılamadı",
                "açılamadı",
                "bulunamadı",
                "engellendi",
                "zaman aşımına",
                "izin verilmiyor",
            )
        )

    def _on_error(self, e):
        if self._awaiting_task_step:
            failed_index = self._active_task_index + 1
            try:
                self.task_center.update_step(
                    self._active_task_id,
                    self._active_task_index,
                    StepStatus.FAILED,
                    str(e)[:300],
                )
            except (KeyError, IndexError):
                logger.exception("[TaskCenter] Hata durumu kaydedilemedi.")
            self._finish_task_record(
                self._active_task_id,
                TaskStatus.FAILED,
                f"{failed_index}. adım hata verdi: {e}",
            )
            self._active_task_id = None
            self._active_task_steps = None
            self._awaiting_task_step = False
        self._add_response(f"Hata: {e}")
        self.core.set_state("error")

    def _sync_border(self, core_state: str) -> None:
        """CoreWidget durumundan ince durum çerçevesini güncelle (Özellik 7).

        - error → kırmızı; done → yeşil (12 sn); thinking/listening/atlas/
          finance/briefing → mavi; idle → nefesli nötr (success beklemesinde
          yeşil korunur — ``notify_idle``).
        """
        if core_state == "error":
            self._state_controller.set_state(AppState.ERROR)
        elif core_state == "done":
            self._state_controller.set_state(AppState.SUCCESS)
        elif core_state == "idle":
            self._state_controller.notify_idle()
        else:
            self._state_controller.set_state(AppState.BUSY)

    def _handle_atlas_memory_command(self, text: str) -> str | None:
        return self.skill_registry.dispatch("local_memory", text)

    def _run_local_memory_skill(self, text: str) -> str | None:
        history_query = re.fullmatch(
            r"(?:sohbet geçmişinde ara|sohbet gecmisinde ara)\s+(.+)",
            text.strip(),
            re.IGNORECASE,
        )
        if history_query:
            matches = db_search_messages(
                history_query.group(1),
                limit=5,
                exclude_content=text.strip(),
            )
            if not matches:
                return "Yerel sohbet geçmişinde eşleşme bulunamadı."
            return "Yerel sohbet geçmişi sonuçları:\n" + "\n".join(
                f"• {match['title']} — {str(match['ts'] or 'Tarih bilinmiyor')[:16]} "
                f"({'Sen' if match['role'] == 'user' else 'JARVIS'})\n"
                f"  {match['content'][:500]}"
                for match in matches
            )

        remember_match = re.fullmatch(
            r"(?:hafızaya ekle|hafizaya ekle)\s+(.+?)\s*:\s*(.+)",
            text.strip(),
            re.IGNORECASE,
        )
        if remember_match:
            title, content = remember_match.groups()
            source = f"Not: {safe_user_text(title, 120)}"
            atlas_memory_add_fact(safe_user_text(content, 5000), source)
            return f"'{source[5:]}' yerel Atlas hafızasına kaydedildi."

        memory_query = re.fullmatch(
            r"(?:hafızada ara|hafizada ara)\s+(.+)",
            text.strip(),
            re.IGNORECASE,
        )
        if memory_query:
            matches = atlas_memory_search(memory_query.group(1), limit=5)
            if not matches:
                return "Yerel Atlas hafızasında eşleşme bulunamadı."
            return "Yerel Atlas hafızası sonuçları:\n" + "\n".join(
                f"• {match.source} — %{round(match.score * 100)} eşleşme\n"
                f"  {match.content[:500]}"
                for match in matches
            )

        delete_match = re.fullmatch(
            r"(?:hafızadan sil|hafizadan sil)\s+(.+)",
            text.strip(),
            re.IGNORECASE,
        )
        if delete_match:
            source = safe_user_text(delete_match.group(1), 250)
            deleted = atlas_memory_delete_source(source)
            if deleted == 0:
                return f"'{source}' kaynağı yerel hafızada bulunamadı."
            return f"'{source}' kaynağından {deleted} hafıza parçası silindi."

        return None

    def _dispatch_presentation_skill(self, text: str) -> str | None:
        lowered = (text or "").casefold()
        if "sunum" not in lowered and "slayt" not in lowered and "prezentasyon" not in lowered:
            return None
        if not any(
            marker in lowered
            for marker in ("hazırla", "olustur", "oluştur", "yap", "yarat")
        ):
            return None
        self._start_presentation(text)
        return "__async__"

    # ── ÖZEL KOMUTLAR (v9: FinCore + LongMemory komutları eklendi) ─────────
    def _handle_special(self, text: str) -> str | None:
        t = text.lower().strip()

        offline_result = handle_offline_command(text)
        if offline_result is not None:
            return offline_result

        briefing_schedule = re.fullmatch(
            r"her (?:gün|gun) saat\s+(\d{1,2}:\d{2})\s+(?:bana\s+)?brifing",
            text.strip(),
            re.IGNORECASE,
        )
        if briefing_schedule:
            try:
                routine_id = add_daily_briefing(briefing_schedule.group(1))
            except ValueError as exc:
                return f"Rutin oluşturulamadı: {exc}"
            return (
                f"Günlük brifing rutini #{routine_id} "
                f"saat {briefing_schedule.group(1)} için kaydedildi."
            )

        if t in {
            "rutinleri göster",
            "rutinleri goster",
            "zamanlanmış görevleri göster",
            "zamanlanmis gorevleri goster",
        }:
            routines = list_routines()
            if not routines:
                return "Zamanlanmış rutin yok."
            return "Zamanlanmış rutinler:\n" + "\n".join(
                f"#{routine.id} — {routine.title}, her gün {routine.run_at}"
                for routine in routines
            )

        routine_delete = re.fullmatch(
            r"(?:rutini sil|rutin sil)\s+(\d+)", t
        )
        if routine_delete:
            return self._delete_routine(int(routine_delete.group(1)))

        undo_request = re.fullmatch(
            r"geri al dosya\s+(.+)", text.strip(), re.IGNORECASE
        )
        if undo_request:
            return undo_last_text_edit(undo_request.group(1).strip())

        memory_reply = self._handle_atlas_memory_command(text)
        if memory_reply is not None:
            return memory_reply

        # Özellik 9: Prompt Mimarı modu (detaylı prompt üretimi)
        if is_prompt_request(t):
            self._start_prompt_architect(text)
            return "__async__"

        presentation_result = self.skill_registry.dispatch("presentation", text)
        if presentation_result is not None:
            return presentation_result

        # Özellik 5: dosya formatı dönüştürme (PDF/JPG/PNG/TXT)
        converted = self.skill_registry.dispatch("file_conversion", text)
        if converted is not None:
            return converted

        atlas_status_words = {
            "atlas var mı", "atlas var mi", "atlas açık mı", "atlas acik mi",
            "atlas durumu", "atlas modu",
        }
        if t in atlas_status_words:
            return f"ATLAS modu şu anda {'açık' if self.atlas_enabled else 'kapalı'}."
        if t in {"atlas aç", "atlasi aç", "atlası aç", "atlas ac"}:
            self._toggle_atlas(True)
            return "ATLAS modu açıldı. Bilgisayar ve web işlemleri hazır."
        if t in {"atlas kapat", "atlası kapat", "atlasi kapat"}:
            self._toggle_atlas(False)
            return "ATLAS modu kapatıldı."

        app_chain = re.fullmatch(
            r"(chrome|google chrome|edge|microsoft edge)\s+girip\s+(.+)$", t
        )
        if app_chain:
            first_result = open_allowed_app(app_chain.group(1))
            second_result = self._handle_special(app_chain.group(2).strip())
            if second_result is not None:
                return f"{first_result}\n{second_result}"

        chain_parts = re.split(r"\s+(?:sonra|ardından|ardindan)\s+", t, maxsplit=3)
        if len(chain_parts) > 1:
            chain_results = []
            for part in chain_parts:
                result = self._handle_special(part.strip())
                if result is None or result == "__async__":
                    chain_results = []
                    break
                chain_results.append(result)
            if chain_results:
                return "\n".join(chain_results)

        site_aliases = {
            "sahibinden": "https://www.sahibinden.com",
            "sahibinden.com": "https://www.sahibinden.com",
            "yemeksepeti": "https://www.yemeksepeti.com",
            "yemeksepeti.com": "https://www.yemeksepeti.com",
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
        }
        site_match = re.fullmatch(
            r"(.+)\s+(?:gir|aç|ac|açık|açınız)$", t
        )
        if site_match:
            site_name = site_match.group(1).strip()
            site_url = site_aliases.get(site_name)
            if site_url is None:
                for alias, alias_url in site_aliases.items():
                    if site_name in {f"{alias}e", f"{alias}a", f"{alias}ye", f"{alias}ya", f"{alias}de", f"{alias}da"}:
                        site_url = alias_url
                        break
            if site_url:
                return open_web_url(site_url)

        google_search = re.fullmatch(
            r"google(?:'da|da|de| üzerinde)?\s+(.+?)\s+ara$", t
        )
        if google_search:
            return open_google(google_search.group(1))

        youtube_search = re.fullmatch(
            r"youtube(?:'da|da|de| üzerinde)?\s+(.+?)\s+ara$", t
        )
        if youtube_search:
            return open_youtube(youtube_search.group(1))

        food_match = re.search(
            r"(?:yemeksepeti|yemek sepeti)(?:['’]?(?:ne|den|dan))?\s+"
            r"(?:gir(?:ip)?\s+)?(?:ara|bul)\s+(.+)$|"
            r"(?:yemeksepeti|yemek sepeti)(?:['’]?(?:ne|den|dan))?\s+"
            r"(?:gir(?:ip)?\s+)?(.+?)\s+(?:ara|bul)$",
            t,
        )
        if food_match:
            return marketplace_search("yemeksepeti", food_match.group(1) or food_match.group(2))

        car_match = re.search(
            r"sahibinden(?:['’]?(?:e|de|da))?\s+"
            r"(?:gir(?:ip)?\s+)?(?:ara|bul)\s+(.+)$|"
            r"sahibinden(?:['’]?(?:e|de|da))?\s+"
            r"(?:gir(?:ip)?\s+)?(.+?)\s+(?:ara|bul)$",
            t,
        )
        if car_match:
            return marketplace_search("sahibinden", car_match.group(1) or car_match.group(2))

        if (re.search(r"yemeksepeti.*sipariş", t)
            or re.search(r"sahibinden.*(?:satıcıya|ilan sahibine).*mesaj", t)
            or re.search(r"(?:sipariş et|satın al|ödeme yap|kart bilgisi|satıcıya mesaj)", t)):
            return (
                "ATLAS arama ve seçenekleri hazırlama aşamasında yardımcı olur; "
                "sipariş, ödeme veya satıcıya mesaj gönderme işlemini otomatik yapmaz."
            )

        app_open_match = re.fullmatch(
            r"(.+?)\s+(?:gir|başlat|baslat|çalıştır|calistir)$", t
        )
        if app_open_match:
            app_name = app_open_match.group(1).strip()
            if app_name in site_aliases:
                return open_web_url(site_aliases[app_name])
            res = open_allowed_app(app_name)
            if "allowlist" not in res:
                return res

        web_open_match = re.search(r"(?:web sitesi|site|url)\s+a[çc]\s+(https://\S+)$", text, re.IGNORECASE)
        if web_open_match:
            return open_web_url(web_open_match.group(1))

        # Bounded Windows control: inspection is read-only; UI mutation is confirmation-gated.
        app_match = re.search(r"(?:uygulama|program)\s+(.+?)\s+a[çc]$|^(.+?)\s+a[çc]$", t)
        if app_match:
            app_name = (app_match.group(1) or app_match.group(2)).strip()
            if app_name not in {"google", "youtube"}:
                res = open_allowed_app(app_name)
                if "allowlist" not in res:
                    return res

        if any(k in t for k in ["açık pencereler", "hangi pencereler", "pencereleri analiz"]):
            return list_open_windows()
        if any(k in t for k in ["aktif pencere", "hangi uygulama açık"]):
            return active_window_title()
        if any(k in t for k in ["ekran görüntüsü", "ekranı analiz et", "ekrana bak"]):
            return analyze_screen() if self.atlas_enabled else capture_screen()
        if any(k in t for k in ["işlemleri analiz", "processleri analiz", "hangi işlemler"]):
            return system_processes()
        if "ayarları aç" in t or "windows ayarları" in t:
            section = next((name for name in ["wifi", "ağ", "ses", "ekran", "bluetooth", "uygulamalar"] if name in t), "")
            return open_windows_settings(section)

        click_match = re.search(r"(?:tıkla|tikla)\s+(\d+)\s*[, ]\s*(\d+)", t)
        if click_match:
            return click_screen(int(click_match.group(1)), int(click_match.group(2)))

        move_match = re.search(
            r"(?:fareyi|mouse(?:'u|u|yi)?)\s+(?:götür|gotur|taşı|tasi|hareket ettir)\s+"
            r"(?:x\s*)?(\d+)\s*[, ]\s*(?:y\s*)?(\d+)", t
        )
        if move_match:
            return move_mouse(int(move_match.group(1)), int(move_match.group(2)))

        type_match = re.search(r"(?:aktif pencereye|klavyeye)\s+yaz\s+(.+)$", text, re.IGNORECASE)
        if type_match:
            return type_text(type_match.group(1))

        # Atlas browser and read-only computer actions.
        google_match = re.search(r"google(?:'|’)?dan\s+(.+?)(?:\s+a[çc]|$)", t)
        if google_match or t in {"google aç", "google ac", "google"}:
            return open_google(google_match.group(1) if google_match else "")

        if t in {"müzik", "muzik", "müzik aç", "muzik ac", "müzik çal", "muzik cal"}:
            if not self.atlas_enabled:
                return "YouTube otomasyonu için önce ATLAS modunu açın."
            self._automation.start_youtube("müzik")
            return "ATLAS YouTube otomasyonu başladı: müzik"

        if any(k in t for k in ["sistem durumu", "bilgisayar durumu", "bilgisayarımı kontrol et"]):
            return system_summary()

        local_match = re.search(
            r"(?:bilgisayarımda|bilgisayarimda|dosya ara|bulabilir misin)\s+(.+?)(?:\s+var mı|\s+var mi|$)",
            t,
        )
        if local_match:
            return find_local_item(local_match.group(1))

        # ── v9: Günlük brifing ──
        if any(k in t for k in ["brifing", "günlük özet", "sabah özeti", "bugün ne var",
                                  "daily briefing"]):
            self._fetch_briefing(); return "__async__"

        # ── v9: Döviz kur sorguları ──
        if is_currency_query(text):
            self.core.set_state("finance")
            self._add_response("Kur sorgulanıyor...")
            worker = CurrencyWorker(text)
            worker.result.connect(
                lambda result: (self._add_response(result), self.core.set_state("idle"))
            )
            worker.error.connect(self._on_error)
            self._start_worker(worker)
            return "__async__"

        if any(k in t for k in ["kur paneli", "döviz tablosu", "tüm kurlar", "döviz pano"]):
            self._fetch_fx_board(); return "__async__"

        # ── v9: Hisse senedi sorguları ──
        # "THYAO.IS hissesi" veya "hisse THYAO.IS"
        stock_match = re.search(
            r"(?:hisse|fiyat|borsa)[\s:]+([A-Z]{2,6}(?:\.[A-Z]{1,3})?)|"
            r"([A-Z]{2,6}(?:\.[A-Z]{1,3})?)\s+(?:hissesi|fiyatı|hisse fiyatı)",
            text, re.IGNORECASE)
        if stock_match:
            ticker = (stock_match.group(1) or stock_match.group(2)).upper()
            self.core.set_state("finance")
            self._add_response(f"{ticker} için anlık fiyat alınıyor...")
            w = StockWorker(ticker)
            w.finished.connect(lambda r: (self._add_response(r), self.core.set_state("idle")))
            self._start_worker(w)
            return "__async__"

        # ── v9: Teknik analiz ──
        tech_match = re.search(
            r"(?:teknik analiz|ma analiz|rsi|analiz)[\s:]+([A-Z]{2,6}(?:\.[A-Z]{1,3})?)|"
            r"([A-Z]{2,6}(?:\.[A-Z]{1,3})?)\s+(?:teknik|analiz|rsi|ma)",
            text, re.IGNORECASE)
        if tech_match:
            ticker = (tech_match.group(1) or tech_match.group(2)).upper()
            self.core.set_state("finance")
            self._add_response(f"{ticker} için teknik analiz hesaplanıyor...")
            w = TechAnalysisWorker(ticker)
            w.finished.connect(lambda r: (self._add_response(r), self.core.set_state("idle")))
            self._start_worker(w)
            return "__async__"

        # ── v9: Takip listesi ──
        if any(k in t for k in ["takip listesi", "watchlist", "favori hisseler"]):
            self._fetch_watchlist(); return "__async__"

        add_match = re.search(r"takip ekle\s+([A-Z]{2,6}(?:\.[A-Z]{1,3})?)", text, re.IGNORECASE)
        if add_match:
            ticker = add_match.group(1).upper()
            if PROFILE.add_favorite_stock(ticker):
                return f"'{ticker}' takip listesine eklendi, Efendim."
            return f"'{ticker}' zaten takip listenizde."

        rem_match = re.search(r"takip (?:çıkar|kaldır|sil)\s+([A-Z]{2,6}(?:\.[A-Z]{1,3})?)",
                              text, re.IGNORECASE)
        if rem_match:
            ticker = rem_match.group(1).upper()
            if PROFILE.remove_favorite_stock(ticker):
                return f"'{ticker}' takip listesinden çıkarıldı, Efendim."
            return f"'{ticker}' takip listenizde değil."

        # ── v9: Profil yönetimi ──
        if any(k in t for k in ["profilim", "profil göster", "beni hatırlıyor musun"]):
            self._show_profile(); return "__async__"

        name_match = re.search(r"(?:benim adım|adım)\s+([A-Za-zÇçĞğİıÖöŞşÜü]+)", text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).capitalize()
            profile_update("name", name)
            return f"Harika, sizi {name} olarak kaydettim. Bundan sonra {name} diye hitap edeceğim."

        if "resmi konuş" in t or "formal" in t:
            profile_update("preferred_tone", "formal")
            return "Bundan sonra resmi konuşacağım, Efendim."
        if "samimi konuş" in t or "casual" in t or "rahat konuş" in t:
            profile_update("preferred_tone", "casual")
            return "Anlaşıldı, samimi tonda devam edelim."

        note_add = re.search(r"not ekle\s+(.+?):\s*(.+)", text, re.IGNORECASE)
        if note_add:
            PROFILE.save_note(note_add.group(1).strip(), note_add.group(2).strip())
            return f"Not kaydedildi: '{note_add.group(1).strip()}'"

        # ── Yetenekler listesi ──
        if any(k in t for k in ["neler yapabilir", "özellikler", "ne yapabilir", "yeteneklerin"]):
            return self._capabilities_text()

        if "gereksizleri sil onayla" in t:
            return delete_junk_files()
        if any(k in t for k in ["gereksiz", "sistem temizle", "temp dosya"]):
            return find_junk_files()

        if any(k in t for k in ["hata", "error", "çözüm bul", "forum ara"]) and len(t) > 15:
            self._add_response("Hata çözümü aranıyor...")
            worker = ForumSearchWorker(text)
            worker.result.connect(
                lambda result: (self._add_response(result), self.core.set_state("idle"))
            )
            worker.error.connect(self._on_error)
            self._start_worker(worker)
            return "__async__"

        if any(k in t for k in ["speedtest", "hız testi", "internet hızı"]):
            self._run_speedtest(); return "__async__"

        if any(k in t for k in ["haber detay", "haberlerin içeriği", "haberleri oku"]):
            if classify_ai_request(text) is AIRequestType.WEB_SEARCH:
                return None
            self._fetch_news(True); return "__async__"
        if any(k in t for k in ["haber", "gündem", "son dakika"]):
            if classify_ai_request(text) is AIRequestType.WEB_SEARCH:
                return None
            self._fetch_news(False); return "__async__"

        # WhatsApp
        wa_match = re.search(
            r"([a-züğışöçÜĞİŞÖÇA-Z][a-züğışöçÜĞİŞÖÇ]+)['\u2019]?[eayi]+\s+(.+?)\s+yaz$",
            text, re.IGNORECASE)
        if wa_match or any(k in t for k in ["whatsapp", "mesaj at", "mesaj gönder"]):
            if wa_match:
                isim = wa_match.group(1); mesaj = wa_match.group(2)
                numara = contacts_find(isim)
                if numara:
                    return whatsapp_send(numara, mesaj)
                return f"'{isim}' rehberde yok. 'rehbere {isim} ekle +905xxxxxxxx'"
            ekle = re.search(r"rehbere\s+(\S+)\s+ekle\s+(\+?\d+)", t)
            if ekle:
                isim = ekle.group(1); num = ekle.group(2)
                if not num.startswith("+"): num = "+" + num
                c = contacts_load(); c[isim] = num; contacts_save(c)
                return f"'{isim}' rehbere eklendi ({num}), Efendim."
            if "rehber" in t:
                c = contacts_load()
                if not c: return "Rehber boş. 'rehbere İsim ekle +905xxxxxxxx'"
                return "Kayıtlı kişiler:\n" + "\n".join(f"• {k}: {v}" for k, v in c.items())

        if any(k in t for k in ["tatil", "bayram", "resmi gün", "özel gün"]):
            return get_all_holidays()

        if any(k in t for k in ["masaüstü", "kısayol", "shortcut"]):
            return create_desktop_shortcut()

        if t in ["/yeni", "yeni oturum", "/temizle"]:
            # Oturum özeti kaydet
            if self.history:
                summary = f"Oturumda {len(self.history)} mesaj vardı."
                PROFILE.add_session_summary(summary)
            self.history.clear(); self.chat.clear_chat()
            self.session_id = db_new_session(); self.left.refresh_history()
            return "Yeni oturum açıldı, Efendim."

        if "yazıcıya at" in t:
            if self.attached: return self._print_epson(self.attached)
            return "Önce (+) ile dosya ekleyin, Efendim."

        return None

    @staticmethod
    def _delete_routine(routine_id: int) -> str:
        if remove_routine(routine_id):
            return f"Zamanlanmış rutin #{routine_id} silindi."
        return f"#{routine_id} numaralı rutin bulunamadı."

    def _capabilities_text(self) -> str:
        fav = PROFILE.get("favorite_stocks", [])
        return (
            f"J.A.R.V.I.S. v{APP_DISPLAY_VERSION} Apex — 2026 — Tam Özellik Listesi\n\n"
            f"v{APP_DISPLAY_VERSION} YENİLİKLERİ\n"
            f"  • Otomatik sunum: '... sunumu hazırla' (.pptx, Canva veya slayt görselleri)\n"
            f"  • Dosya dönüştürücü: 'bunu pdf yap', 'bunu txt yap' (PDF/JPG/PNG/TXT, OCR destekli)\n"
            f"  • Arıza giderme: '+' → Arıza → Windows/macOS (ATLAS uçtan uca çözüm dener)\n"
            f"  • 4 arama modu: Flash Lite / Flash / Pro / Deep Research (kaynak güvenilirlik analizi)\n"
            f"  • Eğitim: 1-12 müfredat + 3 sn doğrulama ('3. sınıf matematik: kesirler')\n"
            f"  • Prompt Mimarı: '... için detaylı prompt yaz' (8 maddelik kalite kontrolü)\n\n"
            f"FİNANS (FinCore)\n"
            f"  • Anlık döviz kurları (USD, EUR, GBP ve daha fazlası)\n"
            f"  • '100 dolar kaç TL?' veya 'euro ne kadar?' ile kur sorgula\n"
            f"  • Kur paneli: tüm favori kurlar bir arada\n"
            f"  • Hisse senedi: 'hisse THYAO.IS' veya 'AAPL fiyatı'\n"
            f"  • Teknik analiz: MA5, MA20, MA50, RSI14\n"
            f"  • Takip listesi: {', '.join(fav) if fav else 'Boş (takip ekle THYAO.IS)'}\n\n"
            f"BELLEK (LongMemory)\n"
            f"  • Kullanıcı adını, tercihlerini, favori hisseleri hatırlama\n"
            f"  • Oturum özetleri (son 10 oturum)\n"
            f"  • Özel not kayıt: 'not ekle başlık: içerik'\n\n"
            f"ATLAS YEREL HAFIZA\n"
            f"  • PDF belgeleri ve açıkça eklenen notlarda yerel arama\n"
            f"  • 'sohbet geçmişinde ara konu' ile bu bilgisayardaki sohbetleri arama\n"
            f"  • 'hafızaya ekle başlık: içerik' / 'hafızada ara konu'\n"
            f"  • 'hafızadan sil kaynak' ile kaynağı kaldırma\n"
            f"  • Model bağlamına ekleme yalnızca JARVIS_SHARE_CONTEXT açıkken\n\n"
            f"GÖREV PLANI & GÜVEN\n"
            f"  • 'planla: ...' veya '... sonra ...' ile önizleme ve onay\n"
            f"  • Görev Merkezi: adım ilerlemesi, hata ve iptal durumu\n"
            f"  • Beceri Kataloğu ve hata halinde kalan adımları durdurma\n"
            f"  • İzin tercihleri: her seferinde, bu oturumda veya engelle\n"
            f"  • Dosya düzenlemede önizleme; 'geri al dosya <yol>'\n"
            f"  • Yanıtlarda kaynak/eşleşme bilgisi ve doğrulanmadı uyarısı\n\n"
            f"ZAMANLANMIŞ RUTİNLER\n"
            f"  • 'her gün saat 08:30 brifing' ile günlük görev\n"
            f"  • 'rutinleri göster' / 'rutini sil <numara>'\n\n"
            f"BRİFİNG (v9 YENİ)\n"
            f"  • 'brifing' ile günlük haber + finans özeti\n"
            f"  • Sabah 8-10 arası otomatik brifing\n\n"
            f"SOHBET & ANALİZ\n"
            f"  • Doğal konuşma, soru cevaplama, analiz\n"
            f"  • Kod yazma, yazılım yardımı\n"
            f"  • TC kanunları, sağlık bilgisi\n\n"
            f"VERİ & ARAŞTIRMA\n"
            f"  • Hava durumu, haberler (başlık + içerik)\n"
            f"  • İnternet hız testi\n"
            f"  • Forum hata arama (Stack Overflow, GitHub)\n\n"
            f"DOSYA & İLETİŞİM\n"
            f"  • PDF yükleme ve soru cevaplama\n"
            f"  • WhatsApp mesaj gönderme\n\n"
            f"SİSTEM\n"
            f"  • CPU, RAM, pil takibi\n"
            f"  • Gereksiz dosya temizliği\n"
            f"  • Bellek/Profil ekranından yerel verileri görme ve yönetme\n"
            f"  • Kısa, dengeli veya detaylı yanıt tercihi\n"
            f"  • HTTPS yayın kaynağı tanımlandığında güvenli güncelleme denetimi\n"
            f"  • 'Hey Jarvis' / 'Apex' uyandırma\n"
            f"  • Profesyonel finans sesi (TTS)\n"
        )

    def _print_epson(self, path):
        if not SMTP_USER:
            return "JARVIS_SMTP_USER ortam değişkeni ayarlanmamış."
        if not EPSON_EMAIL:
            return "JARVIS_EPSON_EMAIL ortam değişkeni ayarlanmamış."
        try:
            resolved = safe_path_under_root(path, Path.home())
            if resolved is None or not resolved.exists() or resolved.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".txt"}:
                return "Yazdırılacak dosya geçersiz veya izin verilen alan dışında."
            msg = MIMEMultipart()
            msg["From"] = SMTP_USER; msg["To"] = EPSON_EMAIL; msg["Subject"] = "JARVIS Print"
            with open(resolved, "rb") as f:
                part = MIMEBase("application", "octet-stream"); part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment;filename="{resolved.name}"')
            msg.attach(part)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
                s.login(SMTP_USER, SMTP_PASS); s.send_message(msg)
            return f"Yazıcıya gönderildi: {resolved.name}"
        except Exception as e:
            return f"Yazıcı hatası: {e}"

    def _load_session(self, sid):
        self.session_id = sid
        display_limit = 100 if self.low_resource_mode else 500
        msgs = db_get_messages(sid, limit=display_limit)
        self.history = msgs[-40:]
        self.chat.clear_chat()
        for m in msgs: self.chat.add_bubble(m["role"], m["content"])

    # ── MONİTÖRLER ────────────────────────────────────────────────────────
    def _start_monitors(self):
        QTimer(self, timeout=self._night_check, interval=60000).start()
        QTimer(self, timeout=self._reminder_check, interval=60000).start()
        self._night_check()

    def _check_hardware_alerts(self, hw):
        if self._closing:
            return
        if hw["bat"] is not None:
            if hw["bat"] < 10 and not hw["charging"]:
                self.core.set_state("error")
                self._add_response(f"Kritik: Pil %{hw['bat']}! Şarj edin, Efendim.")
            if (self._prev_charging is not None
                    and hw["charging"] != self._prev_charging):
                self._add_response("Şarj bağlandı." if hw["charging"] else "Şarj çıkarıldı.")
            self._prev_charging = hw["charging"]
        if hw["cpu"] > 90:
            self._add_response(f"CPU %{hw['cpu']} — sistem yük altında.")
        if hw["ram"] > 90:
            self._add_response(f"RAM %{hw['ram']} — bellek kritik.")

    def _night_check(self):
        h = datetime.datetime.now().hour
        if 0 <= h < 6 and not self.night_mode:
            self.night_mode = True
            self.setStyleSheet("QMainWindow{background:#080508;}")
        elif not (0 <= h < 6) and self.night_mode:
            self.night_mode = False
            self.setStyleSheet(f"QMainWindow{{background:{C['bg']};}}")

    def _reminder_check(self):
        if self._closing or self._reminder_check_active:
            return
        self._reminder_check_active = True
        worker = ReminderCheckWorker()
        worker.result.connect(self._apply_reminder_check)
        worker.finished.connect(
            lambda: setattr(self, "_reminder_check_active", False)
        )
        self._start_worker(worker)

    def _apply_reminder_check(self, result):
        reminders, routines, errors = result
        if self._closing:
            return
        for _, title, _ in reminders:
            self._add_response(f"Hatırlatıcı: {title}")
        for routine in routines:
            if routine.action == "daily_briefing":
                self._add_response(
                    f"Zamanlanmış rutin çalışıyor: {routine.title} ({routine.run_at})."
                )
                self._fetch_briefing()
        if errors:
            self.status_lbl.setText("● HATIRLATICI/RUTİN KONTROLÜNDE HATA")
            logger.error("[Monitor] %s", "; ".join(errors))

    # ── UYANDIRMA KELİMESİ ────────────────────────────────────────────────
    def _start_wake_word(self):
        if (
            not SR_OK
            or not SETTINGS.get("wake_word", True)
            or self.low_bandwidth_mode
        ):
            if self.low_bandwidth_mode:
                self.wake_lbl.setText(
                    "● Uyandırma kapalı — düşük internet modu"
                )
            return
        self._wake = WakeWordListener()
        self._wake.triggered.connect(self._on_wake)
        self._wake.status.connect(lambda s: logger.info("[Wake] %s", s))
        self._wake.start()
        self.wake_lbl.setText("● Hey Jarvis / Apex: Aktif — Dinliyor")

    def _show_from_tray(self):
        """Tepsi 'Aç'/çift tıkla — ATLAS aktifken JARVIS açılmaz (dışlayıcı kural)."""
        if not self._window_manager.request_jarvis():
            return  # ATLAS zaten öne alındı
        self.show()

    def _on_wake(self):
        if not self._window_manager.request_jarvis():
            # ATLAS aktif: JARVIS açılmaz; ATLAS öne alınır, sesli dinleme başlamaz.
            logger.info("[Wake] ATLAS aktif — JARVIS açma isteği reddedildi.")
            return
        self.activateWindow(); self.raise_()
        self.core.set_state("listening")
        self.wake_lbl.setText("● Uyandırma: Tetiklendi!")
        QTimer.singleShot(100, self._start_voice_listen)

    # ── SİSTEM TRAY ───────────────────────────────────────────────────────
    def _system_tray(self):
        try:
            icon_path = Path(__file__).resolve().with_name("JARVIS.ico")
            icon = QIcon(str(icon_path)) if icon_path.is_file() else QApplication.windowIcon()
            if icon.isNull():
                logger.warning("[Tray] Simge bulunamadı; sistem tepsisi devre dışı.")
                return
            self.setWindowIcon(icon)
            self.tray = QSystemTrayIcon(self)
            self.tray.setIcon(icon)
            self.tray.setToolTip(
                f"J.A.R.V.I.S. v{APP_DISPLAY_VERSION} Apex"
            )
            menu = QMenu()
            menu.addAction("Aç", self._show_from_tray)
            menu.addAction("Kapat", QApplication.quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(
                lambda r: self._show_from_tray()
                if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
            self.tray.show()
        except Exception:
            logger.exception("[Tray] Sistem tepsisi başlatılamadı")

    def closeEvent(self, event):
        if self._shutdown_complete:
            event.accept()
            return
        event.ignore()
        if self._closing:
            return
        self._closing = True
        self._automation.stop()
        self._countdown.stop_countdown()
        for timer in self.findChildren(QTimer):
            timer.stop()
        self.left.prepare_for_shutdown()
        if self._atlas_overlay is not None:
            self._atlas_overlay.close()
        # Oturum özeti kaydet
        if self.history and not self._session_summary_saved:
            user_msgs = [m["content"][:50] for m in self.history if m["role"] == "user"]
            summary = f"{len(user_msgs)} mesaj. Konular: {', '.join(user_msgs[:3])}"
            PROFILE.add_session_summary(summary)
            self._session_summary_saved = True
        wake = getattr(self, "_wake", None)
        if wake is not None and wake.isRunning():
            wake.stop()
            wake.requestInterruption()
            wake.quit()
        for worker in list(self._threads):
            if isinstance(worker, AIWorker):
                worker.cancel()
            elif isinstance(worker, ResearchWorker):
                worker.cancel()
            else:
                worker.requestInterruption()
            worker.quit()
        self._shutdown_started_at = time.monotonic()
        self.hide()
        QTimer.singleShot(0, self._poll_close_workers)

    def _poll_close_workers(self):
        wake = getattr(self, "_wake", None)
        workers_running = (
            any(worker.isRunning() for worker in self._threads)
            or self.left.side_worker_running
        )
        automation_running = self._automation.is_running
        if workers_running or (wake is not None and wake.isRunning()) or automation_running:
            elapsed = time.monotonic() - (self._shutdown_started_at or time.monotonic())
            if elapsed >= self._shutdown_timeout_seconds:
                worker_names = [
                    type(worker).__name__ for worker in self._threads if worker.isRunning()
                ]
                if self.left.side_worker_running:
                    worker_names.append("SidePanelWorker")
                if wake is not None and wake.isRunning():
                    worker_names.append(type(wake).__name__)
                if automation_running:
                    worker_names.append("ATLAS automation")
                logger.error(
                    "Shutdown exceeded %ss; workers still active: %s",
                    self._shutdown_timeout_seconds,
                    ", ".join(worker_names),
                )
                self._closing = False
                self.left.resume_after_shutdown()
                self.show()
                self.status_lbl.setText("● KAPATMA BEKLETİLDİ — ARKA PLAN İŞİ SÜRÜYOR")
                self._add_response(
                    "Kapatma güvenlik için durduruldu; şu işler hâlâ çalışıyor: "
                    + ", ".join(worker_names)
                    + ". İş tamamlanınca tekrar kapatabilirsiniz."
                )
                for timer in self.findChildren(QTimer):
                    if not timer.isActive():
                        timer.start()
                self.left.set_low_bandwidth_mode(self.low_bandwidth_mode)
                self._shutdown_started_at = None
                return
            QTimer.singleShot(100, self._poll_close_workers)
            return
        self._threads.clear()
        close_marketplace_browser()
        self._shutdown_complete = True
        self.close()

# ══════════════════════════════════════════════════════════════════════════
# BAŞLAT
# ══════════════════════════════════════════════════════════════════════════
def main():
    if not PYQT_OK:
        logger.error("Eksik: GUI kütüphanesi bulunamadı. pip install PySide6")
        print("Eksik: GUI kütüphanesi bulunamadı. Lütfen şu komutla kurun: pip install PySide6")
        sys.exit(1)

    if not GROQ_API_KEY and not GEMINI_API_KEY:
        logger.warning(
            "Groq ve Gemini API anahtarları bulunamadı. "
            "AI sohbeti için GROQ_API_KEY veya JARVIS_GEMINI_API_KEY ekleyin."
        )
        print(
            "Uyarı: AI sohbeti için .env dosyasına GROQ_API_KEY veya "
            "JARVIS_GEMINI_API_KEY ekleyin."
        )
    elif not GROQ_API_KEY:
        logger.info("Groq anahtarı yok; AI sohbeti Gemini sağlayıcısını kullanacak.")
    if not OWM_API_KEY:
        logger.warning("OWM_API_KEY bulunamadı. .env dosyasını veya ortam değişkenini ekleyin; hava durumu devre dışı kalacak.")
        print("Uyarı: OWM_API_KEY bulunamadı. .env dosyasını veya ortam değişkenini ekleyin; hava durumu devre dışı kalacak.")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,      QColor(C["bg"]))
    pal.setColor(QPalette.WindowText,  QColor(C["text"]))
    pal.setColor(QPalette.Base,        QColor(C["bg2"]))
    pal.setColor(QPalette.Text,        QColor(C["text"]))
    pal.setColor(QPalette.Button,      QColor(C["panel"]))
    pal.setColor(QPalette.ButtonText,  QColor(C["text"]))
    app.setPalette(pal)

    win = JarvisWindow()
    win.show()
    # Özellik 2: macOS ilk çalıştırmada izin rehberi (Windows'ta no-op).
    maybe_show_permissions_guide(win, SETTINGS, settings_save)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
