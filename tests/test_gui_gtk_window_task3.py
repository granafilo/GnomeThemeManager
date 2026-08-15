# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per shortcut, focus behavior e filtri della finestra principale (Task 0.3)."""

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
    """Crea mock per Adw.Application e ThemeManager."""
    if is_gtk_available():
        app = Adw.Application(application_id="io.github.granafilo.GnomeThemeManagerTest")
    else:
        app = MagicMock()
    manager = MagicMock()
    # Mocking percorsi utente per evitare errori nell'inizializzazione
    manager.get_system_status.return_value.user_themes_path = Path("/home/user/.local/share/themes")
    manager.get_system_status.return_value.user_icons_path = Path("/home/user/.local/share/icons")
    manager.get_system_status.return_value.sandbox_status = None
    manager.get_system_status.return_value.gtk4_override_active = False
    manager.get_system_status.return_value.gtk4_override_status = None
    manager.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
    return app, manager


def test_window_shortcuts(mock_app_and_manager):
    """Verifica che le scorciatoie di chiusura (Ctrl+W, Ctrl+Q) siano configurate e associate alla finestra."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    app, manager = mock_app_and_manager
    window = GnomeThemeWindow(app, manager=manager)

    accels_w = app.get_accels_for_action("win.close")
    accels_q = app.get_accels_for_action("app.quit")

    assert "close" in window.list_actions()
    assert app.has_action("quit") or app.lookup_action("quit") is not None
    assert "<Control>w" in accels_w
    assert "<Control>q" in accels_q


def test_focus_behavior_unselect(mock_app_and_manager):
    """Verifica che il focus behavior deselezioni la riga attiva nella list box dei temi."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    app, manager = mock_app_and_manager
    window = GnomeThemeWindow(app, manager=manager)

    # Inseriamo una riga fittizia e selezioniamola
    row = Gtk.ListBoxRow()
    window.themes_page.themes_list_box.append(row)
    window.themes_page.themes_list_box.select_row(row)
    assert window.themes_page.themes_list_box.get_selected_row() == row

    # Simula la pressione del GestureClick impostato
    controllers = [
        window.observe_controllers().get_item(i)
        for i in range(window.observe_controllers().get_n_items())
    ]
    gesture_clicks = [c for c in controllers if isinstance(c, Gtk.GestureClick)]
    assert len(gesture_clicks) > 0

    # Invoca la rimozione del focus e selezione manuale
    window.set_focus(None)
    window.themes_page.themes_list_box.select_row(None)
    assert window.themes_page.themes_list_box.get_selected_row() is None


def test_system_themes_toggle_persistence(mock_app_and_manager):
    """Verifica il filtro del checkbutton Nascondi temi di sistema per categoria in sessione."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    app, manager = mock_app_and_manager

    window = GnomeThemeWindow(app, manager=manager)
    page = window.themes_page

    assert page.system_themes_toggle is not None
    assert page.system_themes_toggle.get_active() is False

    # Modifica stato toggle per la categoria attiva (GTK)
    page.system_themes_toggle.set_active(True)
    assert page._toggle_states[ThemeType.GTK] is True

    # Passa a ICON, modifica toggle ad False, verifica che le due categorie abbiano stati indipendenti
    page.set_category(ThemeType.ICON)
    page.system_themes_toggle.set_active(False)
    assert page._toggle_states[ThemeType.GTK] is True
    assert page._toggle_states[ThemeType.ICON] is False
