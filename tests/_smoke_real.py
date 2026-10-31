import sys

sys.path.insert(0, r"f:\Software\JARVİS")
# GERÇEK ekran (offscreen DEĞİL) — fade/opacity gerçek platformda doğrulanır
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
import jarvis_v11

win = jarvis_v11.JarvisWindow()
win.show()
QTest.qWait(700)
win._toggle_atlas(True)
QTest.qWait(700)          # fade-in denemesi gerçek ekranda
from window_manager import ActiveWindow

assert win._window_manager.active is ActiveWindow.ATLAS
win._toggle_atlas(False)
QTest.qWait(700)          # dönüş fade'i
assert win._window_manager.active is ActiveWindow.JARVIS
op = win.windowOpacity()
assert 0.99 <= op <= 1.01, f"opacity={op}"   # fade tamamlanmış olmalı
print(f"REAL-SCREEN opacity={op:.3f}")
win.close()
QTest.qWait(800)
print("REAL-SCREEN SMOKE OK")
