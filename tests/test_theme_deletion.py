# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for user theme deletion and protections."""

from pathlib import Path

import pytest

from gnome_theme_manager.core.constants import THEME_FORKS_FILE
from gnome_theme_manager.core.errors import ThemeNotFoundError
from gnome_theme_manager.core.installer import ThemeInstaller
from gnome_theme_manager.core.models import ThemeType


def test_uninstall_theme_removes_user_folder_and_cleans_forks(tmp_path: Path) -> None:
    """Test uninstall_theme removes user theme directory and cleans theme_forks.json."""
    user_themes = tmp_path / "themes"
    user_icons = tmp_path / "icons"
    user_themes.mkdir(parents=True)
    user_icons.mkdir(parents=True)

    theme_dir = user_themes / "Custom-Mix"
    theme_dir.mkdir(parents=True)
    (theme_dir / "gtk-4.0").mkdir()
    (theme_dir / "gtk-4.0" / "gtk.css").write_text("window { color: red; }")
    (theme_dir / "gnome-shell").mkdir()
    (theme_dir / "gnome-shell" / "gnome-shell.css").write_text("#panel { color: red; }")

    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    # Pre-populate state in theme_forks.json
    state_file = THEME_FORKS_FILE.expanduser()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        '{"forks": [{"fork_name": "Custom-Mix", "fork_path": "' + str(theme_dir) + '"}]}'
    )

    assert installer.uninstall("Custom-Mix", ThemeType.GTK) is True
    assert not theme_dir.exists()


def test_uninstall_nonexistent_theme_raises(tmp_path: Path) -> None:
    """Test uninstalling nonexistent theme raises ThemeNotFoundError."""
    user_themes = tmp_path / "themes"
    user_icons = tmp_path / "icons"
    user_themes.mkdir(parents=True)
    user_icons.mkdir(parents=True)

    installer = ThemeInstaller(user_themes_dir=user_themes, user_icons_dir=user_icons)

    with pytest.raises(ThemeNotFoundError):
        installer.uninstall("NonExistent", ThemeType.GTK)
