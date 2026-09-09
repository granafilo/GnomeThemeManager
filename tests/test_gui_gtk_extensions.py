# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GNOME Extensions GUI view and page (Task 5.3)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from gnome_theme_manager.core.extension_backend import (
    ExtensionItem,
    ExtensionSearchResult,
)
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
    manager.extensions.open_extension_manager.return_value = True
    manager.extensions.is_extension_manager_installed.return_value = True
    manager.extensions.is_gnome_extensions_installed.return_value = True
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
    mock_manager.extensions.open_extension_manager.assert_called_once()

    # Test removing user extension
    mock_manager.extensions.uninstall_extension.return_value = True
    with patch.object(page, "refresh") as mock_refresh:
        page._on_remove_extension(ext)
        mock_manager.extensions.uninstall_extension.assert_called_with(
            "dash-to-dock@micxgx.gmail.com"
        )
        mock_refresh.assert_called_once()

    # Test _open_app failure displaying OS-tailored install command and copying to clipboard
    mock_manager.extensions.open_extension_manager.return_value = False
    mock_manager.extensions.is_extension_manager_installed.return_value = False
    mock_manager.get_install_command.return_value = "sudo dnf install -y extension-manager"
    notify_mock = MagicMock()
    page.on_notify_message = notify_mock
    page._open_app()
    notify_mock.assert_called_once()
    msg, is_err = notify_mock.call_args[0]
    assert "sudo dnf install -y extension-manager" in msg
    assert is_err is False
    assert page.btn_open_app.get_label() in (
        "Install Extension Manager",
        "Installa Extension Manager",
    )
    assert page.install_banner.get_revealed() is True
    assert page.expander_install_options.get_expanded() is True


def test_extensions_page_install_options_select(mock_manager: MagicMock) -> None:
    """Test switching installation options in combo row updates command and copies correctly."""
    mock_manager.get_extension_manager_install_options.return_value = [
        {
            "id": "system",
            "name": "System Package (APT)",
            "command": "sudo apt install -y gnome-extensions-app",
            "description": "Recommended native package provided by distribution repositories.",
        },
        {
            "id": "flatpak",
            "name": "Flatpak (Flathub)",
            "command": "flatpak install flathub com.mattjakeman.ExtensionManager",
            "description": "Modern Extension Manager in isolated sandbox from Flathub.",
        },
    ]
    mock_manager.extensions.is_extensions_app_installed.return_value = False
    mock_manager.extensions.is_extension_manager_installed.return_value = False

    page = ExtensionsPage(manager=mock_manager)

    assert page.combo_install_method is not None
    assert page.row_install_command is not None
    assert page.expander_install_options is not None

    # First option selected by default (System Package)
    assert page.combo_install_method.get_selected() == 0
    assert page.row_install_command.get_subtitle() == "sudo apt install -y gnome-extensions-app"

    # Switch to second option (Flatpak)
    page.combo_install_method.set_selected(1)
    page._on_install_method_changed()
    assert (
        page.row_install_command.get_subtitle()
        == "flatpak install flathub com.mattjakeman.ExtensionManager"
    )

    # Test copy button with Flatpak option selected
    notify_mock = MagicMock()
    page.on_notify_message = notify_mock
    page._on_copy_install_command()
    notify_mock.assert_called_once()
    msg, is_err = notify_mock.call_args[0]
    assert "flatpak install flathub com.mattjakeman.ExtensionManager" in msg
    assert is_err is False


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


def test_extensions_page_filter_modes(mock_manager: MagicMock) -> None:
    """Test switching filter modes between installed, available, and updatable."""
    page = ExtensionsPage(manager=mock_manager)
    assert page._filter_mode == "installed"
    assert page.user_extensions_group.get_visible() is True
    assert page.sort_dropdown.get_visible() is False

    # Switch to Available (index 1)
    assert page.filter_dropdown is not None
    page.filter_dropdown.set_selected(1)
    page._on_filter_changed()
    assert page._filter_mode == "available"
    assert page.user_extensions_group.get_visible() is False
    assert page.remote_extensions_group is not None
    assert page.remote_extensions_group.get_visible() is True
    assert page.sort_dropdown.get_visible() is True

    # Switch to Updatable (index 2)
    page.filter_dropdown.set_selected(2)
    page._on_filter_changed()
    assert page._filter_mode == "updatable"
    assert page.user_extensions_group.get_visible() is False
    assert page.remote_extensions_group.get_visible() is True
    assert page.sort_dropdown.get_visible() is False

    # Switch back to Installed (index 0)
    page.filter_dropdown.set_selected(0)
    page._on_filter_changed()
    assert page._filter_mode == "installed"
    assert page.user_extensions_group.get_visible() is True
    assert page.remote_extensions_group.get_visible() is False
    assert page.sort_dropdown.get_visible() is False


def test_extension_manager_install_option_hidden_when_installed(mock_manager: MagicMock) -> None:
    """Test that installation options group is hidden when Extension Manager is installed."""
    mock_manager.extensions.is_extension_manager_installed.return_value = True
    page = ExtensionsPage(manager=mock_manager)
    assert page.group_install_manager is not None
    assert page.group_install_manager.get_visible() is False
    assert page.install_banner is not None
    assert page.install_banner.get_revealed() is False


def test_extension_manager_install_option_shown_when_not_installed(mock_manager: MagicMock) -> None:
    """Test that installation options group is shown when Extension Manager is not installed."""
    mock_manager.extensions.is_extension_manager_installed.return_value = False
    mock_manager.extensions.is_extensions_app_installed.return_value = False
    page = ExtensionsPage(manager=mock_manager)
    assert page.group_install_manager is not None
    assert page.group_install_manager.get_visible() is True
    assert page.install_banner is not None
    assert page.install_banner.get_revealed() is True


def test_extensions_page_remote_search_and_lazy_loading(mock_manager: MagicMock) -> None:
    """Test catalog search results rendering and lazy loading pagination."""
    item1 = ExtensionItem(
        uuid="blur-my-shell@aunetx",
        name="Blur my Shell",
        description="Adds blur effect to various GNOME Shell elements.",
        creator="aunetx",
        downloads=54000,
        rating=4.9,
        version="60",
        is_compatible=True,
    )
    item2 = ExtensionItem(
        uuid="incompatible@ext.org",
        name="Old Extension",
        description="Incompatible extension.",
        downloads=120,
        is_compatible=False,
    )

    result_p1 = ExtensionSearchResult(
        extensions=[item1],
        total=2,
        page=1,
        numpages=2,
    )
    result_p2 = ExtensionSearchResult(
        extensions=[item2],
        total=2,
        page=2,
        numpages=2,
    )

    mock_manager.extension_backend.search.side_effect = [result_p1, result_p2]

    page = ExtensionsPage(manager=mock_manager)
    # Simulate page 1 search response
    page._on_remote_search_success(result_p1, reset_page=True)

    assert len(page._remote_items) == 1
    assert page._current_page == 1
    assert page._numpages == 2
    assert page.status_stack.get_visible_child_name() == "content"
    assert len(page._remote_row_widgets) == 1
    assert page.lazy_load_box is not None
    assert page.lazy_load_box.get_visible() is True
    assert page.btn_load_more is not None
    assert page.btn_load_more.get_visible() is True

    # Simulate lazy loading page 2
    page._filter_mode = "available"
    page._on_remote_search_success(result_p2, reset_page=False)

    assert len(page._remote_items) == 2
    assert page._current_page == 2
    assert len(page._remote_row_widgets) == 2
    # No more pages after page 2
    assert page.btn_load_more.get_visible() is False


def test_extensions_page_updatable_check(mock_manager: MagicMock) -> None:
    """Test updatable check populating updatable extensions list."""
    updatable_item = ExtensionItem(
        uuid="dash-to-dock@micxgx.gmail.com",
        name="Dash to Dock",
        description="Dock for GNOME Shell.",
        version="92",
        installed_version="90",
        is_installed=True,
        is_enabled=True,
        has_update=True,
        is_compatible=True,
    )

    mock_manager.extension_backend.check_updates.return_value = [updatable_item]

    page = ExtensionsPage(manager=mock_manager)
    page._on_updatable_loaded([updatable_item])

    assert len(page._remote_items) == 1
    assert page.status_stack.get_visible_child_name() == "content"
    assert len(page._remote_row_widgets) == 1

    # Empty updatable list
    page._on_updatable_loaded([])
    assert len(page._remote_items) == 0
    assert page.status_stack.get_visible_child_name() == "empty"


def test_extensions_page_remote_error_handling(mock_manager: MagicMock) -> None:
    """Test remote error handler switching to error page."""
    page = ExtensionsPage(manager=mock_manager)
    page._on_remote_search_error("Connection timed out")

    assert page.status_stack.get_visible_child_name() == "error"
    assert page.error_status_page is not None
    assert "Connection timed out" in page.error_status_page.get_description()


def test_extensions_page_open_url_normalization(mock_manager: MagicMock) -> None:
    """Test URL normalization in _open_url and _on_view_item_details."""
    page = ExtensionsPage(manager=mock_manager)

    with patch("gi.repository.Gio.AppInfo.launch_default_for_uri") as mock_launch:
        # Relative URL
        page._open_url("/extension/615/appindicator-support/")
        mock_launch.assert_called_with(
            "https://extensions.gnome.org/extension/615/appindicator-support/", None
        )

        # Protocol-less URL
        page._open_url("extensions.gnome.org/test/")
        mock_launch.assert_called_with("https://extensions.gnome.org/test/", None)

        # Full URL
        page._open_url("https://example.com/ext")
        mock_launch.assert_called_with("https://example.com/ext", None)

        # Empty URL (no-op)
        mock_launch.reset_mock()
        page._open_url("")
        mock_launch.assert_not_called()

        # Item click fallback
        item = ExtensionItem(
            uuid="test@example.com",
            name="Test",
            description="",
            link="/extension/615/test/",
        )
        page._on_view_item_details(item)
        mock_launch.assert_called_with("https://extensions.gnome.org/extension/615/test/", None)
