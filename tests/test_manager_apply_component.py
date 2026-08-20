# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per il Task 0.4 — Apply selettivo per componente (RED)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.errors import ThemeNotFoundError
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    Theme,
    ThemeType,
)


def test_manager_apply_component() -> None:
    """Verifica che apply_component applichi solo il componente e tema specifico."""
    mock_scanner = MagicMock()
    mock_gsettings = MagicMock()
    mock_gtk4_linker = MagicMock()
    mock_installer = MagicMock()
    mock_presets = MagicMock()
    mock_sandbox = MagicMock()
    mock_validator = MagicMock()
    mock_validator.validate.return_value = MagicMock(valid=True, warnings=[], missing_files=[])

    manager = ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        gtk4_linker=mock_gtk4_linker,
        installer=mock_installer,
        presets=mock_presets,
        sandbox_bridge=mock_sandbox,
        validator=mock_validator,
    )

    # Configura il mock dello scanner per trovare il tema
    mock_theme = Theme("Adwaita", ThemeType.GTK, Path("/usr/share/themes/Adwaita"), False)
    mock_scanner.find_theme.return_value = mock_theme

    # Eseguiamo l'applicazione del solo componente GTK
    result = manager.apply_component(ThemeType.GTK, "Adwaita")

    # Verifica che sia stato chiamato get_current_themes e apply_themes con il set parziale
    assert result.gtk_theme == "Adwaita"
    assert result.icon_theme is None
    assert result.cursor_theme is None
    assert result.shell_theme is None

    # Se proviamo ad applicare un tema inesistente
    mock_scanner.find_theme.return_value = None
    with pytest.raises(ThemeNotFoundError):
        manager.apply_component(ThemeType.GTK, "Inexistent")
