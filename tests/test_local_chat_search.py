import tempfile
import unittest
from pathlib import Path

import jarvis_v11
from services import database


class LocalChatSearchCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(Path(self.temp_dir.name) / "chat-search.db")
        database.db_init()
        self.session_id = database.db_new_session("Gezi planı")

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_command_searches_local_history_without_returning_search_command(self):
        database.db_save_msg(
            self.session_id, "user", "İstanbul için gezi planı hazırla"
        )
        command = "sohbet geçmişinde ara istanbul"
        database.db_save_msg(self.session_id, "user", command)

        response = jarvis_v11.JarvisWindow._run_local_memory_skill(
            None, command
        )

        self.assertIn("Yerel sohbet geçmişi sonuçları", response)
        self.assertIn("İstanbul için gezi planı hazırla", response)
        self.assertNotIn(command, response)

    def test_command_reports_when_local_history_has_no_match(self):
        response = jarvis_v11.JarvisWindow._run_local_memory_skill(
            None, "sohbet geçmişinde ara bulunmayan konu"
        )

        self.assertEqual(
            response,
            "Yerel sohbet geçmişinde eşleşme bulunamadı.",
        )


if __name__ == "__main__":
    unittest.main()
