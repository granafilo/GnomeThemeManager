# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for ThemeDetector in theme_snap_manager."""

from pathlib import Path

from gnome_theme_manager.core.theme_snap_manager.detector import ThemeDetector


def test_theme_detector_compatible(tmp_path: Path) -> None:
    """Test detector finding theme in mocked gtk-common-themes paths."""
    themes_dir = tmp_path / "share" / "themes"
    icons_dir = tmp_path / "share" / "icons"
    sounds_dir = tmp_path / "share" / "sounds"

    (themes_dir / "Yaru").mkdir(parents=True)
    (icons_dir / "Yaru").mkdir(parents=True)

    detector = ThemeDetector(themes_path=themes_dir, icons_path=icons_dir, sounds_path=sounds_dir)
    is_compat, slots = detector.check_theme_compatibility("Yaru")

    assert is_compat is True
    assert "gtk-3-themes" in slots
    assert "icon-themes" in slots
    assert "sound-themes" not in slots


def test_theme_detector_not_compatible(tmp_path: Path) -> None:
    """Test detector returning false when theme does not exist in common themes."""
    themes_dir = tmp_path / "share" / "themes"
    icons_dir = tmp_path / "share" / "icons"
    sounds_dir = tmp_path / "share" / "sounds"
    themes_dir.mkdir(parents=True)

    detector = ThemeDetector(themes_path=themes_dir, icons_path=icons_dir, sounds_path=sounds_dir)
    is_compat, slots = detector.check_theme_compatibility("MyCustomTheme")

    assert is_compat is False
    assert len(slots) == 0


def test_theme_detector_empty_name(tmp_path: Path) -> None:
    """Test detector handling empty or whitespace theme name."""
    detector = ThemeDetector(themes_path=tmp_path, icons_path=tmp_path, sounds_path=tmp_path)
    is_compat, slots = detector.check_theme_compatibility("   ")
    assert is_compat is False
    assert slots == []
