import os
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import jarvis_v11
from services.permissions import ActionCategory


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, value):
        for callback in self.callbacks:
            callback(value)


class _Worker:
    def __init__(self):
        self.result = _Signal()
        self.error = _Signal()
        self.finished = _Signal()
        self.started = False

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started

    def deleteLater(self, *_args):
        return None


class HardwareSamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_cpu_sampling_is_non_blocking(self):
        psutil = mock.Mock()
        psutil.cpu_percent.return_value = 12
        psutil.virtual_memory.return_value = mock.Mock(percent=40, used=1024**3)
        psutil.sensors_battery.return_value = None
        with mock.patch.object(jarvis_v11, "PSUTIL_OK", True), mock.patch.object(
            jarvis_v11, "psutil", psutil
        ):
            result = jarvis_v11.get_hw()

        self.assertEqual(result["cpu"], 12)
        psutil.cpu_percent.assert_called_once_with(interval=None)

    def test_pdf_worker_runs_loader_in_worker_run_method(self):
        worker = jarvis_v11.PdfLoadWorker("sample.pdf")
        received = []
        worker.result.connect(received.append)
        with mock.patch.object(jarvis_v11, "load_pdf", return_value="loaded") as load:
            worker.run()

        load.assert_called_once_with("sample.pdf")
        self.assertEqual(received, ["loaded"])

    def test_left_panel_hardware_timer_uses_its_own_labels(self):
        side_worker = _Worker()
        hardware_worker = _Worker()
        with mock.patch.object(
            jarvis_v11, "SidePanelWorker", return_value=side_worker
        ), mock.patch.object(
            jarvis_v11, "HardwareWorker", return_value=hardware_worker
        ):
            panel = jarvis_v11.LeftPanel()
            try:
                panel._hw()
                self.assertTrue(hardware_worker.started)
                hardware_worker.result.emit(
                    {"cpu": 21, "ram": 38, "ram_gb": 4.0,
                     "bat": 75, "charging": True}
                )
                self.assertEqual(panel.cpu_lbl.text(), "CPU: 21%")
                self.assertEqual(panel.ram_lbl.text(), "RAM: 38% (4.0 GB)")
                self.assertIn("75%", panel.bat_lbl.text())
            finally:
                panel.prepare_for_shutdown()
                panel.deleteLater()

    def test_left_panel_low_bandwidth_mode_suppresses_automatic_network_refresh(self):
        with mock.patch.object(
            jarvis_v11,
            "SidePanelWorker",
            side_effect=AssertionError("unexpected network request"),
        ):
            panel = jarvis_v11.LeftPanel(
                low_bandwidth_mode=True,
                low_resource_mode=True,
            )
            try:
                self.assertFalse(panel._side_refresh_timer.isActive())
                self.assertEqual(panel._hardware_timer.interval(), 30000)
                panel.prepare_for_shutdown()
                panel.resume_after_shutdown()
                panel.set_low_bandwidth_mode(True)
                self.assertFalse(panel._side_refresh_timer.isActive())
            finally:
                panel.prepare_for_shutdown()
                panel.deleteLater()

    def test_ai_worker_honors_cancellation_between_stream_chunks(self):
        worker = jarvis_v11.AIWorker(
            engine=mock.Mock(stream=lambda *_, **__: iter(["first chunk", "second chunk"])),
            history=[],
            msg="test",
        )
        received = {"tokens": [], "finished": [], "cancelled": []}
        worker.token.connect(received["tokens"].append)
        worker.finished.connect(received["finished"].append)
        worker.cancelled.connect(lambda: received["cancelled"].append(True))
        with mock.patch.object(
            worker, "isInterruptionRequested", side_effect=[False, True]
        ):
            worker.run()

        self.assertEqual(received["tokens"], ["first chunk"])
        self.assertEqual(received["finished"], [])
        self.assertEqual(received["cancelled"], [True])

    def test_ai_worker_cancel_closes_an_active_provider_stream(self):
        entered_read = threading.Event()
        released_read = threading.Event()
        cancelled = threading.Event()

        class _BlockingStream:
            def __iter__(self):
                return self

            def __next__(self):
                entered_read.set()
                released_read.wait(2)
                raise StopIteration

            def close(self):
                released_read.set()

        response = _BlockingStream()

        def engine_stream(*_, stream_callback=None, **__):
            stream_callback(response)
            yield from response

        worker = jarvis_v11.AIWorker(
            engine=mock.Mock(stream=engine_stream),
            history=[],
            msg="test",
        )
        worker.cancelled.connect(cancelled.set)
        worker.start()
        self.assertTrue(entered_read.wait(1))
        worker.cancel()
        self.assertTrue(worker.wait(1000))
        self.app.processEvents()

        self.assertTrue(released_read.is_set())
        self.assertTrue(cancelled.is_set())

    def test_research_worker_does_not_publish_result_after_cancel(self):
        class _ResearchEngine:
            llm_fn = None

            @staticmethod
            def research(*args, cancel=None, **kwargs):
                cancel.set()
                return object()

        worker = jarvis_v11.ResearchWorker("test query", "flash", None, True)
        received = {"results": [], "cancelled": []}
        worker.result.connect(received["results"].append)
        worker.cancelled.connect(lambda: received["cancelled"].append(True))
        with mock.patch.object(
            jarvis_v11, "get_research_engine", return_value=_ResearchEngine()
        ):
            worker.run()

        self.assertEqual(received["results"], [])
        self.assertEqual(received["cancelled"], [True])

    def test_new_management_dialogs_open_and_close_cleanly(self):
        window = jarvis_v11.JarvisWindow()

        def close_active_modal():
            modal = self.app.activeModalWidget()
            if modal is not None:
                modal.accept()

        try:
            for method_name in (
                "_show_task_center",
                "_show_skills_catalog",
                "_show_memory_controls",
                "_show_permission_settings",
                "_check_for_updates",
            ):
                with self.subTest(dialog=method_name):
                    QTimer.singleShot(50, close_active_modal)
                    if method_name == "_show_memory_controls":
                        with mock.patch.object(
                            jarvis_v11, "atlas_memory_list_sources", return_value=[]
                        ):
                            getattr(window, method_name)()
                    elif method_name == "_check_for_updates":
                        # v10: denetim UpdateCheckWorker (QThread) ile arka
                        # planda çalışır. Sahte worker ile hatayı senkron
                        # yayıp modalın (50 ms zamanlayıcıyla) kapanmasını
                        # doğrularız; gerçek ağ çağrısı yapılmaz.
                        fake = _Worker()
                        with mock.patch.object(
                            jarvis_v11, "UpdateCheckWorker", return_value=fake
                        ):
                            getattr(window, method_name)()
                            fake.error.emit("update source unavailable")
                            fake.finished.emit(None)
                    else:
                        getattr(window, method_name)()
        finally:
            window._automation.stop()
            window.left.prepare_for_shutdown()
            for timer in window.findChildren(jarvis_v11.QTimer):
                timer.stop()
            window._shutdown_complete = True
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_send_enforces_session_permission_and_replays_only_after_approval(self):
        with mock.patch.object(
            jarvis_v11, "SidePanelWorker", return_value=_Worker()
        ), mock.patch.object(
            jarvis_v11, "HardwareWorker", return_value=_Worker()
        ):
            window = jarvis_v11.JarvisWindow()
        window.history = [{"role": "user", "content": "earlier message"}]
        window.permission_manager.set_preference(
            ActionCategory.PAYMENT, "session"
        )
        request = "ödeme yap"
        try:
            with mock.patch.object(
                window, "_handle_special", return_value="İşlem onaylandı."
            ) as handler, mock.patch.object(
                jarvis_v11, "db_save_msg"
            ), mock.patch.object(jarvis_v11, "style_update"), mock.patch.object(
                jarvis_v11, "speak_async"
            ), mock.patch.object(
                jarvis_v11.QTimer, "singleShot"
            ):
                window.input_box.setText(request)
                window._send()

                self.assertTrue(window.verifier.has_pending)
                self.assertFalse(
                    window.permission_manager.is_session_approved(
                        ActionCategory.PAYMENT
                    )
                )
                handler.assert_not_called()

                window.input_box.setText("onayla")
                window._send()

                handler.assert_called_once_with(request)
                self.assertTrue(
                    window.permission_manager.is_session_approved(
                        ActionCategory.PAYMENT
                    )
                )
                window.permission_manager.set_preference(
                    ActionCategory.PAYMENT, "never"
                )
                window.input_box.setText(request)
                window._send()
                handler.assert_called_once_with(request)
        finally:
            window._automation.stop()
            window.left.prepare_for_shutdown()
            for timer in window.findChildren(jarvis_v11.QTimer):
                timer.stop()
            window._shutdown_complete = True
            window.close()
            window.deleteLater()
            self.app.processEvents()


class UpdateCheckFlowTests(unittest.TestCase):
    """Otomatik güncelleme denetimi: koruma zinciri + arka plan worker'ı."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _fake_window(self, **overrides):
        defaults = dict(
            _shutdown_complete=False,
            _closing=False,
            low_bandwidth_mode=False,
            _threads=set(),
            _update_worker=None,
            _start_update_check=mock.Mock(),
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_auto_check_skipped_when_device_pref_disabled(self):
        window = self._fake_window()
        with mock.patch.object(
            jarvis_v11, "load_device_pref", return_value=False
        ):
            jarvis_v11.JarvisWindow._maybe_auto_check_updates(window)
        window._start_update_check.assert_not_called()

    def test_auto_check_skipped_in_low_bandwidth_mode(self):
        window = self._fake_window(low_bandwidth_mode=True)
        with mock.patch.object(
            jarvis_v11, "load_device_pref", return_value=True
        ):
            jarvis_v11.JarvisWindow._maybe_auto_check_updates(window)
        window._start_update_check.assert_not_called()

    def test_auto_check_skipped_when_update_source_not_configured(self):
        window = self._fake_window()
        with mock.patch.object(
            jarvis_v11, "load_device_pref", return_value=True
        ), mock.patch.object(
            jarvis_v11, "is_update_check_configured", return_value=False
        ):
            jarvis_v11.JarvisWindow._maybe_auto_check_updates(window)
        window._start_update_check.assert_not_called()

    def test_auto_check_skipped_while_closing(self):
        window = self._fake_window(_closing=True)
        jarvis_v11.JarvisWindow._maybe_auto_check_updates(window)
        window._start_update_check.assert_not_called()

    def test_auto_check_starts_quiet_background_check_when_guards_pass(self):
        window = self._fake_window()
        with mock.patch.object(
            jarvis_v11, "load_device_pref", return_value=True
        ), mock.patch.object(
            jarvis_v11, "is_update_check_configured", return_value=True
        ):
            jarvis_v11.JarvisWindow._maybe_auto_check_updates(window)
        window._start_update_check.assert_called_once_with(manual=False)

    def test_update_check_worker_emits_result_from_background(self):
        worker = jarvis_v11.UpdateCheckWorker()
        received = []
        worker.result.connect(received.append)
        info = mock.Mock(update_available=False)
        with mock.patch.object(
            jarvis_v11, "check_for_update", return_value=info
        ):
            worker.run()
        self.assertEqual(received, [info])

    def test_update_check_worker_emits_error_message_on_failure(self):
        worker = jarvis_v11.UpdateCheckWorker()
        received = []
        worker.error.connect(received.append)
        with mock.patch.object(
            jarvis_v11,
            "check_for_update",
            side_effect=ValueError("update source unavailable"),
        ):
            worker.run()
        self.assertEqual(received, ["update source unavailable"])


if __name__ == "__main__":
    unittest.main()
