# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GNOME Extensions GUI view and page (Task 5.3)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from gnome_theme_manager.core.extensions import GnomeExtension
from gnome_theme_manager.gui_gtk.pages.extensions import ExtensionsPage


@pytest.fixture
def sample_extensions() -> list[GnomeExtension]:
    return [
        GnomeExtension(
            uuid="user-theme@gnome-shell-extensions.gcampax.github.com",
            name="User Themes",
            description="Load shell themes from user directory.",
            enabled=True,
            state="ACTIVE",
            version="46",
            url="https://gitlab.gnome.org/GNOME/gnome-shell-extensions",
            is_user_level=True,
        ),
        GnomeExtension(
            uuid="dash-to-dock@micxgx.gmail.com",
            name="Dash to Dock",
            description="A dock for the Gnome Shell.",
            enabled=False,
            state="INITIALIZED",
            version="90",
            url="https://micheleg.github.io/dash-to-dock/",
            is_user_level=True,
            has_prefs=True,
        ),
        GnomeExtension(
            uuid="ubuntu-dock@ubuntu.com",
            name="Ubuntu Dock",
            description="Ubuntu default dock.",
            enabled=False,
            state="INITIALIZED",
            version="85",
            url="https://github.com/ubuntu/gnome-shell-extension-ubuntu-dock",
            is_user_level=False,
        ),
    ]


@pytest.fixture
def mock_manager(sample_extensions: list[GnomeExtension]) -> MagicMock:
    manager = MagicMock()
    manager.extensions = MagicMock()
    manager.extensions.list_extensions.return_value = sample_extensions
    manager.extensions.toggle_extension.return_value = True
    manager.extensions.enable_extension.return_value = True
    manager.extensions.disable_extension.return_value = True
    manager.extensions.open_prefs.return_value = True
    manager.extensions.open_extensions_app.return_value = True
    manager.extensions.get_store_url.side_effect = lambda uuid: (
        f"https://extensions.gnome.org/extension/{uuid}/"
    )
    return manager


def test_extensions_page_initialization(
    mock_manager: MagicMock, sample_extensions: list[GnomeExtension]
) -> None:
    """Test ExtensionsPage widget structure and initial population."""
    page = ExtensionsPage(manager=mock_manager)
    assert page.page_id == "extensions"
    assert "Extensions" in page.title or "Estensioni" in page.title
    assert isinstance(page.get_widget(), Gtk.Widget)

    # Simulate extensions loading completion
    page._on_extensions_loaded(sample_extensions)
    assert len(page._extensions) == 3
    assert page.widget.get_visible_child_name() == "ready"
    assert page.status_stack.get_visible_child_name() == "content"
    assert page.user_extensions_group.get_visible() is True
    assert page.system_extensions_group.get_visible() is True


def test_extensions_page_search_filter(
    mock_manager: MagicMock, sample_extensions: list[GnomeExtension]
) -> None:
    """Test searching/filtering extensions list."""
    page = ExtensionsPage(manager=mock_manager)
    page._on_extensions_loaded(sample_extensions)

    # Search for "dock"
    page.search_entry.set_text("dock")
    page._filter_extensions("dock")
    assert len(page._filtered_extensions) == 2

    # Search for non-matching query
    page.search_entry.set_text("nonexistent_extension")
    page._filter_extensions("nonexistent_extension")
    assert len(page._filtered_extensions) == 0
    assert page.status_stack.get_visible_child_name() == "empty"


def test_extensions_page_toggle_extension(
    mock_manager: MagicMock, sample_extensions: list[GnomeExtension]
) -> None:
    """Test toggling extension enable switch and opening preferences."""
    page = ExtensionsPage(manager=mock_manager)
    page._on_extensions_loaded(sample_extensions)

    ext = page._extensions[1]  # dash-to-dock (currently disabled)
    page._on_extension_switch_toggled(ext, True)

    mock_manager.extensions.toggle_extension.assert_called_with(
        "dash-to-dock@micxgx.gmail.com", True
    )

    # Test opening prefs
    page._open_prefs(ext.uuid)
    mock_manager.extensions.open_prefs.assert_called_with("dash-to-dock@micxgx.gmail.com")

    # Test opening app
    page._open_app()
    mock_manager.extensions.open_extensions_app.assert_called_once()

    # Test removing user extension
    mock_manager.extensions.uninstall_extension.return_value = True
    with patch.object(page, "refresh") as mock_refresh:
        page._on_remove_extension(ext)
        mock_manager.extensions.uninstall_extension.assert_called_with(
            "dash-to-dock@micxgx.gmail.com"
        )
        mock_refresh.assert_called_once()


class TestMainWindowExtensionsIntegration:
    """Test MainWindow integration and sidebar selection of ExtensionsPage."""

    def test_main_window_has_extensions_page(self) -> None:
        from gi.repository import Gio

        from gnome_theme_manager.core.manager import ThemeManager
        from gnome_theme_manager.core.models import ThemeSet
        from gnome_theme_manager.gui_gtk.window import MainWindow

        app = Adw.Application(
            application_id=None,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        mock_mgr = MagicMock(spec=ThemeManager)
        mock_mgr.installer.ensure_user_directories.return_value = []
        mock_mgr.get_system_status.return_value.user_themes_path = Path(
            "/home/user/.local/share/themes"
        )
        mock_mgr.get_system_status.return_value.user_icons_path = Path(
            "/home/user/.local/share/icons"
        )
        mock_mgr.get_system_status.return_value.sandbox_status = None
        mock_mgr.get_system_status.return_value.gtk4_override_active = False
        mock_mgr.get_system_status.return_value.gtk4_override_status = None
        mock_mgr.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
        mock_mgr.store_client.search.return_value = []
        mock_mgr.extensions.list_extensions.return_value = []

        window = MainWindow(app=app, manager=mock_mgr)
        assert "extensions" in window.pages
        assert isinstance(window.pages["extensions"], ExtensionsPage)
        assert window.row_extensions is not None

        # Select extensions page
        window.select_page("extensions")
        assert window.content_stack.get_visible_child_name() == "extensions"
