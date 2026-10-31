import unittest
from types import SimpleNamespace
from unittest import mock

from config import APP_VERSION
from services.update_check import check_for_update, is_update_check_configured


class UpdateCheckTests(unittest.TestCase):
    def test_update_source_must_be_configured_and_https(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "ayarlı değil"):
                check_for_update()
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            check_for_update("http://example.com/releases/latest")

    def test_valid_manifest_reports_newer_version_without_downloading_artifacts(self):
        response = mock.Mock()
        response.json.return_value = {
            "tag_name": "v1.3.0",
            "html_url": "https://example.com/releases/v1.3.0",
            "body": "Bug fixes",
            "assets": [{"browser_download_url": "https://example.com/app.exe"}],
        }
        with mock.patch(
            "services.update_check.HTTP_SESSION.get", return_value=response
        ) as request:
            info = check_for_update(
                "https://example.com/api/releases/latest", "1.2.0"
            )

        self.assertTrue(info.update_available)
        self.assertEqual(info.latest_version, "v1.3.0")
        self.assertEqual(info.release_notes, "Bug fixes")
        request.assert_called_once()
        response.raise_for_status.assert_called_once()

    def test_unknown_current_version_and_invalid_release_link_are_handled(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "tag_name": "2.0",
                "html_url": "javascript:alert(1)",
            },
        )
        with mock.patch(
            "services.update_check.HTTP_SESSION.get", return_value=response
        ):
            with self.assertRaisesRegex(ValueError, "HTTPS URL"):
                check_for_update(
                    "https://example.com/api/releases/latest", "not-semver"
                )


    def test_is_update_check_configured_reflects_environment(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(is_update_check_configured())
        with mock.patch.dict(
            "os.environ",
            {"JARVIS_UPDATE_URL": "https://example.com/api/releases/latest"},
            clear=True,
        ):
            self.assertTrue(is_update_check_configured())

    def test_app_version_used_when_jarvis_version_env_missing(self):
        """JARVIS_VERSION yoksa paket sürümü (APP_VERSION) karşılaştırılır."""

        def _response(tag):
            response = mock.Mock()
            response.json.return_value = {
                "tag_name": tag,
                "html_url": f"https://example.com/releases/{tag}",
            }
            return response

        # Etiketler gerçek APP_VERSION'dan türetilir; sürüm yükseltildiğinde
        # testin elle güncellenmesi gerekmez.
        major, minor, patch = (int(part) for part in APP_VERSION.split(".")[:3])
        current_tag = f"v{major}.{minor}.{patch}"
        newer_tag = f"v{major}.{minor}.{patch + 1}"

        with mock.patch.dict(
            "os.environ",
            {"JARVIS_UPDATE_URL": "https://example.com/api/releases/latest"},
            clear=True,
        ), mock.patch(
            "services.update_check.HTTP_SESSION.get"
        ) as request:
            request.return_value = _response(newer_tag)
            self.assertTrue(check_for_update().update_available)

            request.return_value = _response(current_tag)
            self.assertFalse(check_for_update().update_available)


if __name__ == "__main__":
    unittest.main()
