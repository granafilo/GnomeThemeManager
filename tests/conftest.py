"""Configurazione globale e fixture per pytest."""

from pathlib import Path

import pytest


@pytest.fixture
def dummy_user_theme_dir(tmp_path: Path) -> Path:
    """Crea una directory temporanea con una finta struttura di temi utente."""
    themes_dir = tmp_path / ".local" / "share" / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)

    # Creazione tema GTK dummy
    nordic_dir = themes_dir / "Nordic" / "gtk-3.0"
    nordic_dir.mkdir(parents=True, exist_ok=True)
    (nordic_dir / "gtk.css").write_text("/* dummy gtk css */")

    return themes_dir
