"""Test di integrazione per i comandi dell'interfaccia a riga di comando (CLI).

Verifica il funzionamento end-to-end dei comandi:
- `current` (interrogazione dello stato attivo, inclusi Shell e color-scheme)
- `list` (elenco tabellare con filtri su gtk, icon, cursor, shell)
- `apply` (validazione preventiva, applicazione GSettings, override GTK4 e gestione errori)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.cli.main import format_table, main
from gnome_theme_manager.core.models import Theme, ThemeSet, ThemeType


def test_format_table():
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


def test_cli_current_success(capsys):
    """Verifica l'output del comando 'current' quando GSettings e Shell sono disponibili."""
    mock_theme_set = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus-Dark",
        cursor_theme="Capitaine",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )

    with patch("gnome_theme_manager.cli.main.GSettingsClient") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.get_current.return_value = mock_theme_set
        mock_client_instance.is_shell_theme_supported = True
        mock_client_cls.return_value = mock_client_instance

        exit_code = main(["current"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Temi attualmente attivi su GNOME:" in captured.out
        assert "Tema GTK (Applicazioni):  Nordic" in captured.out
        assert "Tema GNOME Shell:         Nordic" in captured.out


def test_cli_list_with_shell_type(capsys, tmp_path: Path):
    """Verifica il filtro --type shell nel comando 'list'."""
    mock_themes = [
        Theme(name="Nordic", theme_type=ThemeType.SHELL, path=tmp_path / "Nordic", is_user_level=True),
    ]

    with patch("gnome_theme_manager.cli.main.ThemeScanner") as mock_scanner_cls:
        mock_scanner_instance = MagicMock()
        mock_scanner_instance.scan_shell_themes.return_value = mock_themes
        mock_scanner_cls.return_value = mock_scanner_instance

        exit_code = main(["list", "--type", "shell"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Nordic" in captured.out
        assert "shell" in captured.out


def test_cli_apply_with_gtk_and_shell(capsys, tmp_path: Path):
    """Verifica l'applicazione simultanea di tema GTK, tema Shell e override GTK4."""
    valid_gtk = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=tmp_path / "Nordic",
        is_user_level=True,
    )
    valid_shell = Theme(
        name="Nordic",
        theme_type=ThemeType.SHELL,
        path=tmp_path / "Nordic",
        is_user_level=True,
    )

    with patch("gnome_theme_manager.cli.main.ThemeScanner") as mock_scanner_cls, \
         patch("gnome_theme_manager.cli.main.GSettingsClient") as mock_client_cls, \
         patch("gnome_theme_manager.cli.main.GTK4ThemeLinker") as mock_linker_cls:

        # Configurazione Scanner
        mock_scanner = MagicMock()
        def find_theme_mock(name: str, t_type: ThemeType):
            if t_type == ThemeType.GTK and name == "Nordic":
                return valid_gtk
            if t_type == ThemeType.SHELL and name == "Nordic":
                return valid_shell
            return None

        mock_scanner.find_theme.side_effect = find_theme_mock
        mock_scanner_cls.return_value = mock_scanner

        # Configurazione GSettings
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Configurazione Linker GTK4
        mock_linker = MagicMock()
        mock_linker.apply_override.return_value = True
        mock_linker_cls.return_value = mock_linker

        exit_code = main(["apply", "--gtk", "Nordic", "--shell", "Nordic"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Tema GTK impostato su:         Nordic" in captured.out
        assert "Tema GNOME Shell impostato su: Nordic" in captured.out
        assert "Override GTK4/Libadwaita applicato" in captured.out

        # Verifica chiamata GSettings apply
        mock_client.apply.assert_called_once()
        applied_set: ThemeSet = mock_client.apply.call_args[0][0]
        assert applied_set.gtk_theme == "Nordic"
        assert applied_set.shell_theme == "Nordic"

        # Verifica chiamata GTK4 linker
        mock_linker.apply_override.assert_called_once_with(valid_gtk.path)


def test_cli_apply_no_gtk4_override_flag(capsys, tmp_path: Path):
    """Verifica che il flag --no-gtk4-override disabiliti la chiamata al linker GTK4."""
    valid_gtk = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=tmp_path / "Nordic",
        is_user_level=True,
    )

    with patch("gnome_theme_manager.cli.main.ThemeScanner") as mock_scanner_cls, \
         patch("gnome_theme_manager.cli.main.GSettingsClient") as mock_client_cls, \
         patch("gnome_theme_manager.cli.main.GTK4ThemeLinker") as mock_linker_cls:

        mock_scanner = MagicMock()
        mock_scanner.find_theme.return_value = valid_gtk
        mock_scanner_cls.return_value = mock_scanner
        mock_client_cls.return_value = MagicMock()
        mock_linker = MagicMock()
        mock_linker_cls.return_value = mock_linker

        exit_code = main(["apply", "--gtk", "Nordic", "--no-gtk4-override"])
        _ = capsys.readouterr()

        assert exit_code == 0

        mock_linker.apply_override.assert_not_called()


def test_cli_apply_unified_theme(capsys, tmp_path: Path):
    """Verifica che il parametro --theme applichi sia GTK che GNOME Shell con lo stesso nome."""
    valid_gtk = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=tmp_path / "Nordic",
        is_user_level=True,
    )
    valid_shell = Theme(
        name="Nordic",
        theme_type=ThemeType.SHELL,
        path=tmp_path / "Nordic",
        is_user_level=True,
    )

    with (
        patch("gnome_theme_manager.cli.main.ThemeScanner") as mock_scanner_cls,
        patch("gnome_theme_manager.cli.main.GSettingsClient") as mock_client_cls,
        patch("gnome_theme_manager.cli.main.GTK4ThemeLinker") as mock_linker_cls,
    ):
        mock_scanner = MagicMock()
        # Ritorna valid_gtk quando cerca GTK, valid_shell quando cerca SHELL
        mock_scanner.find_theme.side_effect = lambda name, t_type: (
            valid_gtk if t_type == ThemeType.GTK else valid_shell
        )
        mock_scanner_cls.return_value = mock_scanner

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_linker = MagicMock()
        mock_linker.apply_override.return_value = True
        mock_linker_cls.return_value = mock_linker

        exit_code = main(["apply", "--theme", "Nordic"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Tema GTK impostato su:         Nordic" in captured.out
        assert "Tema GNOME Shell impostato su: Nordic" in captured.out
        assert "Override GTK4/Libadwaita applicato" in captured.out

        mock_client.apply.assert_called_once()
        applied_set: ThemeSet = mock_client.apply.call_args[0][0]
        assert applied_set.gtk_theme == "Nordic"
        assert applied_set.shell_theme == "Nordic"

