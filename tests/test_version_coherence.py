# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests to verify version coherence and the effectiveness of the check_version_coherence.py script."""

from pathlib import Path

from scripts.check_version_coherence import check_version


def test_check_version_coherence_on_current_repo() -> None:
    """Verify that current repository state is coherent and the script returns 0."""
    exit_code = check_version()
    assert exit_code == 0


def test_check_version_fails_on_readme_mismatch(tmp_path: Path) -> None:
    """Verify that a mismatch in README.md causes exit with code 1."""
    # Prepare dummy tree
    src_dir = tmp_path / "src" / "gnome_theme_manager"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "1.2.0"\n', encoding="utf-8")

    # README with mismatched version or missing marker
    (tmp_path / "README.md").write_text("**Current release:** v1.0.0\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [1.2.0] - 2026-08-20\n", encoding="utf-8")

    exit_code = check_version(tmp_path)
    assert exit_code == 1


def test_check_version_fails_on_changelog_mismatch(tmp_path: Path) -> None:
    """Verify that a discrepancy in the first CHANGELOG.md entry causes exit with code 1."""
    src_dir = tmp_path / "src" / "gnome_theme_manager"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('__version__ = "1.2.0"\n', encoding="utf-8")

    (tmp_path / "README.md").write_text("**Current release:** v1.2.0\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [1.1.0] - 2026-08-20\n", encoding="utf-8")

    exit_code = check_version(tmp_path)
    assert exit_code == 1
