# SPDX-License-Identifier: GPL-3.0-or-later

"""GUI integration tests for Terminal Palette page (Task 4.4 - RED Phase)."""

from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.terminal_palette import TerminalPalette
from gnome_theme_manager.gui_gtk import is_gtk_available


def test_terminal_page_instantiation_and_load(mock_theme_manager: MagicMock) -> None:
    """Verify TerminalPage controller instantiates and loads derived palette."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.terminal import TerminalPage

    palette = TerminalPalette(
        name="Nord Derived",
        foreground_color="#D8DEE9",
        background_color="#2E3440",
    )
    mock_theme_manager.list_terminal_profiles.return_value = []
    mock_theme_manager.get_current_terminal_palette.return_value = None
    mock_theme_manager.get_derived_terminal_palette.return_value = palette

    page = TerminalPage(manager=mock_theme_manager)
    page.refresh()

    assert page.get_widget() is not None
    assert page.title is not None
    assert page.bg_picker.get_color_hex() == "#2E3440"
    assert page.fg_picker.get_color_hex() == "#D8DEE9"


def test_terminal_page_apply_palette(mock_theme_manager: MagicMock) -> None:
    """Verify clicking Apply button applies the palette via manager."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.terminal import TerminalPage

    palette = TerminalPalette(
        name="Nord Derived",
        foreground_color="#D8DEE9",
        background_color="#2E3440",
    )
    mock_theme_manager.list_terminal_profiles.return_value = []
    mock_theme_manager.get_derived_terminal_palette.return_value = palette
    mock_theme_manager.apply_terminal_palette.return_value = True

    page = TerminalPage(manager=mock_theme_manager)
    page.refresh()

    notifications = []
    page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

    page.on_apply_button_clicked(page.apply_button)

    assert mock_theme_manager.apply_terminal_palette.called
    assert len(notifications) == 1
    assert notifications[0][1] is False
