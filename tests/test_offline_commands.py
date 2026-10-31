import datetime
import unittest
from types import SimpleNamespace

import jarvis_v11
from services.offline_commands import handle_offline_command


class OfflineCommandTests(unittest.TestCase):
    def test_time_and_date_use_the_supplied_local_clock(self):
        now = datetime.datetime(2026, 10, 3, 20, 43, 12)

        self.assertEqual(
            handle_offline_command("saat kaç?", now),
            "Yerel saat: 20:43:12.",
        )
        self.assertEqual(
            handle_offline_command("bugünün tarihi ne?", now),
            "Yerel tarih: 03.10.2026.",
        )

    def test_calculator_evaluates_arithmetic_without_executing_python(self):
        self.assertEqual(
            handle_offline_command("hesapla: 12 * (3 + 4)"),
            "Sonuç: 84",
        )
        self.assertEqual(
            handle_offline_command("1 / 4 kaç eder"),
            "Sonuç: 0.25",
        )

    def test_calculator_rejects_calls_names_and_oversized_exponents(self):
        for expression in (
            "__import__('os').system('whoami')",
            "open('secret.txt')",
            "2 ** 9",
        ):
            with self.subTest(expression=expression):
                result = handle_offline_command(f"hesapla: {expression}")
                self.assertTrue(result.startswith("Hesaplama yapılamadı:"))

    def test_unmatched_requests_are_left_for_other_handlers(self):
        self.assertIsNone(handle_offline_command("Bana bir hikaye anlat"))

    def test_help_discloses_offline_scope_and_cloud_ai_requirement(self):
        response = handle_offline_command("çevrimdışı komutlar")

        self.assertIn("saat kaç", response)
        self.assertIn("Genel AI yanıtları için internet gerekir", response)

    def test_main_window_routes_offline_commands_before_other_features(self):
        response = jarvis_v11.JarvisWindow._handle_special(
            SimpleNamespace(),
            "hesapla: 6 * 7",
        )

        self.assertEqual(response, "Sonuç: 42")


if __name__ == "__main__":
    unittest.main()
