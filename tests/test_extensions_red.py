# SPDX-License-Identifier: GPL-3.0-or-later

"""Test per la gestione dell'estensione GNOME Shell user-theme (RED phase)."""

from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.extensions import ExtensionsManager


def test_extensions_manager_user_theme_status() -> None:
    """Verifica il rilevamento dello stato dell'estensione user-theme."""
    with patch("subprocess.run") as mock_run:
        # Configura mock_run per restituire estensione abilitata
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="user-theme@gnome-shell-extensions.gcampax.github.com\n",
        )

        manager = ExtensionsManager()
        assert manager.is_user_theme_enabled() is True

        # Configura mock_run per restituire estensione disabilitata (non nella lista di quelle abilitate)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="other-extension@gnome-shell-extensions.gcampax.github.com\n",
        )
        assert manager.is_user_theme_enabled() is False


def test_extensions_manager_enable_user_theme() -> None:
    """Verifica l'abilitazione dell'estensione user-theme."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        manager = ExtensionsManager()
        assert manager.enable_user_theme() is True
        mock_run.assert_called_with(
            ["gnome-extensions", "enable", "user-theme@gnome-shell-extensions.gcampax.github.com"],
            capture_output=True,
            text=True,
            check=False,
        )
