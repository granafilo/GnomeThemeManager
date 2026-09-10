# SPDX-License-Identifier: GPL-3.0-or-later

"""Integration tests for Command Line Interface (CLI) commands.

Verifies end-to-end behavior of commands:
- `current` (query active state, including Shell and color-scheme)
- `list` (tabular list with filters for gtk, icon, cursor, shell)
- `apply` (pre-validation, GSettings application, GTK4 override, and error handling)
- `preset` (list, save, apply, delete)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.cli.main import format_table, main
from gnome_theme_manager.core.models import ApplyResult, SystemStatus, Theme, ThemeSet, ThemeType


def test_format_table() -> None:
    """Verify ASCII table generation."""
    headers = ["NOME", "TIPO", "ORIGINE"]
    rows = [
        ["Adwaita", "gtk", "System"],
        ["Nordic", "shell", "User"],
    ]
    output = format_table(headers, rows)

    assert "+--------+" in output or "+-------+" in output or "+------+" in output
    assert "NOME" in output
    assert "Adwaita" in output
    assert "Nordic" in output


def test_cli_current_success(capsys) -> None:
    """Verify 'current' command output when GSettings and Shell are available."""
    mock_theme_set = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus-Dark",
        cursor_theme="Capitaine",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )
    mock_status = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=True,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.themes"),
        user_icons_path=Path("/home/user/.icons"),
    )

    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.get_current_themes.return_value = mock_theme_set
        mock_mgr.get_system_status.return_value = mock_status
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["current"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Currently active GNOME themes:" in captured.out
        assert "GTK Theme (Applications):  Nordic" in captured.out
        assert "GNOME Shell Theme:         Nordic" in captured.out
        assert "Color Scheme:            prefer-dark" in captured.out


def test_cli_list_with_shell_type(capsys, tmp_path: Path) -> None:
    """Verify --type shell filter in 'list' command."""
    mock_themes = [
        Theme(
            name="Nordic", theme_type=ThemeType.SHELL, path=tmp_path / "Nordic", is_user_level=True
        ),
    ]

    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_themes.return_value = mock_themes
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["list", "--type", "shell"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Nordic" in captured.out
        assert "shell" in captured.out
        mock_mgr.list_themes.assert_called_once_with(theme_type=ThemeType.SHELL, user_only=False)


def test_cli_apply_with_gtk_and_shell(capsys) -> None:
    """Verify simultaneous application of GTK theme, Shell theme, and GTK4 override."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.apply_themes.return_value = ApplyResult(
            gtk_theme="Nordic",
            gtk4_override_applied=True,
            shell_theme="Nordic",
        )
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["apply", "--gtk", "Nordic", "--shell", "Nordic"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "GTK Theme set to:         Nordic" in captured.out
        assert "GNOME Shell Theme set to: Nordic" in captured.out
        assert "GTK4/Libadwaita override applied" in captured.out

        mock_mgr.apply_themes.assert_called_once()
        target_set: ThemeSet = mock_mgr.apply_themes.call_args[0][0]
        assert target_set.gtk_theme == "Nordic"
        assert target_set.shell_theme == "Nordic"


def test_cli_apply_no_gtk4_override_flag(capsys) -> None:
    """Verify that --no-gtk4-override flag disables GTK4 override."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.apply_themes.return_value = ApplyResult(
            gtk_theme="Nordic",
            gtk4_override_applied=False,
        )
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["apply", "--gtk", "Nordic", "--no-gtk4-override"])
        _ = capsys.readouterr()

        assert exit_code == 0
        mock_mgr.apply_themes.assert_called_once_with(
            ThemeSet(gtk_theme="Nordic"),
            apply_gtk4_override=False,
            propagate_sandbox=True,
        )


def test_cli_apply_unified_theme(capsys, tmp_path: Path) -> None:
    """Verify that --theme parameter applies both GTK and Shell."""
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    shell_theme = Theme("Nordic", ThemeType.SHELL, tmp_path / "Nordic", True)

    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.find_theme.side_effect = lambda name, t_type: (
            gtk_theme if t_type == ThemeType.GTK else shell_theme
        )
        mock_mgr.apply_themes.return_value = ApplyResult(
            gtk_theme="Nordic",
            gtk4_override_applied=True,
            shell_theme="Nordic",
        )
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["apply", "--theme", "Nordic"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "GTK Theme set to:         Nordic" in captured.out
        assert "GNOME Shell Theme set to: Nordic" in captured.out


# -----------------------------------------------------------------------------
# Test CLI Preset (list, save, apply, delete)
# -----------------------------------------------------------------------------


def test_cli_preset_list_empty(capsys) -> None:
    """Verify 'preset list' command when no presets are saved."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_presets.return_value = []
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["preset", "list"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "No presets saved." in captured.out


def test_cli_preset_list_with_items(capsys) -> None:
    """Verify 'preset list' command with saved presets."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_presets.return_value = ["DarkSetup", "LightSetup"]
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["preset", "list"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "DarkSetup" in captured.out
        assert "LightSetup" in captured.out
        assert "Total presets: 2" in captured.out


def test_cli_preset_save_success(capsys, tmp_path: Path) -> None:
    """Verify 'preset save <name>' command."""
    preset_file = tmp_path / "MyPreset.json"
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.save_current_as_preset.return_value = preset_file
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["preset", "save", "MyPreset", "-y"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Preset 'MyPreset' saved successfully" in captured.out
        mock_mgr.save_current_as_preset.assert_called_once_with("MyPreset", overwrite=True)


def test_cli_preset_apply_success(capsys) -> None:
    """Verify 'preset apply <name>' command."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.apply_preset.return_value = ApplyResult(
            gtk_theme="Nordic",
            icon_theme="Papirus",
            gtk4_override_applied=True,
        )
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["preset", "apply", "NordicPreset"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Preset 'NordicPreset' applied successfully" in captured.out
        assert "GTK Theme set to:         Nordic" in captured.out
        mock_mgr.apply_preset.assert_called_once_with(
            "NordicPreset",
            apply_gtk4_override=True,
            propagate_sandbox=True,
        )


def test_cli_preset_delete_with_yes(capsys) -> None:
    """Verify 'preset delete <name> -y' command (without prompt)."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.delete_preset.return_value = True
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["preset", "delete", "OldPreset", "-y"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Preset 'OldPreset' deleted successfully." in captured.out
        mock_mgr.delete_preset.assert_called_once_with("OldPreset")


def test_cli_preset_delete_interactive_refusal(capsys, monkeypatch) -> None:
    """Verify cancellation of deletion via interactive prompt 'n'."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_manager_cls.return_value = mock_mgr
        monkeypatch.setattr("builtins.input", lambda prompt: "n")

        exit_code = main(["preset", "delete", "KeepPreset"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Operation cancelled" in captured.out
        mock_mgr.delete_preset.assert_not_called()
