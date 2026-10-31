import unittest

import jarvis_v11


class FinanceCalculationTests(unittest.TestCase):
    def test_rsi_calculation_does_not_require_numpy(self):
        self.assertEqual(jarvis_v11.compute_rsi([1, 2, 3, 2, 4], period=4), 80.0)

    def test_rsi_returns_none_for_insufficient_data_or_invalid_period(self):
        self.assertIsNone(jarvis_v11.compute_rsi([1, 2, 3], period=3))
        self.assertIsNone(jarvis_v11.compute_rsi([1, 2], period=0))

    def test_rsi_returns_one_hundred_when_window_has_no_losses(self):
        self.assertEqual(jarvis_v11.compute_rsi([1, 2, 3], period=2), 100.0)


if __name__ == "__main__":
    unittest.main()
