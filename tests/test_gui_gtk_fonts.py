# SPDX-License-Identifier: GPL-3.0-or-later

"""GUI integration tests for Fonts page (Task 4.3)."""

from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.errors import GSettingsUnavailableError
from gnome_theme_manager.core.fonts import FontConfig
from gnome_theme_manager.gui_gtk import is_gtk_available


def test_fonts_page_instantiation_and_load(mock_theme_manager: MagicMock) -> None:
    """Verify FontsPage controller instantiates and loads current font values into buttons."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.fonts import FontsPage

    active_fonts = FontConfig(
        interface_font="Ubuntu 11",
        document_font="Ubuntu Sans 11",
        monospace_font="Ubuntu Mono 13",
        text_scaling_factor=1.2,
    )
    mock_theme_manager.get_current_fonts.return_value = active_fonts

    page = FontsPage(manager=mock_theme_manager)
    page.refresh()

    assert page.get_widget() is not None
    assert page.interface_font_btn.get_font_desc() is not None
    assert "Ubuntu" in page.interface_font_btn.get_font_desc().to_string()
    assert "Ubuntu Sans" in page.document_font_btn.get_font_desc().to_string()
    assert "Ubuntu Mono" in page.monospace_font_btn.get_font_desc().to_string()
    assert abs(page.scale_spin.get_value() - 1.2) < 0.01


def test_fonts_page_apply_fonts_success(mock_theme_manager: MagicMock) -> None:
    """Verify clicking Apply button reads form and invokes manager.apply_fonts."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gi.repository import Pango

    from gnome_theme_manager.gui_gtk.pages.fonts import FontsPage

    mock_theme_manager.get_current_fonts.return_value = FontConfig()
    mock_theme_manager.apply_fonts.return_value = True

    page = FontsPage(manager=mock_theme_manager)
    page.refresh()

    page.interface_font_btn.set_font_desc(Pango.FontDescription.from_string("Cantarell 12"))
    page.document_font_btn.set_font_desc(Pango.FontDescription.from_string("Sans 12"))
    page.monospace_font_btn.set_font_desc(Pango.FontDescription.from_string("Monospace 13"))
    page.scale_spin.set_value(1.25)

    notifications = []
    page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

    page.on_apply_button_clicked(page.apply_button)

    assert mock_theme_manager.apply_fonts.called
    called_fonts = mock_theme_manager.apply_fonts.call_args[0][0]
    assert called_fonts.interface_font == "Cantarell 12"
    assert called_fonts.document_font == "Sans 12"
    assert called_fonts.monospace_font == "Monospace 13"
    assert abs(called_fonts.text_scaling_factor - 1.25) < 0.01
    assert len(notifications) == 1
    assert notifications[0][1] is False  # not an error


def test_fonts_page_gsettings_unavailable_shows_error(mock_theme_manager: MagicMock) -> None:
    """Verify FontsPage shows error state when GSettings is unavailable."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.fonts import FontsPage

    mock_theme_manager.get_current_fonts.side_effect = GSettingsUnavailableError(
        "GSettings schema missing"
    )

    page = FontsPage(manager=mock_theme_manager)
    page.refresh()

    assert page.widget.get_visible_child() == page.error_view
    assert "unavailable" in page.error_label.get_text().lower()


def test_fonts_page_reset_button_reloads_values(mock_theme_manager: MagicMock) -> None:
    """Verify Reset button discards modified values and reloads from system."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gi.repository import Pango

    from gnome_theme_manager.gui_gtk.pages.fonts import FontsPage

    mock_theme_manager.get_current_fonts.return_value = FontConfig(interface_font="Cantarell 11")

    page = FontsPage(manager=mock_theme_manager)
    page.refresh()
    assert page.interface_font_btn.get_font_desc().to_string() == "Cantarell 11"

    page.interface_font_btn.set_font_desc(Pango.FontDescription.from_string("Fira Code 14"))
    assert page.interface_font_btn.get_font_desc().to_string() == "Fira Code 14"

    page.on_reset_button_clicked(page.reset_button)
    assert page.interface_font_btn.get_font_desc().to_string() == "Cantarell 11"
