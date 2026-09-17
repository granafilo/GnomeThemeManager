# SPDX-License-Identifier: GPL-3.0-or-later

"""GUI integration tests for Terminal Palette page (Task 4.4 - RED Phase)."""

from unittest.mock import MagicMock, patch

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
    mock_theme_manager.get_current_terminal_palette.return_value = palette
    mock_theme_manager.apply_terminal_palette.return_value = True

    with patch(
        "gnome_theme_manager.gui_gtk.pages.terminal.is_terminal_installed", return_value=True
    ):
        page = TerminalPage(manager=mock_theme_manager)
        page.refresh()

        notifications = []
        page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

        page.on_apply_button_clicked(page.apply_button)

        assert mock_theme_manager.apply_terminal_palette.called
        assert len(notifications) == 1
        assert notifications[0][1] is False


def test_terminal_page_apply_palette_not_installed(mock_theme_manager: MagicMock) -> None:
    """Verify error notification when applying palette to uninstalled terminal."""
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
    mock_theme_manager.get_current_terminal_palette.return_value = palette

    with patch(
        "gnome_theme_manager.gui_gtk.pages.terminal.is_terminal_installed", return_value=False
    ):
        page = TerminalPage(manager=mock_theme_manager)
        page.refresh()

        notifications: list[tuple[str, bool]] = []
        page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

        page.on_apply_button_clicked(page.apply_button)

        assert not mock_theme_manager.apply_terminal_palette.called
        assert len(notifications) == 1
        assert notifications[0][1] is True


def test_terminal_page_apply_palette_ptyxis(mock_theme_manager: MagicMock) -> None:
    """Verify applying palette when Ptyxis is selected passes terminal_id='ptyxis'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.terminal import TerminalPage

    palette = TerminalPalette(
        name="Ptyxis Test",
        foreground_color="#FFFFFF",
        background_color="#1E1E1E",
    )
    mock_theme_manager.list_terminal_profiles.return_value = []
    mock_theme_manager.get_derived_terminal_palette.return_value = palette
    mock_theme_manager.get_current_terminal_palette.return_value = palette
    mock_theme_manager.apply_terminal_palette.return_value = True

    with patch(
        "gnome_theme_manager.gui_gtk.pages.terminal.is_terminal_installed", return_value=True
    ):
        page = TerminalPage(manager=mock_theme_manager)
        page.refresh()

        # Select ptyxis
        page._selected_terminal_id = "ptyxis"

        notifications: list[tuple[str, bool]] = []
        page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

        page.on_apply_button_clicked(page.apply_button)

        assert mock_theme_manager.apply_terminal_palette.called
        call_kwargs = mock_theme_manager.apply_terminal_palette.call_args[1]
        assert call_kwargs.get("terminal_id") == "ptyxis"
        assert len(notifications) == 1
        assert notifications[0][1] is False


def test_terminal_page_uninstalled_terminal_install_hint(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify selecting an uninstalled terminal surfaces the accurate install command."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.pages.terminal import TerminalPage

    mock_theme_manager.detect_terminal.return_value = MagicMock(terminal_id="gnome-terminal")
    mock_theme_manager.detect_default_terminal.return_value = MagicMock(
        terminal_id="gnome-terminal"
    )

    from gnome_theme_manager.core.terminal_profile import TerminalProfile

    wezterm_profile = TerminalProfile(
        terminal_id="wezterm",
        terminal_name="WezTerm",
        launch_command='wezterm start -- "{cmd}"',
        config_file_path="~/.config/wezterm/wezterm.lua",
        supports_tabs=True,
        supports_split=True,
        supports_profiles=False,
        install_command="flatpak install -y flathub org.wezfurlong.wezterm",
        icon_name="org.wezfurlong.wezterm",
        notes="GPU accelerated",
    )
    mock_theme_manager.get_terminal_profile.return_value = wezterm_profile

    with patch(
        "gnome_theme_manager.gui_gtk.pages.terminal.is_terminal_installed", return_value=False
    ):
        page = TerminalPage(manager=mock_theme_manager)
        notifications: list[tuple[str, bool]] = []
        page.on_notify_message = lambda msg, is_err: notifications.append((msg, is_err))

        page._selected_terminal_id = "wezterm"
        page._update_terminal_ui()

        assert page.terminal_warning_row is not None
        assert page.terminal_warning_row.get_visible() is True
        subtitle = page.terminal_warning_row.get_subtitle()
        assert "flatpak install -y flathub org.wezfurlong.wezterm" in subtitle
