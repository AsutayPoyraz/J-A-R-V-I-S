"""
JARVIS v10 APEX PRIME — İzin & Onay Katmanı
=============================================
Tüm "geri dönüşü zor" eylemler bu modül üzerinden onaylanır.
Tercihler jarvis_settings.json içindeki SETTINGS dict'ine kaydedilir.

Eylem kategorileri:
  FILE_DELETE      — dosya silme
  FILE_WRITE       — dosya yazma / düzenleme
  CODE_EXEC        — kod çalıştırma
  PROGRAM_INSTALL  — program kurma / kaldırma
  SYSTEM_CHANGE    — sistem ayarı değiştirme
  MESSAGE_SEND     — mesaj / e-posta gönderme
  PAYMENT          — ödeme / satın alma
  NETWORK_ACTION   — ağ eylemi (bağlantı açma/kesme vb.)
  PROCESS_KILL     — işlem sonlandırma

Tercih seviyeleri:
  "always_ask" — Her seferinde sor (varsayılan)
  "session"    — Bu oturumda bir kere sor, sonra otomatik onayla
  "never"      — Asla yapma (engelle)
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from logger_setup import logger


# ── Eylem kategorileri ────────────────────────────────────────────────────
class ActionCategory(str, Enum):
    FILE_DELETE     = "file_delete"
    FILE_WRITE      = "file_write"
    CODE_EXEC       = "code_exec"
    PROGRAM_INSTALL = "program_install"
    SYSTEM_CHANGE   = "system_change"
    MESSAGE_SEND    = "message_send"
    PAYMENT         = "payment"
    NETWORK_ACTION  = "network_action"
    PROCESS_KILL    = "process_kill"


_CATEGORY_MARKERS = (
    (ActionCategory.MESSAGE_SEND, ("whatsapp", "mesaj gönder", "e-posta gönder")),
    (ActionCategory.FILE_DELETE, ("dosya sil", "geri al dosya", "gereksizleri sil")),
    (ActionCategory.FILE_WRITE, ("dosya düzenle", "klavyeye yaz", "aktif pencereye yaz")),
    (ActionCategory.CODE_EXEC, ("powershell", "cmd", "terminal", "kod çalıştır")),
    (
        ActionCategory.PROGRAM_INSTALL,
        ("program kur", "uygulama kur", "install", "programı kaldır", "uygulamayı kaldır"),
    ),
    (ActionCategory.SYSTEM_CHANGE, ("sistem ayar", "ayarları değiştir")),
    (ActionCategory.PROCESS_KILL, ("işlemi sonlandır", "process kill")),
    (ActionCategory.NETWORK_ACTION, ("ağ bağlantısını kes",)),
    (ActionCategory.PAYMENT, ("ödeme yap", "satın al")),
)


def category_for_request(text: str) -> ActionCategory | None:
    normalized = " ".join((text or "").casefold().split())
    for category, markers in _CATEGORY_MARKERS:
        if any(marker in normalized for marker in markers):
            return category
    if any(marker in normalized for marker in ("tıkla", "tikla", "webde aç", "tarayıcıda aç")):
        return ActionCategory.NETWORK_ACTION
    return None


# Kullanıcıya gösterilecek Türkçe kategori isimleri
CATEGORY_LABELS = {
    ActionCategory.FILE_DELETE:     "Dosya Silme",
    ActionCategory.FILE_WRITE:      "Dosya Yazma / Düzenleme",
    ActionCategory.CODE_EXEC:       "Kod Çalıştırma",
    ActionCategory.PROGRAM_INSTALL: "Program Kurma / Kaldırma",
    ActionCategory.SYSTEM_CHANGE:   "Sistem Ayarı Değiştirme",
    ActionCategory.MESSAGE_SEND:    "Mesaj / E-posta Gönderme",
    ActionCategory.PAYMENT:         "Ödeme / Satın Alma",
    ActionCategory.NETWORK_ACTION:  "Ağ Eylemi",
    ActionCategory.PROCESS_KILL:    "İşlem Sonlandırma",
}

# Risk seviyeleri (yüksek = daha ayrıntılı uyarı)
HIGH_RISK_CATEGORIES = {
    ActionCategory.FILE_DELETE,
    ActionCategory.PAYMENT,
    ActionCategory.PROGRAM_INSTALL,
    ActionCategory.SYSTEM_CHANGE,
}


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""


# ── Oturum bazlı onay önbelleği ───────────────────────────────────────────
class _SessionApprovalCache:
    def __init__(self):
        self._approved: set[ActionCategory] = set()
        self._lock = threading.Lock()

    def mark_approved(self, category: ActionCategory):
        with self._lock:
            self._approved.add(category)

    def is_approved(self, category: ActionCategory) -> bool:
        with self._lock:
            return category in self._approved

    def clear(self):
        with self._lock:
            self._approved.clear()


_session_cache = _SessionApprovalCache()


# ── PermissionManager ─────────────────────────────────────────────────────
class PermissionManager:
    """
    İzin yöneticisi. Qt dialog VEYA CLI fallback (headless mod) destekler.
    
    Kullanım:
        pm = get_permission_manager()
        result = pm.request(ActionCategory.FILE_DELETE,
                            "config.json silinecek",
                            details="Tam yol: C:/Users/x/config.json")
        if result.allowed:
            os.remove(...)
    """

    def __init__(self, settings: dict, audit_log_fn: Callable | None = None):
        """
        settings  : jarvis_v11.py'deki SETTINGS dict'i (canlı referans)
        audit_log_fn : db_log_action(category, description, result) imzalı fonksiyon
        """
        self._settings = settings
        self._audit_log_fn = audit_log_fn
        self._qt_available = self._check_qt()
        self._lock = threading.Lock()

    def _check_qt(self) -> bool:
        try:
            from PySide6.QtWidgets import QApplication
            return True
        except ImportError:
            try:
                from PyQt6.QtWidgets import QApplication
                return True
            except ImportError:
                try:
                    from PyQt5.QtWidgets import (
                        QApplication,  # noqa: F401 — alternatif Qt binding
                    )
                    return True
                except ImportError:
                    return False

    def _pref_key(self, category: ActionCategory) -> str:
        return f"perm_{category.value}"

    def get_preference(self, category: ActionCategory) -> str:
        """'always_ask' | 'session' | 'never' döndürür."""
        return self._settings.get(self._pref_key(category), "always_ask")

    def set_preference(self, category: ActionCategory, pref: str):
        """Kullanıcı tercihini SETTINGS'e yazar."""
        valid = {"always_ask", "session", "never"}
        if pref not in valid:
            raise ValueError(f"Geçersiz tercih: {pref}. Geçerli: {valid}")
        self._settings[self._pref_key(category)] = pref
        # Üst katman settings_save() çağırmalı
        logger.info("[Permissions] %s tercihi → %s", category.value, pref)

    def is_session_approved(self, category: ActionCategory) -> bool:
        return _session_cache.is_approved(category)

    def mark_session_approved(self, category: ActionCategory) -> None:
        _session_cache.mark_approved(category)

    def request(
        self,
        category: ActionCategory,
        description: str,
        details: str = "",
        undo_info: str = "",
    ) -> PermissionResult:
        """
        Eylem için kullanıcı onayı ister.
        
        Args:
            category    : Eylem kategorisi
            description : "config.json silinecek" gibi kısa açıklama
            details     : Tam yol, etkilenecek dosyalar vb.
            undo_info   : "Geri almak için: git revert xyz" gibi ipucu
        
        Returns:
            PermissionResult(allowed=True/False, reason=...)
        """
        pref = self.get_preference(category)

        # "never" → anında engelle
        if pref == "never":
            result = PermissionResult(False, f"{CATEGORY_LABELS[category]} tercihiniz 'asla yapma' olarak ayarlanmış.")
            self._log(category, description, False)
            return result

        # "session" ve bu oturumda zaten onaylandıysa → geç
        if pref == "session" and _session_cache.is_approved(category):
            result = PermissionResult(True, "Oturum onayı mevcut.")
            self._log(category, description, True)
            return result

        # Onay iste
        allowed = self._ask_user(category, description, details, undo_info)

        if allowed and pref == "session":
            _session_cache.mark_approved(category)

        self._log(category, description, allowed)
        return PermissionResult(allowed, "Kullanıcı onayladı." if allowed else "Kullanıcı reddetti.")

    def _ask_user(
        self,
        category: ActionCategory,
        description: str,
        details: str,
        undo_info: str,
    ) -> bool:
        """Qt dialog veya console ile onay ister."""
        if self._qt_available:
            return self._ask_qt(category, description, details, undo_info)
        return self._ask_console(category, description, details)

    def _ask_qt(self, category, description, details, undo_info) -> bool:
        """Qt dialog penceresi gösterir."""
        result_holder = [False]
        done_event = threading.Event()

        def _show():
            try:
                # Qt import (mevcut uygulamanın kullandığı hangisi ise)
                try:
                    from PySide6.QtCore import Qt
                    from PySide6.QtWidgets import (
                        QDialog,
                        QHBoxLayout,
                        QLabel,
                        QPushButton,
                        QTextEdit,
                        QVBoxLayout,
                    )
                except ImportError:
                    try:
                        from PyQt6.QtCore import Qt
                        from PyQt6.QtWidgets import (
                            QDialog,
                            QHBoxLayout,
                            QLabel,
                            QPushButton,
                            QTextEdit,
                            QVBoxLayout,
                        )
                    except ImportError:
                        from PyQt5.QtCore import Qt  # noqa: F401
                        from PyQt5.QtWidgets import (  # noqa: F401
                            QDialog,
                            QHBoxLayout,
                            QLabel,
                            QPushButton,
                            QTextEdit,
                            QVBoxLayout,
                        )

                is_high_risk = category in HIGH_RISK_CATEGORIES
                risk_color = "#ff4444" if is_high_risk else "#ff8800"

                dlg = QDialog()
                dlg.setWindowTitle("JARVIS — İzin Gerekli")
                dlg.setMinimumWidth(480)
                dlg.setStyleSheet("background:#0d1220; color:#c8d8f0; font-family:Consolas;")

                lay = QVBoxLayout(dlg)
                lay.setSpacing(10)
                lay.setContentsMargins(20, 16, 20, 16)

                # Başlık
                title = QLabel(f"⚠ {CATEGORY_LABELS[category]}")
                title.setStyleSheet(f"color:{risk_color};font:bold 14px Consolas;")
                lay.addWidget(title)

                # Açıklama
                desc_lbl = QLabel(description)
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet("color:#c8d8f0;font:12px Consolas;")
                lay.addWidget(desc_lbl)

                if details:
                    det_lbl = QLabel(f"Detay: {details}")
                    det_lbl.setWordWrap(True)
                    det_lbl.setStyleSheet("color:#4a6080;font:10px Consolas;")
                    lay.addWidget(det_lbl)

                if undo_info:
                    undo_lbl = QLabel(f"Geri alma: {undo_info}")
                    undo_lbl.setWordWrap(True)
                    undo_lbl.setStyleSheet("color:#00ffaa;font:10px Consolas;")
                    lay.addWidget(undo_lbl)

                if is_high_risk:
                    warn = QLabel("Bu işlem geri alınamayabilir. Devam etmek istiyor musunuz?")
                    warn.setStyleSheet("color:#ff4444;font:bold 11px Consolas;")
                    warn.setWordWrap(True)
                    lay.addWidget(warn)

                # Butonlar
                btn_row = QHBoxLayout()
                btn_row.setSpacing(8)

                cancel_btn = QPushButton("İptal")
                cancel_btn.setStyleSheet(
                    "QPushButton{background:#1a2540;color:#c8d8f0;border:1px solid #304060;"
                    "border-radius:6px;padding:6px 18px;font:Consolas;}"
                    "QPushButton:hover{background:#304060;}"
                )
                cancel_btn.clicked.connect(dlg.reject)
                btn_row.addWidget(cancel_btn)

                ok_btn = QPushButton("Onayla" if not is_high_risk else "Evet, Devam Et")
                ok_btn.setStyleSheet(
                    f"QPushButton{{background:{risk_color}22;color:{risk_color};border:1px solid {risk_color}60;"
                    f"border-radius:6px;padding:6px 18px;font:bold Consolas;}}"
                    f"QPushButton:hover{{background:{risk_color}44;}}"
                )
                ok_btn.clicked.connect(dlg.accept)
                btn_row.addWidget(ok_btn)

                lay.addLayout(btn_row)

                # Ana thread'de çalıştır
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    result_holder[0] = dlg.exec() == QDialog.DialogCode.Accepted
                else:
                    # Fallback: console
                    result_holder[0] = self._ask_console(category, description, details)
            except Exception as exc:
                logger.warning("[Permissions] Dialog hatası: %s — console'a düşüyorum.", exc)
                result_holder[0] = self._ask_console(category, description, details)
            finally:
                done_event.set()

        # Qt ana thread kontrolü
        try:
            from PySide6.QtCore import QMetaObject, Qt
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app and threading.current_thread() is not threading.main_thread():
                # Ana thread'e gönder
                QMetaObject.invokeMethod(app, lambda: _show(), Qt.ConnectionType.BlockingQueuedConnection)
            else:
                _show()
        except Exception:
            _show()

        done_event.wait(timeout=120)  # 2 dakika sonra otomatik reddet
        return result_holder[0]

    def _ask_console(self, category, description, details) -> bool:
        """Headless / console modunda basit input ile onay ister."""
        label = CATEGORY_LABELS[category]
        print(f"\n[JARVIS İzin] {label}: {description}")
        if details:
            print(f"  Detay: {details}")
        try:
            ans = input("  Onayla? [e/h]: ").strip().lower()
            return ans in {"e", "evet", "y", "yes"}
        except (EOFError, KeyboardInterrupt):
            return False

    def _log(self, category: ActionCategory, description: str, allowed: bool):
        """Audit log'a yaz."""
        try:
            if self._audit_log_fn:
                self._audit_log_fn(category.value, description, "onaylandı" if allowed else "reddedildi")
        except Exception as exc:
            logger.warning("[Permissions] Audit log hatası: %s", exc)

    def preference_summary(self) -> str:
        """Tüm kategorilerin tercih özetini döndürür."""
        lines = ["İzin Tercihleri:"]
        pref_labels = {
            "always_ask": "Her seferinde sor",
            "session": "Bu oturumda bir kere",
            "never": "Asla yapma",
        }
        for cat in ActionCategory:
            pref = self.get_preference(cat)
            lines.append(f"  {CATEGORY_LABELS[cat]:30} → {pref_labels.get(pref, pref)}")
        return "\n".join(lines)


# ── Singleton ────────────────────────────────────────────────────────────
_pm_instance: PermissionManager | None = None
_pm_lock = threading.Lock()


def init_permission_manager(settings: dict, audit_log_fn: Callable | None = None) -> PermissionManager:
    """Ana uygulama başlatılırken çağrılır."""
    global _pm_instance
    with _pm_lock:
        _pm_instance = PermissionManager(settings, audit_log_fn)
    return _pm_instance


def get_permission_manager() -> PermissionManager:
    """Singleton instance döndürür. init çağrılmamışsa minimal nesne döner."""
    global _pm_instance
    with _pm_lock:
        if _pm_instance is None:
            logger.warning("[Permissions] init_permission_manager() çağrılmadı, boş settings ile başlatılıyor.")
            _pm_instance = PermissionManager({})
    return _pm_instance


def clear_session_approvals():
    """Yeni oturum açıldığında çağrılır."""
    _session_cache.clear()
