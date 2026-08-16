# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GlobalTheme and GlobalThemeManager."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.errors import ThemeNotFoundError
from gnome_theme_manager.core.global_themes import GlobalTheme, GlobalThemeManager
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import ApplyResult, ThemeSet


def test_global_theme_model_serialization() -> None:
    """Test GlobalTheme to_dict and from_dict."""
    ts = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus-Dark",
        cursor_theme="Bibata-Modern-Classic",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )
    theme = GlobalTheme(
        id="nordic-night",
        name="Nordic Night",
        description="Nordic style theme",
        components=ts,
        author="EliverLara",
        is_bundled=True,
        tags=["dark", "nordic"],
    )

    data = theme.to_dict()
    assert data["id"] == "nordic-night"
    assert data["name"] == "Nordic Night"
    assert data["author"] == "EliverLara"
    assert data["is_bundled"] is True
    assert data["tags"] == ["dark", "nordic"]
    assert data["components"]["gtk_theme"] == "Nordic"

    reconstructed = GlobalTheme.from_dict(data, is_bundled=True)
    assert reconstructed.id == theme.id
    assert reconstructed.name == theme.name
    assert reconstructed.components.gtk_theme == "Nordic"
    assert reconstructed.components.icon_theme == "Papirus-Dark"
    assert reconstructed.is_bundled is True


def test_global_theme_manager_load_bundled_themes(tmp_path: Path) -> None:
    """Test loading bundled global themes from JSON files."""
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir(parents=True)

    theme1 = {
        "id": "theme-1",
        "name": "Theme One",
        "description": "First theme",
        "components": {
            "gtk3": "Yaru",
            "icons": "Yaru",
        },
    }
    (bundled_dir / "theme1.json").write_text(json.dumps(theme1), encoding="utf-8")

    state_file = tmp_path / "state" / "global_themes.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"global_themes": []}))

    mgr = GlobalThemeManager(
        bundled_dir=bundled_dir,
        user_presets_dir=tmp_path / "presets",
        state_file=state_file,
    )
    themes = [t for t in mgr.list_global_themes() if t.id == "theme-1"]

    assert len(themes) == 1
    assert themes[0].id == "theme-1"
    assert themes[0].name == "Theme One"
    assert themes[0].is_bundled is True
    assert themes[0].components.gtk_theme == "Yaru"
    assert themes[0].components.icon_theme == "Yaru"


def test_global_theme_manager_load_user_presets(tmp_path: Path) -> None:
    """Test loading user presets as global themes."""
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir(parents=True)

    presets_data = {
        "presets": [
            {
                "name": "Custom Workspace",
                "components": {
                    "gtk3": "Adwaita",
                    "icons": "Papirus",
                    "cursors": "Adwaita",
                    "shell": "Adwaita",
                },
            }
        ]
    }
    (presets_dir / "presets.json").write_text(json.dumps(presets_data), encoding="utf-8")

    state_file = tmp_path / "state" / "global_themes.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"global_themes": []}))

    mgr = GlobalThemeManager(
        bundled_dir=tmp_path / "empty_bundled",
        user_presets_dir=presets_dir,
        state_file=state_file,
    )
    themes = [t for t in mgr.list_global_themes() if t.name == "Custom Workspace"]

    assert len(themes) == 1
    assert themes[0].name == "Custom Workspace"
    assert themes[0].is_bundled is False
    assert themes[0].components.gtk_theme == "Adwaita"
    assert themes[0].components.icon_theme == "Papirus"


def test_global_theme_manager_get_global_theme(tmp_path: Path) -> None:
    """Test retrieving global theme by id or name."""
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir(parents=True)

    theme1 = {
        "id": "theme-1",
        "name": "Theme One",
        "description": "First theme",
        "components": {"gtk3": "Yaru"},
    }
    (bundled_dir / "theme1.json").write_text(json.dumps(theme1), encoding="utf-8")

    mgr = GlobalThemeManager(bundled_dir=bundled_dir, user_presets_dir=tmp_path / "presets")
    t_by_id = mgr.get_global_theme("theme-1")
    assert t_by_id is not None
    assert t_by_id.name == "Theme One"

    t_by_name = mgr.get_global_theme("Theme One")
    assert t_by_name is not None
    assert t_by_name.id == "theme-1"

    assert mgr.get_global_theme("nonexistent") is None


def test_theme_manager_apply_global_theme(tmp_path: Path) -> None:
    """Test ThemeManager facade applying global theme."""
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir(parents=True)

    theme_data = {
        "id": "solarized",
        "name": "Solarized",
        "description": "Solarized desktop theme",
        "components": {
            "gtk3": "Solarized-Dark",
            "icons": "Solarized-Icons",
            "cursors": "Adwaita",
            "shell": "Solarized-Shell",
            "color_scheme": "prefer-dark",
        },
    }
    (bundled_dir / "solarized.json").write_text(json.dumps(theme_data), encoding="utf-8")

    gt_mgr = GlobalThemeManager(bundled_dir=bundled_dir, user_presets_dir=tmp_path / "presets")

    mock_apply_themes = MagicMock(return_value=ApplyResult(gtk_theme="Solarized-Dark"))
    tm = ThemeManager(global_themes=gt_mgr)
    tm.apply_themes = mock_apply_themes  # type: ignore[method-assign]

    res = tm.apply_global_theme("solarized", propagate_sandbox=True)
    assert res.gtk_theme == "Solarized-Dark"
    assert mock_apply_themes.call_count == 1

    # Check components passed
    called_args, called_kwargs = mock_apply_themes.call_args
    passed_theme_set: ThemeSet = called_args[0]
    assert passed_theme_set.gtk_theme == "Solarized-Dark"
    assert passed_theme_set.icon_theme == "Solarized-Icons"
    assert passed_theme_set.color_scheme == "prefer-dark"
    assert called_kwargs.get("propagate_sandbox") is True


def test_theme_manager_apply_global_theme_not_found() -> None:
    """Test apply_global_theme raises ThemeNotFoundError for unknown theme."""
    tm = ThemeManager()
    with pytest.raises(ThemeNotFoundError):
        tm.apply_global_theme("unknown-theme-xyz")


def test_global_theme_manager_auto_generates_from_installed_themes(tmp_path: Path) -> None:
    """Test that when global_themes.json is missing or empty, it generates 3 themes from scanner."""
    state_file = tmp_path / "state" / "global_themes.json"
    scanner = MagicMock()
    # Mock themes discovered on system
    from gnome_theme_manager.core.models import Theme, ThemeType

    scanner.list_themes.side_effect = lambda t: {
        ThemeType.GTK: [
            Theme(
                name="Yaru",
                theme_type=ThemeType.GTK,
                path=Path("/usr/share/themes/Yaru"),
                is_user_level=False,
            ),
            Theme(
                name="Yaru-dark",
                theme_type=ThemeType.GTK,
                path=Path("/usr/share/themes/Yaru-dark"),
                is_user_level=False,
            ),
        ],
        ThemeType.ICON: [
            Theme(
                name="Yaru",
                theme_type=ThemeType.ICON,
                path=Path("/usr/share/icons/Yaru"),
                is_user_level=False,
            ),
        ],
        ThemeType.CURSOR: [
            Theme(
                name="Yaru",
                theme_type=ThemeType.CURSOR,
                path=Path("/usr/share/icons/Yaru"),
                is_user_level=False,
            ),
        ],
        ThemeType.SHELL: [
            Theme(
                name="Yaru",
                theme_type=ThemeType.SHELL,
                path=Path("/usr/share/themes/Yaru"),
                is_user_level=False,
            ),
        ],
    }.get(t, [])

    mgr = GlobalThemeManager(
        state_file=state_file,
        scanner=scanner,
        current_themes_provider=lambda: ThemeSet(
            gtk_theme="Yaru", icon_theme="Yaru", cursor_theme="Yaru", shell_theme="Yaru"
        ),
    )

    themes = mgr.list_global_themes()
    assert len(themes) >= 2
    assert state_file.is_file()

    # Verify that components match real installed themes
    dark_theme = mgr.get_global_theme("auto-dark")
    assert dark_theme is not None
    assert dark_theme.components.gtk_theme in ("Yaru-dark", "Yaru")
    assert dark_theme.components.icon_theme == "Yaru"


def test_global_theme_manager_save_delete_and_ordering(tmp_path: Path) -> None:
    """Test saving user global theme puts it on top, delete works, and bundled themes cannot be deleted."""
    state_file = tmp_path / "state" / "global_themes.json"
    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir(parents=True)

    bundled_theme = {
        "id": "theme-bundled",
        "name": "Bundled Classic",
        "origin": "bundled",
        "components": {"gtk3": "Yaru"},
    }
    (bundled_dir / "bundled.json").write_text(json.dumps(bundled_theme), encoding="utf-8")

    mgr = GlobalThemeManager(
        bundled_dir=bundled_dir,
        state_file=state_file,
    )

    # Save User Theme 1
    t1 = mgr.save_global_theme(
        "My Work Setup",
        ThemeSet(gtk_theme="Adwaita", icon_theme="Papirus"),
    )
    assert t1.origin == "user"
    assert t1.id == "user-my-work-setup"

    # Save User Theme 2 (more recent)
    t2 = mgr.save_global_theme(
        "My Gaming Setup",
        ThemeSet(gtk_theme="Nordic", icon_theme="Papirus-Dark"),
    )
    assert t2.origin == "user"

    themes = mgr.list_global_themes()
    # Ordering: User themes on top (Gaming Setup most recent, then Work Setup), Bundled at bottom
    user_names = [t.name for t in themes if t.origin == "user"]
    bundled_names = [t.name for t in themes if t.origin == "bundled"]

    assert user_names[0] == "My Gaming Setup"
    assert user_names[1] == "My Work Setup"
    assert "Bundled Classic" in bundled_names

    # Delete user theme
    assert mgr.delete_global_theme("user-my-work-setup") is True
    assert mgr.get_global_theme("user-my-work-setup") is None

    # Bundled themes cannot be deleted
    with pytest.raises(ValueError):
        mgr.delete_global_theme("theme-bundled")
