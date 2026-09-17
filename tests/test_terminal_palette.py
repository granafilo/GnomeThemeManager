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
            "#2E3440",
            "#BF616A",
            "#A3BE8C",
            "#EBCB8B",
            "#81A1C1",
            "#B48EAD",
            "#88C0D0",
            "#E5E9F0",
            "#4C566A",
            "#BF616A",
            "#A3BE8C",
            "#EBCB8B",
            "#81A1C1",
            "#B48EAD",
            "#8FBCBB",
            "#ECEFF4",
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
    mock_settings_cls.return_value = MagicMock(
        get_strv=MagicMock(return_value=["b1dcc9dd-5262-4d8d-a863-c897e6d979b9"])
    )

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


def test_gnome_terminal_debian_no_transparency() -> None:
    """Verify GNOME Terminal read and apply work seamlessly on vanilla GNOME (Debian) without transparency keys."""
    from gnome_theme_manager.core.terminal_palette import (
        TerminalPalette,
        apply_palette_to_gnome_terminal,
        read_current_gnome_terminal_palette,
    )

    # Standard vanilla upstream keys (NO use-transparent-background or background-transparency-percent)
    vanilla_keys = [
        "visible-name",
        "foreground-color",
        "background-color",
        "palette",
        "use-system-font",
        "font",
        "cursor-shape",
        "cursor-blink-mode",
        "audible-bell",
        "use-theme-colors",
    ]

    mock_profiles_settings = MagicMock()
    mock_profiles_settings.get_string.return_value = "vanilla-profile-uuid"

    mock_profile_settings = MagicMock()
    mock_profile_settings.list_keys.return_value = vanilla_keys
    mock_profile_settings.get_string.side_effect = lambda k: {
        "visible-name": "Debian Vanilla",
        "foreground-color": "#ffffff",
        "background-color": "#000000",
        "font": "Monospace 10",
        "cursor-shape": "block",
        "cursor-blink-mode": "system",
    }.get(k, "")
    mock_profile_settings.get_strv.side_effect = lambda k: (
        ["#000000"] * 16 if k == "palette" else []
    )
    mock_profile_settings.get_boolean.side_effect = lambda k: {
        "use-system-font": True,
        "audible-bell": False,
    }.get(k, False)

    mock_settings_cls = MagicMock()
    mock_settings_cls.return_value = mock_profiles_settings
    mock_settings_cls.new_with_path.return_value = mock_profile_settings

    with patch("gnome_theme_manager.core.terminal_palette.schema_exists", return_value=True):
        with patch("gnome_theme_manager.core.terminal_palette._GIO_AVAILABLE", True):
            with patch("gnome_theme_manager.core.terminal_palette.Gio") as mock_gio:
                mock_gio.Settings = mock_settings_cls

                # 1. Reading should succeed and default transparency to False/0 without crashing
                read_palette = read_current_gnome_terminal_palette(
                    profile_id="vanilla-profile-uuid"
                )
                assert read_palette is not None
                assert read_palette.name == "Debian Vanilla"
                assert read_palette.use_transparent_background is False
                assert read_palette.background_transparency_percent == 0

                # 2. Applying palette should skip nonexistent transparency keys and not crash
                pal_to_apply = TerminalPalette(
                    name="Custom Debian",
                    foreground_color="#e0e0e0",
                    background_color="#121212",
                    palette=["#121212"] * 16,
                    use_transparent_background=True,
                    background_transparency_percent=25,
                )
                success = apply_palette_to_gnome_terminal(
                    pal_to_apply, profile_id="vanilla-profile-uuid"
                )
                assert success is True
                # Crucial assertion: set_boolean should NEVER be called for use-transparent-background
                for call in mock_profile_settings.set_boolean.call_args_list:
                    assert call[0][0] != "use-transparent-background"
                # Nor should set_int be called for background-transparency-percent
                for call in mock_profile_settings.set_int.call_args_list:
                    assert call[0][0] != "background-transparency-percent"


def test_gnome_terminal_supports_transparency_detection() -> None:
    """Verify detection of transparency capability in GNOME Terminal profiles."""
    from gnome_theme_manager.core.terminal_palette import gnome_terminal_supports_transparency

    mock_profile_patched = MagicMock()
    mock_profile_patched.list_keys.return_value = ["use-transparent-background", "font"]

    mock_profile_vanilla = MagicMock()
    mock_profile_vanilla.list_keys.return_value = ["font", "audible-bell"]

    with patch("gnome_theme_manager.core.terminal_palette.schema_exists", return_value=True):
        with patch(
            "gnome_theme_manager.core.terminal_palette._get_settings_instance"
        ) as mock_get_inst:
            # Patched distro (Ubuntu/Fedora)
            mock_get_inst.return_value = mock_profile_patched
            assert gnome_terminal_supports_transparency("patched-uuid") is True

            # Vanilla distro (Debian)
            mock_get_inst.return_value = mock_profile_vanilla
            assert gnome_terminal_supports_transparency("vanilla-uuid") is False


def test_alacritty_palette_apply_and_read(tmp_path: Path) -> None:
    """Verify Alacritty palette generation, file writing, and reading."""
    from gnome_theme_manager.core.terminal_palette import (
        apply_palette_to_alacritty,
        read_current_alacritty_palette,
    )

    alacritty_cfg = tmp_path / "alacritty.toml"
    palette = TerminalPalette(
        name="CachyOS Alacritty",
        foreground_color="#cdd6f4",
        background_color="#1e1e2e",
        palette=[f"#{i:02x}{i:02x}{i:02x}" for i in range(16)],
        use_system_font=False,
        font="FiraCode Nerd Font 12",
        cursor_shape="ibeam",
        cursor_blink_mode="on",
        use_transparent_background=True,
        background_transparency_percent=15,
    )

    ok = apply_palette_to_alacritty(palette, config_path=alacritty_cfg)
    assert ok is True
    assert alacritty_cfg.is_file()

    content = alacritty_cfg.read_text(encoding="utf-8")
    assert "[colors.primary]" in content
    assert 'background = "#1e1e2e"' in content
    assert 'foreground = "#cdd6f4"' in content
    assert "opacity = 0.85" in content
    assert 'family = "FiraCode Nerd Font"' in content
    assert "size = 12.0" in content

    read_back = read_current_alacritty_palette(config_path=alacritty_cfg)
    assert read_back is not None
    assert read_back.background_color == "#1e1e2e"
    assert read_back.foreground_color == "#cdd6f4"
    assert read_back.use_transparent_background is True
    assert read_back.background_transparency_percent == 15
    assert read_back.cursor_shape == "ibeam"
    assert read_back.cursor_blink_mode == "on"
    assert "FiraCode Nerd Font" in read_back.font


def test_alacritty_palette_preserves_user_settings(tmp_path: Path) -> None:
    """Verify Alacritty palette application preserves custom user keys and sections."""
    from gnome_theme_manager.core.terminal_palette import apply_palette_to_alacritty

    alacritty_cfg = tmp_path / "alacritty.toml"
    initial_content = (
        "[env]\n"
        'TERM = "alacritty"\n\n'
        "[window]\n"
        "padding = { x = 8, y = 8 }\n"
        'decorations = "Full"\n'
        "opacity = 0.50\n\n"
        "[keyboard]\n"
        "bindings = []\n"
    )
    alacritty_cfg.write_text(initial_content, encoding="utf-8")

    palette = TerminalPalette(
        name="Updated Palette",
        foreground_color="#ffffff",
        background_color="#000000",
        use_transparent_background=False,
    )

    ok = apply_palette_to_alacritty(palette, config_path=alacritty_cfg)
    assert ok is True

    updated = alacritty_cfg.read_text(encoding="utf-8")
    assert 'TERM = "alacritty"' in updated
    assert "padding = { x = 8, y = 8 }" in updated
    assert 'decorations = "Full"' in updated
    assert "opacity = 1.00" in updated
    assert "bindings = []" in updated
    assert 'background = "#000000"' in updated


def test_kitty_palette_apply_and_read(tmp_path: Path) -> None:
    """Verify Kitty palette generation, file writing, and reading."""
    from gnome_theme_manager.core.terminal_palette import (
        apply_palette_to_kitty,
        read_current_kitty_palette,
    )

    kitty_cfg = tmp_path / "kitty.conf"
    initial_content = "map ctrl+c copy_to_clipboard\ntab_bar_style powerline\n"
    kitty_cfg.write_text(initial_content, encoding="utf-8")

    palette = TerminalPalette(
        name="CachyOS Kitty",
        foreground_color="#d0d0d0",
        background_color="#101010",
        palette=[f"#{i:02x}{i:02x}{i:02x}" for i in range(16)],
        use_system_font=False,
        font="JetBrains Mono 11",
        cursor_shape="underline",
        cursor_blink_mode="off",
        use_transparent_background=True,
        background_transparency_percent=10,
    )

    ok = apply_palette_to_kitty(palette, config_path=kitty_cfg)
    assert ok is True
    assert kitty_cfg.is_file()

    content = kitty_cfg.read_text(encoding="utf-8")
    assert "map ctrl+c copy_to_clipboard" in content
    assert "tab_bar_style powerline" in content
    assert "foreground #d0d0d0" in content
    assert "background #101010" in content
    assert "background_opacity 0.90" in content
    assert "font_family JetBrains Mono" in content
    assert "cursor_shape underline" in content
    assert "cursor_blink_interval 0" in content

    read_back = read_current_kitty_palette(config_path=kitty_cfg)
    assert read_back is not None
    assert read_back.background_color == "#101010"
    assert read_back.foreground_color == "#d0d0d0"
    assert read_back.use_transparent_background is True
    assert read_back.background_transparency_percent == 10
    assert read_back.cursor_shape == "underline"
    assert read_back.cursor_blink_mode == "off"
