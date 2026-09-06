# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for filesystem scanner (ThemeScanner).

Verifies correct detection of:
- GTK themes (via gtk-X.0 directories or index.theme)
- Icon themes (via resolution/scalable directories or index.theme)
- Cursor themes (via cursors/ directory)
- GNOME Shell themes (via gnome-shell/ directory)
- Hybrid folders (themes containing both icons and cursors)
- Precedence between user and system directories (User > System)
- Filters such as 'user_only' and targeted search with 'find_theme'
"""

from pathlib import Path

import pytest

from gnome_theme_manager.core.models import ThemeType
from gnome_theme_manager.core.scanner import ThemeScanner


@pytest.fixture
def mock_filesystem_structure(tmp_path: Path):
    """Create a temporary directory and file hierarchy simulating the GNOME environment."""
    # 1. User Directories
    user_themes = tmp_path / "user" / "themes"
    user_icons = tmp_path / "user" / "icons"
    user_themes.mkdir(parents=True, exist_ok=True)
    user_icons.mkdir(parents=True, exist_ok=True)

    # User GTK + Shell Theme (e.g. "Nordic" with gtk-3.0 and gnome-shell/)
    nordic = user_themes / "Nordic"
    (nordic / "gtk-3.0").mkdir(parents=True, exist_ok=True)
    (nordic / "gtk-3.0" / "gtk.css").write_text("/* dummy */")
    (nordic / "gnome-shell").mkdir(parents=True, exist_ok=True)
    (nordic / "gnome-shell" / "gnome-shell.css").write_text("/* shell css */")

    # User Icon Theme (e.g. "Papirus-Dark" with index.theme)
    papirus_icon = user_icons / "Papirus-Dark"
    papirus_icon.mkdir(parents=True, exist_ok=True)
    (papirus_icon / "index.theme").write_text(
        "[Icon Theme]\nName=Papirus-Dark\nDirectories=48x48\n"
    )
    (papirus_icon / "48x48").mkdir(parents=True, exist_ok=True)

    # User Cursor Theme (e.g. "Capitaine" with cursors/)
    capitaine_cursor = user_icons / "Capitaine-Cursors"
    capitaine_cursor.mkdir(parents=True, exist_ok=True)
    (capitaine_cursor / "cursors").mkdir(parents=True, exist_ok=True)

    # 2. System Directories
    sys_themes = tmp_path / "sys" / "themes"
    sys_icons = tmp_path / "sys" / "icons"
    sys_themes.mkdir(parents=True, exist_ok=True)
    sys_icons.mkdir(parents=True, exist_ok=True)

    # System GTK Theme (e.g. "Adwaita" with gtk-4.0)
    adwaita_gtk = sys_themes / "Adwaita" / "gtk-4.0"
    adwaita_gtk.mkdir(parents=True, exist_ok=True)

    # System GTK Theme with same name as User theme ("Nordic") to test precedence
    nordic_sys = sys_themes / "Nordic"
    (nordic_sys / "gtk-3.0").mkdir(parents=True, exist_ok=True)
    (nordic_sys / "gnome-shell").mkdir(parents=True, exist_ok=True)

    # System Hybrid Theme (e.g. "Yaru" containing both icons and cursors/ directory)
    yaru_hybrid = sys_icons / "Yaru"
    yaru_hybrid.mkdir(parents=True, exist_ok=True)
    (yaru_hybrid / "index.theme").write_text("[Icon Theme]\nName=Yaru\n")
    (yaru_hybrid / "scalable").mkdir(parents=True, exist_ok=True)
    (yaru_hybrid / "cursors").mkdir(parents=True, exist_ok=True)

    return {
        "user_themes": user_themes,
        "user_icons": user_icons,
        "sys_themes": sys_themes,
        "sys_icons": sys_icons,
    }


def test_scanner_initialization():
    """Verify that ThemeScanner instantiates properly with custom or default paths."""
    scanner = ThemeScanner()
    assert len(scanner.user_theme_dirs) >= 1
    assert len(scanner.system_theme_dirs) >= 1

    custom_dir = [Path("/custom/themes")]
    scanner_custom = ThemeScanner(user_theme_dirs=custom_dir)
    assert scanner_custom.user_theme_dirs == custom_dir


def test_scan_gtk_themes(mock_filesystem_structure):
    """Verify scanning of GTK themes and proper application of precedence."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    gtk_themes = scanner.scan_gtk_themes()
    names = [t.name for t in gtk_themes]

    assert "Nordic" in names
    assert "Adwaita" in names

    nordic_theme = next(t for t in gtk_themes if t.name == "Nordic")
    assert nordic_theme.is_user_level is True
    assert nordic_theme.path == fs["user_themes"] / "Nordic"

    adwaita_theme = next(t for t in gtk_themes if t.name == "Adwaita")
    assert adwaita_theme.is_user_level is False


def test_scan_shell_themes(mock_filesystem_structure):
    """Verify scanning of themes for GNOME Shell."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    shell_themes = scanner.scan_shell_themes()
    names = [t.name for t in shell_themes]

    assert "Nordic" in names
    nordic_shell = next(t for t in shell_themes if t.name == "Nordic")
    assert nordic_shell.is_user_level is True
    assert nordic_shell.theme_type == ThemeType.SHELL


def test_scan_icon_and_cursor_themes(mock_filesystem_structure):
    """Verify separate scanning of icons and cursors, including handling of hybrid directories."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    # Icons scan
    icon_themes = scanner.scan_icon_themes()
    icon_names = [t.name for t in icon_themes]
    assert "Papirus-Dark" in icon_names
    assert "Yaru" in icon_names
    assert "Capitaine-Cursors" not in icon_names

    # Cursors scan
    cursor_themes = scanner.scan_cursor_themes()
    cursor_names = [t.name for t in cursor_themes]
    assert "Capitaine-Cursors" in cursor_names
    assert "Yaru" in cursor_names
    assert "Papirus-Dark" not in cursor_names


def test_scan_all(mock_filesystem_structure):
    """Verify that scan_all returns the complete set of all themes (including Shell)."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    all_themes = scanner.scan_all()
    # Expected: Nordic (GTK), Adwaita (GTK), Papirus-Dark (ICON), Yaru (ICON), Yaru (CURSOR), Capitaine (CURSOR), Nordic (SHELL)
    assert len(all_themes) == 7


def test_scan_user_only(mock_filesystem_structure):
    """Verify that user_only=True excludes all system themes."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    user_all = scanner.scan_all(user_only=True)
    for theme in user_all:
        assert theme.is_user_level is True

    user_names = [t.name for t in user_all]
    assert "Nordic" in user_names
    assert "Papirus-Dark" in user_names
    assert "Capitaine-Cursors" in user_names
    assert "Adwaita" not in user_names
    assert "Yaru" not in user_names


def test_find_theme(mock_filesystem_structure):
    """Verify looking up a theme by name and type."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    # Existing GTK theme
    gtk_theme = scanner.find_theme("Nordic", ThemeType.GTK)
    assert gtk_theme is not None
    assert gtk_theme.name == "Nordic"
    assert gtk_theme.theme_type == ThemeType.GTK

    # Existing Shell theme
    shell_theme = scanner.find_theme("Nordic", ThemeType.SHELL)
    assert shell_theme is not None
    assert shell_theme.name == "Nordic"
    assert shell_theme.theme_type == ThemeType.SHELL

    # Looked up with wrong type -> must return None
    wrong_type = scanner.find_theme("Capitaine-Cursors", ThemeType.GTK)
    assert wrong_type is None

    # Non-existent theme -> must return None
    non_existent = scanner.find_theme("Fantasma", ThemeType.GTK)
    assert non_existent is None


def test_scanner_nonexistent_directory(tmp_path: Path):
    """Verify that non-existent directories are handled without raising exceptions."""
    non_existent = tmp_path / "does_not_exist"
    scanner = ThemeScanner(
        user_theme_dirs=[non_existent],
        user_icon_dirs=[non_existent],
        system_theme_dirs=[non_existent],
        system_icon_dirs=[non_existent],
    )

    assert scanner.scan_all() == []
    assert scanner.scan_gtk_themes() == []
    assert scanner.scan_icon_themes() == []
    assert scanner.scan_cursor_themes() == []
    assert scanner.scan_shell_themes() == []


def test_dynamic_xdg_paths_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify that XDG_DATA_HOME and XDG_DATA_DIRS environment variables are respected dynamically."""
    custom_xdg_home = tmp_path / "custom_data_home"
    custom_xdg_dirs = f"{tmp_path}/custom_sys1:{tmp_path}/custom_sys2"

    monkeypatch.setenv("XDG_DATA_HOME", str(custom_xdg_home))
    monkeypatch.setenv("XDG_DATA_DIRS", custom_xdg_dirs)

    scanner = ThemeScanner()

    # Check user themes
    assert custom_xdg_home / "themes" in scanner.user_theme_dirs
    assert Path.home() / ".themes" in scanner.user_theme_dirs

    # Check user icons
    assert custom_xdg_home / "icons" in scanner.user_icon_dirs
    assert Path.home() / ".icons" in scanner.user_icon_dirs

    # Check system themes
    assert tmp_path / "custom_sys1" / "themes" in scanner.system_theme_dirs
    assert tmp_path / "custom_sys2" / "themes" in scanner.system_theme_dirs
    assert Path("/usr/share/themes") in scanner.system_theme_dirs

    # Check system icons
    assert tmp_path / "custom_sys1" / "icons" in scanner.system_icon_dirs
    assert tmp_path / "custom_sys2" / "icons" in scanner.system_icon_dirs
    assert Path("/usr/share/icons") in scanner.system_icon_dirs


def test_scanner_invalid_index_theme(tmp_path: Path):
    """Verify that themes with corrupted/missing index.theme are marked as invalid without crashing the scanner."""
    user_themes = tmp_path / "themes"
    user_themes.mkdir()

    # 1. Theme with corrupted index.theme (cannot parse as INI)
    bad_theme = user_themes / "CorruptedTheme"
    bad_theme.mkdir()
    (bad_theme / "index.theme").write_text("corrupted content without sections or key-value pairs")

    scanner = ThemeScanner(
        user_theme_dirs=[user_themes], user_icon_dirs=[], system_theme_dirs=[], system_icon_dirs=[]
    )
    themes = scanner.scan_gtk_themes()
    assert len(themes) == 1
    assert themes[0].name == "CorruptedTheme"
    assert themes[0].invalid is True


def test_scanner_inheritance_chain(tmp_path: Path):
    """Verify recursive inheritance chain resolution from index.theme up to max depth 5."""
    user_themes = tmp_path / "themes"
    user_themes.mkdir()

    # Create 6 themes in a chain: Theme5 -> Theme4 -> Theme3 -> Theme2 -> Theme1 -> Theme0
    for i in range(6):
        theme_dir = user_themes / f"Theme{i}"
        theme_dir.mkdir()
        inherits = f"Theme{i - 1}" if i > 0 else ""
        (theme_dir / "index.theme").write_text(
            f"[Desktop Entry]\nName=Theme{i}\nInherits={inherits}\n"
        )

    scanner = ThemeScanner(
        user_theme_dirs=[user_themes], user_icon_dirs=[], system_theme_dirs=[], system_icon_dirs=[]
    )

    # For Theme5 (depth 5), chain stops at Theme1 (Theme5, 4, 3, 2, 1) and excludes Theme0
    theme5 = scanner.find_theme("Theme5", ThemeType.GTK)
    assert theme5 is not None
    assert "Theme4" in theme5.inheritance_chain
    assert "Theme1" in theme5.inheritance_chain
    assert "Theme0" not in theme5.inheritance_chain
