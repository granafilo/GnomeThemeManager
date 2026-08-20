# SPDX-License-Identifier: GPL-3.0-or-later

"""Test per verificare la coerenza della versione e l'efficacia dello script check_version_coherence.py."""

from pathlib import Path

from scripts.check_version_coherence import check_version


def test_check_version_coherence_on_current_repo() -> None:
    """Verifica che l'attuale stato del repository sia coerente e lo script ritorni 0."""
    exit_code = check_version()
    assert exit_code == 0


def test_check_version_fails_on_readme_mismatch(tmp_path: Path) -> None:
    """Verifica che un mismatch nel README.md provochi l'uscita con codice 1."""
    # Prepara albero dummy
    src_dir = tmp_path / "src" / "gnome_theme_manager"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "1.2.0"\n', encoding="utf-8")

    # README con versione discordante o marker mancante
    (tmp_path / "README.md").write_text("**Current release:** v1.0.0\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [1.2.0] - 2026-08-20\n", encoding="utf-8")

    exit_code = check_version(tmp_path)
    assert exit_code == 1


def test_check_version_fails_on_changelog_mismatch(tmp_path: Path) -> None:
    """Verifica che una discrepanza nella prima entry del CHANGELOG.md provochi l'uscita con codice 1."""
    src_dir = tmp_path / "src" / "gnome_theme_manager"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "1.2.0"\n', encoding="utf-8")

    (tmp_path / "README.md").write_text("**Current release:** v1.2.0\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [1.1.0] - 2026-08-20\n", encoding="utf-8")

    exit_code = check_version(tmp_path)
    assert exit_code == 1
