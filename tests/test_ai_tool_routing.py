import json
import unittest
from types import SimpleNamespace
from unittest import mock

import jarvis_v11


class AIToolRoutingTests(unittest.TestCase):
    def setUp(self):
        self.engine = object.__new__(jarvis_v11.AIEngine)
        self.engine.client = mock.Mock()
        self.engine.client.chat.completions.create.return_value = iter(())

    def _stream(self, prompt):
        with mock.patch.object(jarvis_v11, "build_persona", return_value="persona"), \
             mock.patch.object(jarvis_v11, "REMOTE_CONTEXT_ENABLED", False):
            return list(self.engine.stream([], prompt))

    def test_conversation_does_not_offer_desktop_tools_to_model(self):
        self._stream("espri yap")

        options = self.engine.client.chat.completions.create.call_args.kwargs
        self.assertNotIn("tools", options)
        self.assertNotIn("tool_choice", options)

    def test_explicit_computer_command_offers_desktop_tools(self):
        self._stream("Chrome'u aç")

        options = self.engine.client.chat.completions.create.call_args.kwargs
        self.assertEqual(options["tool_choice"], "auto")
        self.assertEqual(
            {tool["function"]["name"] for tool in options["tools"]},
            {"search_on_site", "open_url"},
        )

    def test_unrequested_tool_call_does_not_open_atlas_or_start_automation(self):
        window = SimpleNamespace(
            history=[{"role": "user", "content": "espri yap"}],
            atlas_enabled=False,
            _add_response=mock.Mock(),
            _toggle_atlas=mock.Mock(),
            _automation=mock.Mock(),
        )

        jarvis_v11.JarvisWindow._on_tool_call(
            window,
            json.dumps({
                "name": "open_url",
                "arguments": {"url": "https://example.com"},
            }),
        )

        window._toggle_atlas.assert_not_called()
        window._automation.open_url.assert_not_called()
        window._add_response.assert_called_once()

    def test_computer_tool_call_does_not_bypass_disabled_atlas(self):
        window = SimpleNamespace(
            history=[{"role": "user", "content": "Chrome'u aç"}],
            atlas_enabled=False,
            _add_response=mock.Mock(),
            _toggle_atlas=mock.Mock(),
            _automation=mock.Mock(),
        )

        jarvis_v11.JarvisWindow._on_tool_call(
            window,
            json.dumps({
                "name": "open_url",
                "arguments": {"url": "https://example.com"},
            }),
        )

        window._toggle_atlas.assert_not_called()
        window._automation.open_url.assert_not_called()
        window._add_response.assert_called_once()


if __name__ == "__main__":
    unittest.main()
