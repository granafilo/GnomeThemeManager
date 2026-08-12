"""Test di integrazione CLI per i comandi `install` e `uninstall`."""

from pathlib import Path

import pytest

from gnome_theme_manager.cli.main import main
from tests.test_installer import create_mock_zip


def test_cli_install_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test di esecuzione del comando `install` da CLI con successo."""
    user_themes = tmp_path / "themes"
    user_icons = tmp_path / "icons"

    # Mock dei percorsi utente in ThemeInstaller
    monkeypatch.setattr("gnome_theme_manager.core.installer.USER_THEMES_DIRS", [user_themes])
    monkeypatch.setattr("gnome_theme_manager.core.installer.USER_ICONS_DIRS", [user_icons])

    archive_file = tmp_path / "CLITheme.zip"
    create_mock_zip(archive_file, {"CLITheme/gtk-3.0/gtk.css": "/* CLI */"})

    exit_code = main(["install", "-f", str(archive_file)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Installazione completata con successo" in captured.out
    assert "CLITheme" in captured.out
    assert (user_themes / "CLITheme" / "gtk-3.0" / "gtk.css").exists()


def test_cli_install_bad_archive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test di gestione errore con archivio corrotto da CLI."""
    bad_archive = tmp_path / "corrupt.zip"
    bad_archive.write_bytes(b"INVALID DATA")

    exit_code = main(["install", "-f", str(bad_archive)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[ERRORE ESTRAZIONE ARCHIVIO]" in captured.err


def test_cli_uninstall_success_with_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test disinstallazione via CLI con flag `-y` (senza prompt)."""
    user_themes = tmp_path / "themes"
    theme_dir = user_themes / "ThemeToUninstall"
    (theme_dir / "gtk-3.0").mkdir(parents=True)

    monkeypatch.setattr("gnome_theme_manager.core.installer.USER_THEMES_DIRS", [user_themes])

    exit_code = main(["uninstall", "-n", "ThemeToUninstall", "-t", "gtk", "-y"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "disinstallato con successo" in captured.out
    assert not theme_dir.exists()


def test_cli_uninstall_interactive_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test annullamento disinstallazione tramite prompt interattivo 'n'."""
    user_themes = tmp_path / "themes"
    theme_dir = user_themes / "ThemeToKeep"
    (theme_dir / "gtk-3.0").mkdir(parents=True)

    monkeypatch.setattr("gnome_theme_manager.core.installer.USER_THEMES_DIRS", [user_themes])
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    exit_code = main(["uninstall", "-n", "ThemeToKeep", "-t", "gtk"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Operazione annullata" in captured.out
    assert theme_dir.exists()


def test_cli_uninstall_non_existent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test disinstallazione di tema non esistente via CLI."""
    user_themes = tmp_path / "themes"
    user_themes.mkdir(parents=True)

    monkeypatch.setattr("gnome_theme_manager.core.installer.USER_THEMES_DIRS", [user_themes])

    exit_code = main(["uninstall", "-n", "GhostTheme", "-t", "gtk", "-y"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "[ERRORE TEMA]" in captured.err
