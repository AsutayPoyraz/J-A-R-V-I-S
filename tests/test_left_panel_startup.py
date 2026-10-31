import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import jarvis_v11


class _Signal:
    def connect(self, callback):
        return None


class _Worker:
    def __init__(self):
        self.result = _Signal()
        self.error = _Signal()
        self.finished = _Signal()
        self.started = False

    def start(self):
        self.started = True

    def deleteLater(self):
        return None

    def isRunning(self):
        return self.started


class LeftPanelStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_initial_side_panel_refresh_owns_and_starts_its_worker(self):
        worker = _Worker()
        with mock.patch.object(jarvis_v11, "SidePanelWorker", return_value=worker):
            panel = jarvis_v11.LeftPanel()
            try:
                self.assertTrue(panel._side_refresh_active)
                self.assertIs(panel._side_worker, worker)
                self.assertTrue(worker.started)
            finally:
                panel.prepare_for_shutdown()
                panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
