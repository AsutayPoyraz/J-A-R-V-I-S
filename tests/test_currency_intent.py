import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import jarvis_v11
from services import currency


class CurrencyIntentTests(unittest.TestCase):
    def test_supported_currency_queries_are_recognized(self):
        for text in ("dolar ne kadar", "10 dolar kaç tl", "euro kuru nedir"):
            with self.subTest(text=text):
                self.assertTrue(jarvis_v11.is_currency_query(text))

    def test_regular_chat_is_not_routed_to_currency_worker(self):
        for text in ("bana espri yap", "bugün hava nasıl", "merhaba"):
            with self.subTest(text=text):
                self.assertFalse(jarvis_v11.is_currency_query(text))

    def test_amount_conversion_uses_injected_rates(self):
        result = currency.parse_currency_query(
            "10 dolar kaç TL",
            rate_lookup=lambda base: {"TRY": 32.5} if base == "USD" else {},
        )

        self.assertIn("10.00 USD = 325.0000 TRY", result)
        self.assertIn("1 USD = 32.5000 TRY", result)

    def test_exchange_rate_provider_falls_back_after_empty_primary_response(self):
        with mock.patch.object(
            currency,
            "get_cached_json",
            side_effect=[None, {"rates": {"TRY": 32.0}}],
        ) as get_json:
            rates = currency.get_exchange_rates("USD")

        self.assertEqual(rates, {"TRY": 32.0, "USD": 1.0})
        self.assertEqual(get_json.call_count, 2)
        self.assertIn("api.frankfurter.app", get_json.call_args_list[0].args[0])
        self.assertIn("api.exchangerate-api.com", get_json.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
