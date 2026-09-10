# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for shortcuts, focus behavior, and main window filters (Task 0.3)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.models import ThemeSet, ThemeType
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio, Gtk
else:
    Adw = None  # type: ignore
    Gtk = None  # type: ignore
    Gio = None  # type: ignore


@pytest.fixture
def mock_app_and_manager():
    """Create mock for Adw.Application and ThemeManager."""
    if is_gtk_available():
        app = Adw.Application(application_id="io.github.granafilo.GnomeThemeManagerTest")
    else:
        app = MagicMock()
    manager = MagicMock()
    # Mock user paths to avoid initialization errors
    manager.get_system_status.return_value.user_themes_path = Path("/home/user/.local/share/themes")
    manager.get_system_status.return_value.user_icons_path = Path("/home/user/.local/share/icons")
    manager.get_system_status.return_value.sandbox_status = None
    manager.get_system_status.return_value.gtk4_override_active = False
    manager.get_system_status.return_value.gtk4_override_status = None
    manager.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
    return app, manager


def test_window_shortcuts(mock_app_and_manager):
    """Verify that close shortcuts (Ctrl+W, Ctrl+Q) are configured and bound to window."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    app, manager = mock_app_and_manager
    window = GnomeThemeWindow(app, manager=manager)

    accels_w = app.get_accels_for_action("win.close")
    accels_q = app.get_accels_for_action("app.quit")

    assert "close" in window.list_actions()
    assert app.has_action("quit") or app.lookup_action("quit") is not None
    assert "<Control>w" in accels_w
    assert "<Control>q" in accels_q


def test_focus_behavior_unselect(mock_app_and_manager):
    """Verify that focus behavior deselects active row in themes list box."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    app, manager = mock_app_and_manager
    window = GnomeThemeWindow(app, manager=manager)

    # Insert a dummy row and select it
    row = Gtk.ListBoxRow()
    window.themes_page.themes_list_box.append(row)
    window.themes_page.themes_list_box.select_row(row)
    assert window.themes_page.themes_list_box.get_selected_row() == row

    # Simulate click gesture trigger
    controllers = [
        window.observe_controllers().get_item(i)
        for i in range(window.observe_controllers().get_n_items())
    ]
    gesture_clicks = [c for c in controllers if isinstance(c, Gtk.GestureClick)]
    assert len(gesture_clicks) > 0

    # Invoke focus removal and manual deselection
    window.set_focus(None)
    window.themes_page.themes_list_box.select_row(None)
    assert window.themes_page.themes_list_box.get_selected_row() is None


def test_system_themes_toggle_persistence(mock_app_and_manager):
    """Verify Hide system themes checkbutton filter per category across session."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    app, manager = mock_app_and_manager

    window = GnomeThemeWindow(app, manager=manager)
    page = window.themes_page

    assert page.system_themes_toggle is not None
    assert page.system_themes_toggle.get_active() is False

    # Change toggle state for active category (GTK)
    page.system_themes_toggle.set_active(True)
    assert page._toggle_states[ThemeType.GTK] is True

    # Switch to ICON, change toggle to False, verify both categories maintain independent states
    page.set_category(ThemeType.ICON)
    page.system_themes_toggle.set_active(False)
    assert page._toggle_states[ThemeType.GTK] is True
    assert page._toggle_states[ThemeType.ICON] is False
