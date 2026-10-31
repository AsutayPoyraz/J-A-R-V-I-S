import unittest
from types import SimpleNamespace
from unittest import mock

import jarvis_v11


def _content_chunk(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=None))]
    )


class AIFailoverTests(unittest.TestCase):
    def setUp(self):
        self.engine = object.__new__(jarvis_v11.AIEngine)
        self.engine.client = mock.Mock()
        self.engine.gemini_client = mock.Mock()

    def _stream(self, prompt):
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False):
            return list(self.engine.stream([], prompt))

    def test_gemini_is_used_when_groq_fails_before_producing_output(self):
        self.engine.client.chat.completions.create.side_effect = RuntimeError("Groq offline")
        self.engine.gemini_client.chat.completions.create.return_value = iter(
            [_content_chunk("Gemini yanıtı")]
        )

        output = "".join(self._stream("Merhaba"))

        self.assertIn("Gemini yedek modeli deneniyor", output)
        self.assertTrue(output.endswith("Gemini yanıtı"))
        self.engine.gemini_client.chat.completions.create.assert_called_once()
        self.assertEqual(
            self.engine.gemini_client.chat.completions.create.call_args.kwargs["model"],
            jarvis_v11.GEMINI_MODEL,
        )

    def test_gemini_is_not_used_after_groq_has_streamed_partial_answer(self):
        def interrupted_stream():
            yield _content_chunk("Kısmi cevap")
            raise RuntimeError("connection lost")

        self.engine.client.chat.completions.create.return_value = interrupted_stream()

        output = "".join(self._stream("Merhaba"))

        self.assertIn("Kısmi cevap", output)
        self.assertIn("yanıt akışı kesildi", output)
        self.engine.gemini_client.chat.completions.create.assert_not_called()

    def test_atlas_tools_are_included_in_gemini_fallback_request(self):
        self.engine.client.chat.completions.create.side_effect = RuntimeError("Groq offline")
        self.engine.gemini_client.chat.completions.create.return_value = iter(
            [_content_chunk("Komut anlaşıldı")]
        )

        list(self._stream("Chrome'u aç"))

        fallback_args = self.engine.gemini_client.chat.completions.create.call_args.kwargs
        self.assertEqual(fallback_args["tool_choice"], "auto")
        self.assertEqual(
            {tool["function"]["name"] for tool in fallback_args["tools"]},
            {"search_on_site", "open_url"},
        )

    def test_sync_chat_falls_back_to_gemini(self):
        self.engine.client.chat.completions.create.side_effect = RuntimeError("Groq offline")
        self.engine.gemini_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Gemini yanıtı"))]
        )
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False):
            reply = self.engine.chat([], "Merhaba")

        self.assertEqual(reply, "Gemini yanıtı")

    def test_low_bandwidth_mode_uses_long_timeout_without_retries_and_short_output(self):
        self.engine.low_bandwidth_mode = True
        self.engine.client.with_options.return_value = self.engine.client
        self.engine.client.chat.completions.create.return_value = iter(())

        list(self._stream("Merhaba"))

        self.engine.client.with_options.assert_called_once_with(
            timeout=300.0,
            max_retries=0,
        )
        request = self.engine.client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["max_tokens"], 256)

    def test_fact_question_prefers_gemini_before_groq(self):
        self.engine.gemini_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Bilgi yanıtı"))]
        )
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False):
            reply = self.engine.chat([], "Fotosentez nedir?")

        self.assertEqual(reply, "Bilgi yanıtı")
        self.engine.gemini_client.chat.completions.create.assert_called_once()
        self.engine.client.chat.completions.create.assert_not_called()

    def test_explicit_context_is_sent_but_old_history_stays_local(self):
        self.engine.client.chat.completions.create.return_value = iter(
            [_content_chunk("Yanıt")]
        )
        local_context = "Yerel alıntı: kullanıcı bilgisayarını güncelledi."
        old_history = [{"role": "user", "content": "private old conversation"}]
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False):
            list(self.engine.stream(
                old_history,
                "Devam et: bilgisayar",
                local_context,
            ))

        messages = self.engine.client.chat.completions.create.call_args.kwargs[
            "messages"
        ]
        request_text = "\n".join(message["content"] for message in messages)
        self.assertIn(local_context, request_text)
        self.assertNotIn("private old conversation", request_text)

    def test_web_search_uses_grounding_and_does_not_call_groq(self):
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False), \
             mock.patch.object(
                 jarvis_v11,
                 "gemini_grounded_search",
                 return_value="Güncel yanıt\n\nKaynaklar:\n• Örnek: https://example.com",
             ) as search:
            output = "".join(self._stream("Bugünkü son dakika haberleri neler?"))

        self.assertIn("Kaynaklar:", output)
        search.assert_called_once()
        self.assertIn("Google Search kullan", search.call_args.args[0])
        self.engine.client.chat.completions.create.assert_not_called()

    def test_failed_web_search_is_reported_without_ungrounded_fallback(self):
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False), \
             mock.patch.object(
                 jarvis_v11,
                 "gemini_grounded_search",
                 side_effect=RuntimeError("Gemini key missing"),
             ):
            output = "".join(self._stream("Bugünkü son dakika haberleri neler?"))

        self.assertIn("Web araması yapılamadı", output)
        self.engine.client.chat.completions.create.assert_not_called()

    def test_reports_missing_provider_configuration(self):
        self.engine.client = None
        self.engine.gemini_client = None

        self.assertIn("JARVIS_GEMINI_API_KEY", "".join(self.engine.stream([], "Merhaba")))

    def test_provider_errors_are_reported_with_actionable_messages(self):
        cases = (
            ("read timed out", "zamanında alınamadı"),
            ("Connection refused", "bağlanılamadı"),
            ("HTTP 429 rate limit", "istek sınırına ulaşıldı"),
            ("API key unauthorized", "kimlik doğrulamasını reddetti"),
        )
        for raw_error, expected in cases:
            with self.subTest(raw_error=raw_error):
                self.assertIn(expected, jarvis_v11._friendly_ai_error(RuntimeError(raw_error)))

    def test_cancelled_provider_stream_does_not_fall_back_to_gemini(self):
        class _ClosableStream:
            def __init__(self):
                self.closed = False

            def __iter__(self):
                return self

            def __next__(self):
                if self.closed:
                    raise RuntimeError("stream closed")
                return _content_chunk("partial")

            def close(self):
                self.closed = True

        response = _ClosableStream()
        cancel_event = mock.Mock()
        cancel_event.is_set.side_effect = [False, False, False, True]
        register = mock.Mock()
        self.engine.client.chat.completions.create.return_value = response

        output = list(self.engine.stream(
            [], "Merhaba", cancel_event=cancel_event, stream_callback=register
        ))

        self.assertEqual(output, ["partial"])
        self.engine.gemini_client.chat.completions.create.assert_not_called()
        self.assertTrue(response.closed)
        self.assertEqual(register.call_args_list, [mock.call(response), mock.call(None)])


if __name__ == "__main__":
    unittest.main()
