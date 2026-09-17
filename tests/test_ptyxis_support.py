# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Ptyxis terminal palette export, profile management, and application."""

import configparser
from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.terminal_palette import (
    TerminalPalette,
    apply_palette_to_ptyxis,
    create_ptyxis_profile,
    delete_ptyxis_profile,
    export_ptyxis_palette,
    list_ptyxis_profiles,
    read_current_ptyxis_palette,
    set_default_ptyxis_profile,
)


def test_export_ptyxis_palette(tmp_path: Path) -> None:
    """Verify that export_ptyxis_palette generates a valid INI .palette file."""
    palette = TerminalPalette(
        name="Cyberpunk",
        foreground_color="#EEEEEE",
        background_color="#121212",
        palette=[
            "#000000",
            "#FF0000",
            "#00FF00",
            "#FFFF00",
            "#0000FF",
            "#FF00FF",
            "#00FFFF",
            "#FFFFFF",
            "#555555",
            "#FF5555",
            "#55FF55",
            "#FFFF55",
            "#5555FF",
            "#FF55FF",
            "#55FFFF",
            "#FFFFFF",
        ],
        bold_color="#FFAA00",
        cursor_background_color="#00FFCC",
    )

    out_file = export_ptyxis_palette(palette, name="Cyberpunk-Theme", target_dir=tmp_path)
    assert out_file.is_file()
    assert out_file.name == "Cyberpunk-Theme.palette"

    cfg = configparser.ConfigParser()
    cfg.read(str(out_file), encoding="utf-8")

    assert cfg.has_section("Palette")
    assert cfg.get("Palette", "Name") == "Cyberpunk-Theme"
    assert cfg.get("Palette", "Primary") == "true"

    assert cfg.has_section("Dark")
    assert cfg.get("Dark", "Foreground") == "#EEEEEE"
    assert cfg.get("Dark", "Background") == "#121212"
    assert cfg.get("Dark", "Color0") == "#000000"
    assert cfg.get("Dark", "Color1") == "#FF0000"
    assert cfg.get("Dark", "Color15") == "#FFFFFF"
    assert cfg.get("Dark", "Bold") == "#FFAA00"
    assert cfg.get("Dark", "Cursor") == "#00FFCC"

    assert cfg.has_section("Light")
    assert cfg.get("Light", "Foreground") == "#EEEEEE"
    assert cfg.get("Light", "Color4") == "#0000FF"


def test_list_ptyxis_profiles_via_gio() -> None:
    """Verify listing Ptyxis profiles using mocked Gio.Settings."""
    mock_main_settings = MagicMock()
    mock_main_settings.get_strv.return_value = ["uuid-1", "uuid-2"]
    mock_main_settings.get_string.return_value = "uuid-1"

    mock_prof_settings = MagicMock()
    mock_prof_settings.get_string.side_effect = lambda key: "Default" if key == "label" else ""

    def mock_get_settings(schema_id: str, path: str | None = None) -> MagicMock | None:
        if schema_id == "org.gnome.Ptyxis":
            return mock_main_settings
        if schema_id == "org.gnome.Ptyxis.Profile":
            return mock_prof_settings
        return None

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        side_effect=mock_get_settings,
    ):
        profiles = list_ptyxis_profiles()
        assert len(profiles) == 2
        assert profiles[0].id == "uuid-1"
        assert profiles[0].is_default is True
        assert profiles[1].id == "uuid-2"
        assert profiles[1].is_default is False


def test_list_ptyxis_profiles_dconf_fallback() -> None:
    """Verify listing Ptyxis profiles falling back to dconf CLI."""

    def mock_dconf(path: str) -> str | None:
        if path == "/org/gnome/Ptyxis/profile-uuids":
            return "['dconf-1', 'dconf-2']"
        if path == "/org/gnome/Ptyxis/default-profile-uuid":
            return "'dconf-2'"
        if path == "/org/gnome/Ptyxis/Profiles/dconf-1/label":
            return "'Work'"
        if path == "/org/gnome/Ptyxis/Profiles/dconf-2/label":
            return "'Main'"
        return None

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        return_value=None,
    ):
        with patch(
            "gnome_theme_manager.core.terminal_palette._dconf_read",
            side_effect=mock_dconf,
        ):
            profiles = list_ptyxis_profiles()
            assert len(profiles) == 2
            assert profiles[0].id == "dconf-1"
            assert profiles[0].name == "Work"
            assert profiles[0].is_default is False
            assert profiles[1].id == "dconf-2"
            assert profiles[1].name == "Main"
            assert profiles[1].is_default is True


def test_create_and_delete_ptyxis_profile(tmp_path: Path) -> None:
    """Verify creating and deleting a Ptyxis profile."""
    mock_main_settings = MagicMock()
    mock_main_settings.get_strv.return_value = ["default-uuid"]
    mock_main_settings.get_string.return_value = "default-uuid"

    mock_prof = MagicMock()

    def mock_get_settings(schema_id: str, path: str | None = None) -> MagicMock:
        if schema_id == "org.gnome.Ptyxis":
            return mock_main_settings
        return mock_prof

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        side_effect=mock_get_settings,
    ):
        with patch("gnome_theme_manager.core.terminal_palette._dconf_write", return_value=True):
            with patch(
                "gnome_theme_manager.core.terminal_palette.export_ptyxis_palette",
                return_value=tmp_path / "test.palette",
            ):
                new_id = create_ptyxis_profile("New Test Profile")
                assert new_id is not None
                assert mock_main_settings.set_strv.called

                # Try deleting default profile -> should be disallowed
                cannot_delete = delete_ptyxis_profile("default-uuid")
                assert cannot_delete is False

                # Deleting the newly created profile -> should succeed
                mock_main_settings.get_strv.return_value = ["default-uuid", new_id]
                can_delete = delete_ptyxis_profile(new_id)
                assert can_delete is True


def test_set_default_ptyxis_profile() -> None:
    """Verify setting a profile as default in Ptyxis."""
    mock_main_settings = MagicMock()
    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        return_value=mock_main_settings,
    ):
        success = set_default_ptyxis_profile("target-uuid-123")
        assert success is True
        mock_main_settings.set_string.assert_called_once_with(
            "default-profile-uuid", "target-uuid-123"
        )


def test_apply_palette_to_ptyxis(tmp_path: Path) -> None:
    """Verify applying a palette to Ptyxis via GSettings and palette file generation."""
    mock_main_settings = MagicMock()
    mock_main_settings.get_string.return_value = "profile-abc"

    mock_prof_settings = MagicMock()

    def mock_get_settings(schema_id: str, path: str | None = None) -> MagicMock:
        if schema_id == "org.gnome.Ptyxis":
            return mock_main_settings
        return mock_prof_settings

    palette = TerminalPalette(
        name="Adwaita Dark Custom",
        foreground_color="#FFFFFF",
        background_color="#1E1E1E",
        palette=["#1E1E1E"] * 16,
        use_system_font=False,
        font="Fira Code 12",
        use_transparent_background=True,
        background_transparency_percent=20,
    )

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        side_effect=mock_get_settings,
    ):
        success = apply_palette_to_ptyxis(
            palette,
            profile_id=None,
            palette_name="Adwaita-Custom",
            target_dir=tmp_path,
        )
        assert success is True
        assert (tmp_path / "Adwaita-Custom.palette").is_file()
        mock_prof_settings.set_string.assert_any_call("palette", "Adwaita-Custom")
        mock_prof_settings.set_double.assert_called_once()
        assert 0.79 <= mock_prof_settings.set_double.call_args[0][1] <= 0.81
        mock_main_settings.set_boolean.assert_any_call("use-system-font", False)
        mock_main_settings.set_string.assert_any_call("font-name", "Fira Code 12")


def test_read_current_ptyxis_palette(tmp_path: Path) -> None:
    """Verify reading palette and settings from a Ptyxis profile and palette file."""
    # Write sample palette file
    pal_file = tmp_path / "CustomTheme.palette"
    pal_file.write_text(
        "[Palette]\nName=CustomTheme\n\n[Dark]\nForeground=#FAFAFA\nBackground=#111111\nColor0=#000000\nColor15=#FFFFFF\n",
        encoding="utf-8",
    )

    mock_main_settings = MagicMock()
    mock_main_settings.get_string.side_effect = lambda k: {
        "font-name": "Monospace 10",
        "cursor-shape": "ibeam",
        "cursor-blink-mode": "on",
    }.get(k, "")
    mock_main_settings.get_boolean.side_effect = lambda k: {
        "use-system-font": False,
        "audible-bell": True,
    }.get(k, False)

    mock_prof_settings = MagicMock()
    mock_prof_settings.get_string.side_effect = lambda k: {
        "label": "My Profile",
        "palette": "CustomTheme",
    }.get(k, "")
    mock_prof_settings.get_double.return_value = 0.90

    def mock_get_settings(schema_id: str, path: str | None = None) -> MagicMock:
        if schema_id == "org.gnome.Ptyxis":
            return mock_main_settings
        return mock_prof_settings

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        side_effect=mock_get_settings,
    ):
        with patch(
            "pathlib.Path.home",
            return_value=tmp_path,
        ):
            # Place palette where search_dirs finds it:
            pal_dir = tmp_path / ".local/share/org.gnome.Ptyxis/palettes"
            pal_dir.mkdir(parents=True, exist_ok=True)
            (pal_dir / "CustomTheme.palette").write_text(pal_file.read_text())

            palette = read_current_ptyxis_palette(profile_id="pid-1")
            assert palette is not None
            assert palette.name == "My Profile"
            assert palette.foreground_color == "#FAFAFA"
            assert palette.background_color == "#111111"
            assert palette.font == "Monospace 10"
            assert palette.use_system_font is False
            assert palette.cursor_shape == "ibeam"
            assert palette.cursor_blink_mode == "on"
            assert palette.audible_bell is True
            assert palette.use_transparent_background is True
            assert palette.background_transparency_percent == 10


def test_theme_manager_ptyxis_routing() -> None:
    """Verify ThemeManager dispatches profile and palette operations to Ptyxis when requested."""
    manager = ThemeManager()
    palette = TerminalPalette(name="TestPalette")

    with patch(
        "gnome_theme_manager.core.terminal_palette.apply_palette_to_ptyxis",
        return_value=True,
    ) as mock_apply:
        res = manager.apply_terminal_palette(palette, profile_id="p1", terminal_id="ptyxis")
        assert res is True
        mock_apply.assert_called_once_with(palette, profile_id="p1")

    with patch(
        "gnome_theme_manager.core.terminal_palette.list_ptyxis_profiles",
        return_value=[],
    ) as mock_list:
        res_list = manager.list_terminal_profiles(terminal_id="ptyxis")
        assert res_list == []
        mock_list.assert_called_once()

    with patch(
        "gnome_theme_manager.core.terminal_palette.read_current_ptyxis_palette",
        return_value=palette,
    ) as mock_read:
        res_pal = manager.get_current_terminal_palette(profile_id="p1", terminal_id="ptyxis")
        assert res_pal == palette
        mock_read.assert_called_once_with(profile_id="p1")


def test_dconf_helpers() -> None:
    """Verify _dconf_read and _dconf_write handlers and exception handling."""
    from gnome_theme_manager.core.terminal_palette import _dconf_read, _dconf_write

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(return_code=0, returncode=0, stdout=" 'test_val'\n ")
        val = _dconf_read("/test/path")
        assert val == "'test_val'"

        mock_run.side_effect = Exception("dconf missing")
        val_err = _dconf_read("/test/path")
        assert val_err is None

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = None
        mock_run.return_value = MagicMock(returncode=0)
        assert _dconf_write("/test/path", "'val'") is True

        mock_run.return_value = MagicMock(returncode=1)
        assert _dconf_write("/test/path", "'val'") is False

        mock_run.side_effect = Exception("failed")
        assert _dconf_write("/test/path", "'val'") is False


def test_detect_installed_terminal_ptyxis() -> None:
    """Verify detect_installed_terminal detects ptyxis first."""
    from gnome_theme_manager.core.terminal_palette import detect_installed_terminal

    with patch(
        "gnome_theme_manager.core.terminal_palette._find_terminal_binary",
        side_effect=lambda name: Path("/usr/bin/ptyxis") if "ptyxis" in name.lower() else None,
    ):
        with patch("gnome_theme_manager.core.terminal_palette.schema_exists", return_value=True):
            term = detect_installed_terminal()
            assert term is not None
            assert term.terminal_type == "ptyxis"
            assert term.display_name == "Ptyxis"
            assert term.supports_gsettings is True


def test_export_ptyxis_palette_defaults_and_flatpak(tmp_path: Path) -> None:
    """Verify default directory fallback and Flatpak sync in export_ptyxis_palette."""
    palette = TerminalPalette()

    with patch("pathlib.Path.home", return_value=tmp_path):
        # Create flatpak simulated parent
        flatpak_dir = tmp_path / ".var/app/org.gnome.Ptyxis/data/ptyxis/palettes"
        flatpak_dir.parent.mkdir(parents=True, exist_ok=True)

        res_path = export_ptyxis_palette(palette)
        assert res_path.is_file()
        assert (flatpak_dir / "Gnome-Theme-Manager.palette").is_file()


def test_apply_palette_to_ptyxis_dconf_fallback(tmp_path: Path) -> None:
    """Verify apply_palette_to_ptyxis falls back to dconf write when Gio settings are unavailable."""
    palette = TerminalPalette()

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        return_value=None,
    ):
        with patch(
            "gnome_theme_manager.core.terminal_palette._dconf_read", return_value="'uuid-def'"
        ):
            with patch(
                "gnome_theme_manager.core.terminal_palette._dconf_write", return_value=True
            ) as mock_write:
                ok = apply_palette_to_ptyxis(palette, target_dir=tmp_path)
                assert ok is True
                assert mock_write.called


def test_apply_palette_to_ptyxis_export_error() -> None:
    """Verify apply_palette_to_ptyxis returns False when export fails."""
    palette = TerminalPalette()
    with patch(
        "gnome_theme_manager.core.terminal_palette.export_ptyxis_palette",
        side_effect=OSError("Read-only filesystem"),
    ):
        assert apply_palette_to_ptyxis(palette) is False


def test_manager_ptyxis_crud_routing() -> None:
    """Verify ThemeManager create, delete, and default profile routing for ptyxis."""
    manager = ThemeManager()

    with patch(
        "gnome_theme_manager.core.terminal_palette.create_ptyxis_profile",
        return_value="new-id",
    ) as mock_create:
        assert manager.create_terminal_profile("Ptyxis Prof", terminal_id="ptyxis") == "new-id"
        mock_create.assert_called_once()

    with patch(
        "gnome_theme_manager.core.terminal_palette.delete_ptyxis_profile",
        return_value=True,
    ) as mock_del:
        assert manager.delete_terminal_profile("new-id", terminal_id="ptyxis") is True
        mock_del.assert_called_once_with("new-id")

    with patch(
        "gnome_theme_manager.core.terminal_palette.set_default_ptyxis_profile",
        return_value=True,
    ) as mock_def:
        assert manager.set_default_terminal_profile("new-id", terminal_id="ptyxis") is True
        mock_def.assert_called_once_with("new-id")


def test_ptyxis_profile_schema_safety_no_crash_on_missing_keys(tmp_path: Path) -> None:
    """Verify that Ptyxis profile schema lacking 'use-custom-font' never raises or crashes."""
    # Real Ptyxis.Profile schema keys
    profile_real_keys = ["label", "palette", "opacity", "bold-is-bright", "limit-scrollback"]
    mock_prof = MagicMock()
    mock_prof.list_keys.return_value = profile_real_keys

    def fail_on_missing_key(k: str) -> None:
        if k not in profile_real_keys:
            raise KeyError(f"Settings schema does not contain a key named '{k}'")

    mock_prof.get_boolean.side_effect = fail_on_missing_key
    mock_prof.get_string.side_effect = lambda k: (
        "Ptyxis Default" if k in profile_real_keys else fail_on_missing_key(k)
    )
    mock_prof.get_double.side_effect = lambda k: (
        1.0 if k in profile_real_keys else fail_on_missing_key(k)
    )
    mock_prof.set_boolean.side_effect = lambda k, v: (
        None if k in profile_real_keys else fail_on_missing_key(k)
    )

    mock_app = MagicMock()
    app_real_keys = [
        "use-system-font",
        "font-name",
        "cursor-shape",
        "cursor-blink-mode",
        "audible-bell",
    ]
    mock_app.list_keys.return_value = app_real_keys
    mock_app.get_boolean.return_value = True
    mock_app.get_string.return_value = "Monospace 11"

    def mock_get(schema_id: str, path: str | None = None) -> MagicMock:
        if schema_id == "org.gnome.Ptyxis":
            return mock_app
        return mock_prof

    with patch(
        "gnome_theme_manager.core.terminal_palette._get_settings_instance",
        side_effect=mock_get,
    ):
        with patch("pathlib.Path.home", return_value=tmp_path):
            # Must read without raising
            palette = read_current_ptyxis_palette(profile_id="uuid-123")
            assert palette is not None
            assert palette.name == "Ptyxis Default"

            # Must apply without raising
            ok = apply_palette_to_ptyxis(palette, profile_id="uuid-123", target_dir=tmp_path)
            assert ok is True
