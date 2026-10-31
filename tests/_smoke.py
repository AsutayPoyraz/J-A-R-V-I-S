import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
import jarvis_v11

win = jarvis_v11.JarvisWindow()
win.show()
QTest.qWait(800)
# Özellik 6/4/10/3 bileşenleri yerinde mi?
checks = {
    "window_manager": hasattr(win, "_window_manager"),
    "state_controller": hasattr(win, "_state_controller"),
    "status_border": hasattr(win, "_status_border"),
    "operation_status": win.operation_status.text() == "Hazır",
    "cancel_button_hidden": not win.cancel_btn.isVisible(),
    "mode_box": hasattr(win, "mode_box"),
    "countdown": hasattr(win, "_countdown"),
    "troubleshoot_init": win._troubleshoot is None,
    "settings_btn": hasattr(win, "settings_btn"),
    "tray_ok": hasattr(win, "tray"),
}
print("checks:", checks)
assert all(checks.values()), checks
# Merkezi widget StatusBorderWidget mi?
from status_border import StatusBorderWidget

assert isinstance(win.centralWidget(), StatusBorderWidget), type(win.centralWidget())
print("central=StatusBorderWidget OK")
# Simülasyon: ATLAS aç/kapat (Özellik 6 dışlayıcı)
win._toggle_atlas(True)
QTest.qWait(300)
from window_manager import ActiveWindow

assert win._window_manager.active is ActiveWindow.ATLAS
assert win.atlas_enabled
assert not win.isVisible()
assert win._atlas_overlay is not None and win._atlas_overlay.isVisible()
win._toggle_atlas(False)
QTest.qWait(300)
assert win._window_manager.active is ActiveWindow.JARVIS
assert not win.atlas_enabled
assert win.isVisible()
assert not win._atlas_overlay.isVisible()
print("ATLAS toggle exclusivity OK")
win.close()
shutdown_deadline = time.monotonic() + win._shutdown_timeout_seconds + 5
while not win._shutdown_complete and time.monotonic() < shutdown_deadline:
    QTest.qWait(100)
assert win._shutdown_complete, "Jarvis background workers did not shut down in time"
QTest.qWait(100)
print("SMOKE-TEST OK")
