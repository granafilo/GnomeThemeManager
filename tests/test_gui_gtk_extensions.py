# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GNOME Extensions GUI view and page (Task 5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from gnome_theme_manager.core.errors import ExtensionNetworkError
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
    """Test remote error handler switching to error page on server error."""
    page = ExtensionsPage(manager=mock_manager)
    page._on_remote_search_error("500 Internal Server Error")

    assert page.status_stack.get_visible_child_name() == "error"
    assert page.error_status_page is not None
    assert "500 Internal Server Error" in page.error_status_page.get_description()


def test_extensions_page_open_url_normalization(mock_manager: MagicMock) -> None:
    """Test URL normalization in _open_url and _on_detail_website_clicked."""
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

        # Detail website button click
        item = ExtensionItem(
            uuid="test@example.com",
            name="Test",
            description="",
            link="https://extensions.gnome.org/extension/615/test/",
        )
        page.show_details(item)
        page._on_detail_website_clicked()
        mock_launch.assert_called_with("https://extensions.gnome.org/extension/615/test/", None)


def test_extensions_page_show_details_and_back(mock_manager: MagicMock) -> None:
    """Test opening details view and returning to catalog."""
    page = ExtensionsPage(manager=mock_manager)

    item = ExtensionItem(
        uuid="dash-to-dock@micxgx.gmail.com",
        name="Dash to Dock",
        description="A dock for the GNOME Shell.",
        creator="michele_g",
        version="92",
        downloads=1250000,
        popularity=98,
        rating=4.7,
        is_installed=False,
        is_compatible=True,
    )

    page._on_view_item_details(item)

    assert page.view_stack is not None
    assert page.view_stack.get_visible_child_name() == "detail"
    assert page.detail_title_label is not None
    assert page.detail_title_label.get_text() == "Dash to Dock"
    assert page.detail_uuid_label is not None
    assert page.detail_uuid_label.get_text() == "dash-to-dock@micxgx.gmail.com"
    assert page.detail_creator_label is not None
    assert "michele_g" in page.detail_creator_label.get_text()
    assert page.detail_compat_banner is not None
    assert page.detail_compat_banner.get_revealed() is False
    assert page.btn_detail_install is not None
    assert page.btn_detail_install.get_visible() is True
    assert page.btn_detail_remove is not None
    assert page.btn_detail_remove.get_visible() is False

    # Return to catalog
    page.show_catalog()
    assert page.view_stack.get_visible_child_name() == "catalog"


def test_extensions_page_install_flow(mock_manager: MagicMock) -> None:
    """Test install flow: confirmation dialog -> backend install -> notification & UI update."""
    mock_manager.extension_backend.install.return_value = True
    page = ExtensionsPage(manager=mock_manager)
    notify_mock = MagicMock()
    page.on_notify_message = notify_mock

    item = ExtensionItem(
        uuid="appindicator@ubuntu.com",
        name="AppIndicator Support",
        description="Tray icons for GNOME.",
        is_installed=False,
        is_compatible=True,
    )
    page.show_details(item)

    # Click install with confirmation accepted
    with patch.object(
        page, "_show_confirmation_dialog", side_effect=lambda **kw: kw["on_confirm"]()
    ):
        page._on_detail_install_clicked()

    # Wait for worker thread to complete in GLib main context
    import time

    timeout = time.time() + 2.0
    while time.time() < timeout and not item.is_installed:
        GLib.MainContext.default().iteration(False)

    mock_manager.extension_backend.install.assert_called_with("appindicator@ubuntu.com")
    assert item.is_installed is True
    assert item.is_enabled is True
    assert page.btn_detail_install is not None
    assert page.btn_detail_install.get_visible() is False
    assert page.btn_detail_remove is not None
    assert page.btn_detail_remove.get_visible() is True
    assert notify_mock.called


def test_extensions_page_remove_flow(mock_manager: MagicMock) -> None:
    """Test uninstall flow: confirmation dialog -> manager uninstall -> notification & UI update."""
    mock_manager.extensions.uninstall_extension.return_value = True
    page = ExtensionsPage(manager=mock_manager)
    notify_mock = MagicMock()
    page.on_notify_message = notify_mock

    item = ExtensionItem(
        uuid="user-theme@gnome-shell-extensions.gcampax.github.com",
        name="User Themes",
        description="Load shell themes from user directory.",
        is_installed=True,
        is_enabled=True,
        is_compatible=True,
    )
    page.show_details(item)
    assert page.btn_detail_remove is not None
    assert page.btn_detail_remove.get_visible() is True

    # Click uninstall with confirmation accepted
    with patch.object(
        page, "_show_confirmation_dialog", side_effect=lambda **kw: kw["on_confirm"]()
    ):
        page._on_detail_remove_clicked()

    mock_manager.extensions.uninstall_extension.assert_called_with(item.uuid)
    assert item.is_installed is False
    assert page.btn_detail_install is not None
    assert page.btn_detail_install.get_visible() is True
    assert page.btn_detail_remove.get_visible() is False
    assert notify_mock.called


def test_extensions_page_detail_switch_and_prefs(mock_manager: MagicMock) -> None:
    """Test toggling extension switch and launching preferences from detail view."""
    mock_manager.extensions.toggle_extension.return_value = True
    mock_manager.extensions.open_prefs.return_value = True
    page = ExtensionsPage(manager=mock_manager)

    item = ExtensionItem(
        uuid="blur-my-shell@aunetx",
        name="Blur my Shell",
        description="",
        is_installed=True,
        is_enabled=True,
    )
    page.show_details(item)

    assert page.detail_switch_enable is not None
    # Toggle switch
    page._on_detail_switch_state_set(page.detail_switch_enable, False)
    mock_manager.extensions.toggle_extension.assert_called_with("blur-my-shell@aunetx", False)
    assert item.is_enabled is False

    # Settings button
    page._on_detail_prefs_clicked()
    mock_manager.extensions.open_prefs.assert_called_with("blur-my-shell@aunetx")


def test_extensions_page_multiple_screenshots_gallery(mock_manager: MagicMock) -> None:
    """Test gallery navigation, counter label, and thumbnails with multiple screenshots."""
    page = ExtensionsPage(manager=mock_manager)

    item = ExtensionItem(
        uuid="gallery-ext@example.com",
        name="Gallery Ext",
        description="Extension with multiple screenshots",
        screenshot_url="https://example.com/shot1.png",
        screenshots=[
            "https://example.com/shot1.png",
            "https://example.com/shot2.png",
            "https://example.com/shot3.png",
        ],
    )

    page.show_details(item)

    assert page.detail_screenshot_container is not None
    assert page.detail_screenshot_container.get_visible() is True

    # Multi-image controls should be visible
    assert page.btn_detail_prev_image is not None
    assert page.btn_detail_prev_image.get_visible() is True
    assert page.btn_detail_next_image is not None
    assert page.btn_detail_next_image.get_visible() is True
    assert page.detail_thumbnails_scrolled is not None
    assert page.detail_thumbnails_scrolled.get_visible() is True
    assert page.detail_image_counter_label is not None
    assert page.detail_image_counter_label.get_visible() is True
    assert "1" in page.detail_image_counter_label.get_text()
    assert "3" in page.detail_image_counter_label.get_text()

    # Verify thumbnails buttons created
    assert len(page._thumbnail_buttons) == 3

    # Navigate to next image
    page._navigate_image(1)
    assert page._detail_image_index == 1
    assert "2" in page.detail_image_counter_label.get_text()
    assert "suggested-action" in page._thumbnail_buttons[1].get_css_classes()
    assert "suggested-action" not in page._thumbnail_buttons[0].get_css_classes()

    # Navigate next again
    page._navigate_image(1)
    assert page._detail_image_index == 2
    assert "3" in page.detail_image_counter_label.get_text()

    # Wrap around to first image
    page._navigate_image(1)
    assert page._detail_image_index == 0

    # Wrap backwards to last image
    page._navigate_image(-1)
    assert page._detail_image_index == 2


def test_extensions_page_single_screenshot(mock_manager: MagicMock) -> None:
    """Test gallery with single or zero screenshots hides navigation controls."""
    page = ExtensionsPage(manager=mock_manager)

    # 1 screenshot
    single_item = ExtensionItem(
        uuid="single@example.com",
        name="Single Ext",
        screenshot_url="https://example.com/single.png",
        screenshots=["https://example.com/single.png"],
    )
    page.show_details(single_item)
    assert page.detail_screenshot_container is not None
    assert page.detail_screenshot_container.get_visible() is True
    assert page.btn_detail_prev_image is not None
    assert page.btn_detail_prev_image.get_visible() is False
    assert page.btn_detail_next_image is not None
    assert page.btn_detail_next_image.get_visible() is False
    assert page.detail_thumbnails_scrolled is not None
    assert page.detail_thumbnails_scrolled.get_visible() is False

    # 0 screenshots
    no_shot_item = ExtensionItem(
        uuid="none@example.com",
        name="No Shot Ext",
        screenshot_url=None,
        screenshots=[],
    )
    page.show_details(no_shot_item)
    assert page.detail_screenshot_container.get_visible() is False


def test_extensions_page_offline_state_and_recovery(mock_manager: MagicMock) -> None:
    """Test transitioning to offline status page on network error and recovering to installed."""
    page = ExtensionsPage(manager=mock_manager)

    # Trigger search error with network error
    err = ExtensionNetworkError("Temporary failure in name resolution")
    page._on_remote_search_error(str(err), is_offline=True)

    assert page.status_stack.get_visible_child_name() == "offline"
    assert page.offline_status_page is not None
    assert page.btn_offline_retry is not None
    assert page.btn_offline_switch_installed is not None

    # Clicking switch to installed switches filter mode back to installed
    page._switch_to_installed_filter()
    assert page._filter_mode == "installed"


def test_extensions_page_error_state(mock_manager: MagicMock) -> None:
    """Test transitioning to generic error page on non-network failure."""
    page = ExtensionsPage(manager=mock_manager)

    page._on_remote_search_error("Internal Server Error 500", is_offline=False)

    assert page.status_stack.get_visible_child_name() == "error"
    assert page.error_status_page is not None
    assert "Internal Server Error 500" in page.error_status_page.get_description()


def test_extensions_page_loading_callback(mock_manager: MagicMock) -> None:
    """Test on_loading_changed is fired during remote operations."""
    page = ExtensionsPage(manager=mock_manager)
    loading_states: list[bool] = []
    page.on_loading_changed = lambda state: loading_states.append(state)

    result = ExtensionSearchResult(extensions=[], total=0, numpages=1, page=1)
    page._on_remote_search_success(result, reset_page=True)

    assert False in loading_states


def test_extensions_page_detail_update_flow(mock_manager: MagicMock) -> None:
    """Test update flow: confirmation dialog -> manager install -> state update & notification."""
    mock_manager.extension_backend.install.return_value = True
    page = ExtensionsPage(manager=mock_manager)
    notify_mock = MagicMock()
    page.on_notify_message = notify_mock

    item = ExtensionItem(
        uuid="appindicator@ubuntu.com",
        name="AppIndicator Support",
        description="Tray icons for GNOME.",
        is_installed=True,
        is_enabled=True,
        has_update=True,
        version="58",
        installed_version="57",
    )

    page.show_details(item)
    assert page.btn_detail_update is not None
    assert page.btn_detail_update.get_visible() is True

    # Simulate clicking update with confirmation dialog accepted
    with patch.object(
        page, "_show_confirmation_dialog", side_effect=lambda **kw: kw["on_confirm"]()
    ):
        page._on_detail_update_clicked()

    import time

    timeout = time.time() + 2.0
    while time.time() < timeout and item.has_update:
        GLib.MainContext.default().iteration(False)

    mock_manager.extension_backend.install.assert_called_with("appindicator@ubuntu.com")
    assert item.has_update is False
    assert page.btn_detail_update.get_visible() is False
    assert notify_mock.called


def test_extensions_page_offline_cache_notification(mock_manager: MagicMock) -> None:
    """Test that displaying results from offline cache triggers an informative notification."""
    page = ExtensionsPage(manager=mock_manager)
    notifications: list[tuple[str, bool]] = []
    page.on_notify_message = lambda msg, is_err=False: notifications.append((msg, is_err))

    item = ExtensionItem(
        uuid="cached@example.com",
        name="Cached Item",
        description="Offline cached item",
    )
    result = ExtensionSearchResult(
        extensions=[item],
        total=1,
        numpages=1,
        page=1,
        from_cache=True,
    )
    page._on_remote_search_success(result, reset_page=True)

    assert len(notifications) == 1
    assert "Offline mode" in notifications[0][0] or "offline" in notifications[0][0].lower()
    assert notifications[0][1] is False


def test_extensions_page_install_failure_handling(mock_manager: MagicMock) -> None:
    """Test that installation failure displays an error notification and re-enables action buttons."""
    mock_manager.extension_backend.install.side_effect = RuntimeError("Disk full")
    page = ExtensionsPage(manager=mock_manager)
    notifications: list[tuple[str, bool]] = []
    page.on_notify_message = lambda msg, is_err=False: notifications.append((msg, is_err))

    item = ExtensionItem(
        uuid="fail@example.com",
        name="Failing Extension",
        description="",
        is_installed=False,
    )
    page.show_details(item)

    with patch.object(
        page, "_show_confirmation_dialog", side_effect=lambda **kw: kw["on_confirm"]()
    ):
        page._on_detail_install_clicked()

    import time

    timeout = time.time() + 2.0
    while time.time() < timeout and not notifications:
        GLib.MainContext.default().iteration(False)

    assert len(notifications) == 1
    assert notifications[0][1] is True  # is_error flag set
    assert "Disk full" in notifications[0][0] or "Failing Extension" in notifications[0][0]
    assert page.btn_detail_install is not None
    assert page.btn_detail_install.get_sensitive() is True


def test_extensions_page_incompatible_warning_dialog(mock_manager: MagicMock) -> None:
    """Test that installing an incompatible extension shows a warning in the confirmation dialog."""
    page = ExtensionsPage(manager=mock_manager)
    item = ExtensionItem(
        uuid="incompat@example.com",
        name="Incompatible Extension",
        description="",
        is_installed=False,
        is_compatible=False,
    )
    page.show_details(item)

    captured_dialog_kwargs: dict[str, Any] = {}

    def capture_dialog(**kwargs: Any) -> None:
        captured_dialog_kwargs.update(kwargs)

    with patch.object(page, "_show_confirmation_dialog", side_effect=capture_dialog):
        page._on_detail_install_clicked()

    assert (
        "Warning" in captured_dialog_kwargs["body"]
        or "Attenzione" in captured_dialog_kwargs["body"]
    )
    assert "Incompatible Extension" in captured_dialog_kwargs["body"]
