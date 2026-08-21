# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Terminal Palette generation and GNOME Terminal profile integration (Task 4.4 - RED Phase)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.css_extractor import ExtractedColors
from gnome_theme_manager.core.terminal_palette import (
    TerminalPalette,
    derive_terminal_palette_from_colors,
    export_palette_to_json,
    import_palette_from_json,
)


def test_terminal_palette_defaults() -> None:
    """Verify default standard 16-color ANSI terminal palette."""
    palette = TerminalPalette()
    assert len(palette.palette) == 16
    assert palette.background_color.startswith("#")
    assert palette.foreground_color.startswith("#")
    assert palette.bold_color is None
    assert palette.cursor_background_color is None
    assert palette.cursor_foreground_color is None


def test_terminal_palette_serialization_roundtrip(tmp_path: Path) -> None:
    """Verify export and import of palette JSON."""
    palette = TerminalPalette(
        name="Custom Nord",
        foreground_color="#D8DEE9",
        background_color="#2E3440",
        palette=[
            "#2E3440", "#BF616A", "#A3BE8C", "#EBCB8B",
            "#81A1C1", "#B48EAD", "#88C0D0", "#E5E9F0",
            "#4C566A", "#BF616A", "#A3BE8C", "#EBCB8B",
            "#81A1C1", "#B48EAD", "#8FBCBB", "#ECEFF4",
        ],
    )
    dest = tmp_path / "nord_palette.json"
    export_palette_to_json(palette, dest)
    assert dest.is_file()

    loaded = import_palette_from_json(dest)
    assert loaded.name == "Custom Nord"
    assert loaded.foreground_color == "#D8DEE9"
    assert loaded.background_color == "#2E3440"
    assert len(loaded.palette) == 16


def test_derive_terminal_palette_from_theme_colors() -> None:
    """Verify generating high-contrast 16 ANSI colors from extracted theme colors."""
    colors = ExtractedColors(
        theme_fg_color="#FFFFFF",
        theme_bg_color="#1E1E2E",
        accent_color="#89B4FA",
    )
    palette = derive_terminal_palette_from_colors(colors, name="Catppuccin Derived")
    assert palette.name == "Catppuccin Derived"
    assert palette.background_color == "#1E1E2E"
    assert palette.foreground_color == "#FFFFFF"
    assert len(palette.palette) == 16
    # Ansi blue (index 4) should reflect accent or derived blue
    assert palette.palette[4].startswith("#")


def test_apply_terminal_palette_gnome_terminal() -> None:
    """Verify applying palette to GNOME Terminal relocatable schema via GSettings."""
    from gnome_theme_manager.core.terminal_palette import apply_palette_to_gnome_terminal

    mock_settings_cls = MagicMock()
    mock_profile_settings = MagicMock()
    mock_settings_cls.new_with_path.return_value = mock_profile_settings
    mock_settings_cls.return_value = MagicMock(get_strv=MagicMock(return_value=["b1dcc9dd-5262-4d8d-a863-c897e6d979b9"]))

    palette = TerminalPalette(
        name="Test",
        foreground_color="#FFFFFF",
        background_color="#000000",
        palette=["#000000"] * 16,
    )

    with patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", True):
        with patch("gnome_theme_manager.core.terminal_palette.Gio") as mock_gio:
            mock_gio.Settings = mock_settings_cls
            success = apply_palette_to_gnome_terminal(palette, profile_id=None)
            assert success is True
            assert mock_profile_settings.set_string.called
            assert mock_profile_settings.set_strv.called
            assert mock_profile_settings.set_boolean.called
            mock_profile_settings.set_boolean.assert_any_call("audible-bell", False)
            mock_profile_settings.set_boolean.assert_any_call("use-transparent-background", False)
            mock_profile_settings.set_boolean.assert_any_call("use-system-font", True)
            mock_profile_settings.set_int.assert_any_call("background-transparency-percent", 0)


def test_list_and_manage_terminal_profiles() -> None:
    """Verify listing, creating, deleting, and setting default terminal profiles."""
    from gnome_theme_manager.core.terminal_palette import (
        create_gnome_terminal_profile,
        delete_gnome_terminal_profile,
        list_gnome_terminal_profiles,
        set_default_gnome_terminal_profile,
    )

    mock_profiles_settings = MagicMock()
    mock_profiles_settings.get_string.return_value = "default-uuid"
    mock_profiles_settings.get_strv.return_value = ["default-uuid", "secondary-uuid"]

    mock_profile_settings = MagicMock()
    mock_profile_settings.get_string.return_value = "Profile Name"

    mock_settings_cls = MagicMock()
    mock_settings_cls.return_value = mock_profiles_settings
    mock_settings_cls.new_with_path.return_value = mock_profile_settings

    with patch("gnome_theme_manager.core.terminal_palette._GIO_AVAILABLE", True):
        with patch("gnome_theme_manager.core.terminal_palette.Gio") as mock_gio:
            mock_gio.Settings = mock_settings_cls

            # 1. List
            profiles = list_gnome_terminal_profiles()
            assert len(profiles) == 2
            assert profiles[0].is_default is True
            assert profiles[1].is_default is False

            # 2. Set default
            ok_def = set_default_gnome_terminal_profile("secondary-uuid")
            assert ok_def is True
            mock_profiles_settings.set_string.assert_called_with("default", "secondary-uuid")

            # 3. Create
            new_id = create_gnome_terminal_profile("My New Profile")
            assert new_id is not None
            assert mock_profiles_settings.set_strv.called

            # 4. Delete default profile -> should be blocked
            ok_del_def = delete_gnome_terminal_profile("default-uuid")
            assert ok_del_def is False

            # 5. Delete non-default profile -> should succeed
            ok_del_sec = delete_gnome_terminal_profile("secondary-uuid")
            assert ok_del_sec is True
