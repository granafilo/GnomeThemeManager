# SPDX-License-Identifier: GPL-3.0-or-later

"""Test di integrazione per i comandi dell'interfaccia a riga di comando (CLI).

Verifica il funzionamento end-to-end dei comandi:
- `current` (interrogazione dello stato attivo, inclusi Shell e color-scheme)
- `list` (elenco tabellare con filtri su gtk, icon, cursor, shell)
- `apply` (validazione preventiva, applicazione GSettings, override GTK4 e gestione errori)
- `preset` (list, save, apply, delete)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.cli.main import format_table, main
from gnome_theme_manager.core.models import ApplyResult, SystemStatus, Theme, ThemeSet, ThemeType


def test_format_table() -> None:
    """Verifica la generazione della tabella ASCII."""
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
    """Verifica l'output del comando 'current' quando GSettings e Shell sono disponibili."""
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
    """Verifica il filtro --type shell nel comando 'list'."""
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
    """Verifica l'applicazione simultanea di tema GTK, tema Shell e override GTK4."""
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
    """Verifica che il flag --no-gtk4-override disabiliti l'override GTK4."""
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
    """Verifica che il parametro --theme applichi sia GTK che Shell."""
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
    """Verifica il comando 'preset list' in assenza di preset."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_mgr.list_presets.return_value = []
        mock_manager_cls.return_value = mock_mgr

        exit_code = main(["preset", "list"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "No presets saved." in captured.out


def test_cli_preset_list_with_items(capsys) -> None:
    """Verifica il comando 'preset list' con preset memorizzati."""
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
    """Verifica il comando 'preset save <nome>'."""
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
    """Verifica il comando 'preset apply <nome>'."""
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
    """Verifica il comando 'preset delete <nome> -y' (senza prompt)."""
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
    """Verifica l'annullamento della cancellazione tramite prompt interattivo 'n'."""
    with patch("gnome_theme_manager.cli.main.ThemeManager") as mock_manager_cls:
        mock_mgr = MagicMock()
        mock_manager_cls.return_value = mock_mgr
        monkeypatch.setattr("builtins.input", lambda prompt: "n")

        exit_code = main(["preset", "delete", "KeepPreset"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Operation cancelled" in captured.out
        mock_mgr.delete_preset.assert_not_called()

