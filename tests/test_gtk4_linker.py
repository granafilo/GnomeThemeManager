# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per il modulo GTK4ThemeLinker.

Verifica la corretta creazione, sostituzione, rimozione e verifica di integrità
dei collegamenti simbolici (symlink) nella directory di configurazione utente ~/.config/gtk-4.0/.
"""

from pathlib import Path

import pytest

from gnome_theme_manager.core.gtk4_linker import GTK4ThemeLinker


@pytest.fixture
def mock_gtk4_environment(tmp_path: Path):
    """Crea una struttura fittizia di tema e di cartella ~/.config/gtk-4.0/ per i test."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    theme_dir = tmp_path / "themes" / "Nordic"

    # Creazione file tema con cartella gtk-4.0 e assets
    gtk4_dir = theme_dir / "gtk-4.0"
    gtk4_dir.mkdir(parents=True, exist_ok=True)
    (gtk4_dir / "gtk.css").write_text("/* nordic gtk4 css */")
    (gtk4_dir / "gtk-dark.css").write_text("/* nordic gtk4 dark css */")

    assets_dir = gtk4_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "bullet.png").write_text("dummy image data")

    return {
        "config_dir": config_dir,
        "theme_dir": theme_dir,
    }


def test_gtk4_linker_apply_success(mock_gtk4_environment):
    """Verifica che apply_override crei correttamente i symlink per gtk.css e assets."""
    env = mock_gtk4_environment
    linker = GTK4ThemeLinker(config_dir=env["config_dir"])

    success = linker.apply_override(env["theme_dir"])
    assert success is True

    target_css = env["config_dir"] / "gtk.css"
    target_dark_css = env["config_dir"] / "gtk-dark.css"
    target_assets = env["config_dir"] / "assets"

    assert target_css.exists()
    assert target_css.is_symlink() or target_css.is_file()
    assert "nordic gtk4 css" in target_css.read_text()

    assert target_dark_css.exists()
    assert target_assets.exists()


def test_gtk4_linker_apply_fallback_gtk3(tmp_path: Path):
    """Verifica che venga usata la cartella gtk-3.0 come fallback se gtk-4.0 non esiste."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    theme_dir = tmp_path / "themes" / "LegacyOnly"

    gtk3_dir = theme_dir / "gtk-3.0"
    gtk3_dir.mkdir(parents=True, exist_ok=True)
    (gtk3_dir / "gtk.css").write_text("/* fallback gtk3 css */")

    linker = GTK4ThemeLinker(config_dir=config_dir)
    success = linker.apply_override(theme_dir)

    assert success is True
    target_css = config_dir / "gtk.css"
    assert target_css.exists()
    assert "fallback gtk3 css" in target_css.read_text()


def test_gtk4_linker_apply_no_css(tmp_path: Path):
    """Verifica che apply_override ritorni False se non trova file CSS."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    theme_dir = tmp_path / "themes" / "EmptyTheme"
    theme_dir.mkdir(parents=True, exist_ok=True)

    linker = GTK4ThemeLinker(config_dir=config_dir)
    success = linker.apply_override(theme_dir)

    assert success is False
    assert not (config_dir / "gtk.css").exists()


def test_gtk4_linker_remove_override(mock_gtk4_environment):
    """Verifica che remove_override elimini i symlink precedentemente creati."""
    env = mock_gtk4_environment
    linker = GTK4ThemeLinker(config_dir=env["config_dir"])

    linker.apply_override(env["theme_dir"])
    assert (env["config_dir"] / "gtk.css").exists()

    linker.remove_override()
    assert not (env["config_dir"] / "gtk.css").exists()
    assert not (env["config_dir"] / "gtk-dark.css").exists()
    assert not (env["config_dir"] / "assets").exists()


def test_gtk4_linker_is_override_active_true(mock_gtk4_environment):
    """Verifica che is_override_active ritorni True quando i symlink sono validi."""
    env = mock_gtk4_environment
    linker = GTK4ThemeLinker(config_dir=env["config_dir"])

    assert linker.is_override_active() is False

    linker.apply_override(env["theme_dir"])
    assert linker.is_override_active() is True


def test_gtk4_linker_is_override_active_false_when_empty(tmp_path: Path):
    """Verifica che is_override_active ritorni False su una directory vuota o inesistente."""
    config_dir = tmp_path / "non_existent_gtk4"
    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.is_override_active() is False


def test_gtk4_linker_is_override_active_false_when_dangling_symlink(tmp_path: Path):
    """Verifica che is_override_active ritorni False se gtk.css è un symlink rotto/dangling."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    config_dir.mkdir(parents=True, exist_ok=True)

    target_css = config_dir / "gtk.css"
    non_existent_source = tmp_path / "deleted_theme" / "gtk.css"
    target_css.symlink_to(non_existent_source)

    assert target_css.is_symlink()
    assert not target_css.exists()  # dangling symlink

    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.is_override_active() is False


def test_gtk4_linker_is_override_active_false_when_secondary_symlink_dangling(tmp_path: Path):
    """Verifica che is_override_active ritorni False se un file opzionale collegato è dangling."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    config_dir.mkdir(parents=True, exist_ok=True)

    # gtk.css valido
    valid_css_source = tmp_path / "valid_theme" / "gtk.css"
    valid_css_source.parent.mkdir(parents=True, exist_ok=True)
    valid_css_source.write_text("/* valid */")
    (config_dir / "gtk.css").symlink_to(valid_css_source)

    # gtk-dark.css rotto
    (config_dir / "gtk-dark.css").symlink_to(tmp_path / "deleted" / "gtk-dark.css")

    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.is_override_active() is False
