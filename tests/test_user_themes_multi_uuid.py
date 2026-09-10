# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Multi-UUID User Themes extension detection."""

import unittest
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.extensions import USER_THEMES_IDS, ExtensionsManager


class TestUserThemesMultiUuid(unittest.TestCase):
    """Test suite for robust Multi-UUID detection of GNOME User Themes extension."""

    def setUp(self) -> None:
        self.manager = ExtensionsManager()

    def test_user_themes_ids_contains_expected_uuids(self) -> None:
        """Verify fallback chain contains vanilla, Debian, short-name and Zorin IDs."""
        self.assertIn("user-theme@gnome-shell-extensions.gcampax.github.com", USER_THEMES_IDS)
        self.assertIn("user-theme@gnome-shell-extensions", USER_THEMES_IDS)
        self.assertIn("user-theme", USER_THEMES_IDS)
        self.assertIn("user-theme@zorin.com", USER_THEMES_IDS)
        self.assertIn("zorin-appearance@zorin.com", USER_THEMES_IDS)
        self.assertIn("zorin-appearance@zorinos.com", USER_THEMES_IDS)

    def test_is_user_theme_enabled_with_each_known_uuid(self) -> None:
        """Verify is_user_theme_enabled returns True for every supported UUID."""
        for uuid in USER_THEMES_IDS:
            with patch.object(self.manager, "get_enabled_uuids", return_value={uuid}):
                self.assertTrue(
                    self.manager.is_user_theme_enabled(),
                    f"Failed to detect User Themes with UUID: {uuid}",
                )

    def test_is_user_theme_enabled_negative_case(self) -> None:
        """Verify is_user_theme_enabled returns False when extension is disabled."""
        with (
            patch.object(
                self.manager, "get_enabled_uuids", return_value={"dash-to-dock@micxgx.gmail.com"}
            ),
            patch.object(self.manager, "list_extensions", return_value=[]),
            patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
            patch("shutil.which", return_value=None),
        ):
            self.assertFalse(self.manager.is_user_theme_enabled())

    def test_is_user_theme_enabled_via_fuzzy_name(self) -> None:
        """Verify fuzzy detection by extension display name or UUID substring."""
        mock_ext = MagicMock()
        mock_ext.enabled = True
        mock_ext.uuid = "custom-user-theme-fork@distro.org"
        mock_ext.name = "Custom User Theme Helper"

        with (
            patch.object(self.manager, "get_enabled_uuids", return_value=set()),
            patch.object(self.manager, "list_extensions", return_value=[mock_ext]),
        ):
            self.assertTrue(self.manager.is_user_theme_enabled())

    def test_is_user_theme_enabled_via_dconf_fallback(self) -> None:
        """Verify dconf fallback detection when shell theme value is present."""
        with (
            patch.object(self.manager, "get_enabled_uuids", return_value=set()),
            patch.object(self.manager, "list_extensions", return_value=[]),
            patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
            patch("shutil.which", return_value="/usr/bin/dconf"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="'ZorinDesert-Light'\n")
            self.assertTrue(self.manager.is_user_theme_enabled())


if __name__ == "__main__":
    unittest.main()
