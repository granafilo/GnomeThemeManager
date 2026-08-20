# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for ThemeComposition and ThemeMixer (Task 2.1)."""

import json
from pathlib import Path

import pytest

from gnome_theme_manager.core.global_themes import GlobalThemeManager
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import ThemeSet
from gnome_theme_manager.core.theme_editor import ThemeComposition, ThemeMixer


def test_theme_composition_model() -> None:
    """Test ThemeComposition dataclass serialization and conversion."""
    comp = ThemeComposition(
        name="Nordic Custom",
        gtk3="Nordic",
        gtk4="Nordic-v40",
        shell="Nordic-Shell",
        icon="Papirus-Dark",
        cursor="Bibata-Modern-Classic",
        color_scheme="prefer-dark",
        description="A customized Nordic experience",
        user_composed=True,
    )

    data = comp.to_dict()
    assert data["name"] == "Nordic Custom"
    assert data["gtk3"] == "Nordic"
    assert data["gtk4"] == "Nordic-v40"
    assert data["shell"] == "Nordic-Shell"
    assert data["icon"] == "Papirus-Dark"
    assert data["cursor"] == "Bibata-Modern-Classic"
    assert data["color_scheme"] == "prefer-dark"
    assert data["user_composed"] is True

    reconstructed = ThemeComposition.from_dict(data)
    assert reconstructed.name == comp.name
    assert reconstructed.gtk4 == "Nordic-v40"
    assert reconstructed.user_composed is True

    theme_set = comp.to_theme_set()
    assert isinstance(theme_set, ThemeSet)
    assert theme_set.gtk_theme == "Nordic-v40"  # prefers gtk4 over gtk3
    assert theme_set.shell_theme == "Nordic-Shell"
    assert theme_set.icon_theme == "Papirus-Dark"
    assert theme_set.cursor_theme == "Bibata-Modern-Classic"
    assert theme_set.color_scheme == "prefer-dark"


def test_theme_composition_empty_and_fallback() -> None:
    """Test empty checking and gtk3 fallback when gtk4 is None."""
    empty_comp = ThemeComposition(name="Empty")
    assert empty_comp.is_empty() is True

    gtk3_only = ThemeComposition(name="Gtk3Only", gtk3="Adwaita")
    assert gtk3_only.is_empty() is False
    ts = gtk3_only.to_theme_set()
    assert ts.gtk_theme == "Adwaita"


def test_theme_mixer_save_and_ordering(tmp_path: Path) -> None:
    """Test ThemeMixer saves ThemeComposition as a Global Theme with origin='user' and user_composed=True."""
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

    gt_manager = GlobalThemeManager(
        bundled_dir=bundled_dir,
        state_file=state_file,
    )
    mixer = ThemeMixer(global_theme_manager=gt_manager)

    comp = ThemeComposition(
        name="Cyberpunk Sunset",
        gtk3="Sweet-Dark",
        gtk4="Sweet-Dark",
        icon="Candy-Icons",
        cursor="Sweet-Cursors",
        shell="Sweet-Dark",
        color_scheme="prefer-dark",
        description="Vibrant neon styling",
    )

    saved_theme = mixer.mix_and_save(comp)
    assert saved_theme.id == "user-cyberpunk-sunset"
    assert saved_theme.name == "Cyberpunk Sunset"
    assert saved_theme.origin == "user"
    assert saved_theme.is_bundled is False
    assert saved_theme.user_composed is True
    assert saved_theme.components.gtk_theme == "Sweet-Dark"
    assert saved_theme.components.icon_theme == "Candy-Icons"

    # Verify presence in list_global_themes at top
    all_themes = gt_manager.list_global_themes()
    assert all_themes[0].id == "user-cyberpunk-sunset"
    assert all_themes[0].user_composed is True
    assert all_themes[-1].origin == "bundled"


def test_theme_mixer_validation_errors(tmp_path: Path) -> None:
    """Test ThemeMixer raises ValueError on empty name or empty composition."""
    mixer = ThemeMixer(global_theme_manager=GlobalThemeManager(state_file=tmp_path / "state.json"))

    with pytest.raises(ValueError, match="cannot be empty"):
        mixer.mix_and_save(ThemeComposition(name=""))

    with pytest.raises(ValueError, match="Cannot save an empty theme composition"):
        mixer.mix_and_save(ThemeComposition(name="Valid Name"))


def test_theme_manager_save_theme_composition(tmp_path: Path) -> None:
    """Test ThemeManager facade saving composition."""
    state_file = tmp_path / "state" / "global_themes.json"
    gt_manager = GlobalThemeManager(state_file=state_file)
    mixer = ThemeMixer(global_theme_manager=gt_manager)
    tm = ThemeManager(global_themes=gt_manager, theme_mixer=mixer)

    comp = ThemeComposition(
        name="Workspace Pro",
        gtk4="Adwaita",
        icon="Papirus",
    )
    saved = tm.save_theme_composition(comp)
    assert saved.name == "Workspace Pro"
    assert saved.origin == "user"
    assert saved.user_composed is True
    assert gt_manager.get_global_theme("user-workspace-pro") is not None
