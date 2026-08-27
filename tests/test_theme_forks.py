# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Theme Fork and Color Override manager (Task 2.4)."""

from pathlib import Path

import pytest

from gnome_theme_manager.core.theme_forks import (
    ThemeFork,
    ThemeForkManager,
)


def test_theme_fork_model_serialization() -> None:
    """Test ThemeFork serialization to/from dict."""
    fork = ThemeFork(
        fork_name="Nordic-Custom",
        base_theme_name="Nordic",
        fork_path=Path("/home/user/.themes/Nordic-Custom-gtk4"),
        colors={
            "theme_fg_color": "#ffffff",
            "theme_bg_color": "#1e1e2e",
            "theme_selected_bg_color": "#cba6f7",
            "theme_selected_fg_color": "#11111b",
        },
        created_at="2026-08-20T20:00:00Z",
    )
    d = fork.to_dict()
    assert d["fork_name"] == "Nordic-Custom"
    assert d["base_theme_name"] == "Nordic"
    assert d["fork_path"] == "/home/user/.themes/Nordic-Custom-gtk4"
    assert d["colors"]["theme_bg_color"] == "#1e1e2e"

    reconstructed = ThemeForkManager.fork_from_dict(d)
    assert reconstructed.fork_name == fork.fork_name
    assert reconstructed.base_theme_name == fork.base_theme_name
    assert reconstructed.fork_path == fork.fork_path
    assert reconstructed.colors == fork.colors


def test_create_theme_fork_copies_and_overrides_colors(tmp_path: Path) -> None:
    """Test creating a fork copies base theme and modifies @define-color definitions in CSS."""
    # Setup base theme
    base_dir = tmp_path / "usr_share_themes" / "Adwaita"
    gtk4_dir = base_dir / "gtk-4.0"
    gtk3_dir = base_dir / "gtk-3.0"
    gtk4_dir.mkdir(parents=True)
    gtk3_dir.mkdir(parents=True)

    (gtk4_dir / "gtk.css").write_text(
        """
        @define-color theme_fg_color #000000;
        @define-color theme_bg_color #ffffff;
        @define-color theme_selected_bg_color #0055ff;
        window { color: @theme_fg_color; background-color: @theme_bg_color; }
        """,
        encoding="utf-8",
    )
    (gtk3_dir / "gtk.css").write_text(
        """
        @define-color theme_fg_color #000000;
        @define-color theme_bg_color #ffffff;
        """,
        encoding="utf-8",
    )
    (base_dir / "index.theme").write_text(
        "[Desktop Entry]\nType=X-GNOME-Metatheme\nName=Adwaita\n",
        encoding="utf-8",
    )

    user_themes_dir = tmp_path / "user_themes"
    state_file = tmp_path / "state" / "theme_forks.json"

    fork_mgr = ThemeForkManager(
        user_themes_dir=user_themes_dir,
        state_file=state_file,
    )

    new_colors = {
        "theme_fg_color": "#e0e0e0",
        "theme_bg_color": "#121212",
        "theme_selected_bg_color": "#ff5500",
        "theme_selected_fg_color": "#ffffff",
    }

    fork = fork_mgr.create_fork(
        base_theme_name="Adwaita",
        base_theme_path=base_dir,
        custom_name="My Dark Adwaita",
        colors=new_colors,
        overwrite=True,
    )

    assert fork.fork_name == "My Dark Adwaita"
    assert fork.fork_path.is_dir()
    assert (fork.fork_path / "gtk-4.0" / "gtk.css").is_file()

    # Verify CSS contains overridden colors
    gtk4_css = (fork.fork_path / "gtk-4.0" / "gtk.css").read_text(encoding="utf-8")
    assert "@define-color theme_bg_color #121212;" in gtk4_css
    assert "@define-color theme_fg_color #e0e0e0;" in gtk4_css
    assert "@define-color theme_selected_bg_color #ff5500;" in gtk4_css

    # Check state file persisted
    assert state_file.is_file()
    forks_list = fork_mgr.list_forks()
    assert len(forks_list) == 1
    assert forks_list[0].fork_name == "My Dark Adwaita"
    assert forks_list[0].base_theme_name == "Adwaita"


def test_theme_fork_index_theme_label(tmp_path: Path) -> None:
    """Test that index.theme in fork includes (edited) label in Name field."""
    base_dir = tmp_path / "base_theme"
    base_dir.mkdir(parents=True)
    (base_dir / "index.theme").write_text(
        "[Desktop Entry]\nName=Yaru\nType=X-GNOME-Metatheme\n",
        encoding="utf-8",
    )
    gtk4_dir = base_dir / "gtk-4.0"
    gtk4_dir.mkdir()
    (gtk4_dir / "gtk.css").write_text("@define-color theme_bg_color #fff;")

    fork_mgr = ThemeForkManager(
        user_themes_dir=tmp_path / "user_themes",
        state_file=tmp_path / "forks.json",
    )

    fork = fork_mgr.create_fork(
        base_theme_name="Yaru",
        base_theme_path=base_dir,
        custom_name="Yaru Orange",
        colors={"theme_bg_color": "#ff8800"},
    )

    index_content = (fork.fork_path / "index.theme").read_text(encoding="utf-8")
    assert "Name=Yaru Orange (edited)" in index_content


def test_revert_theme_fork(tmp_path: Path) -> None:
    """Test reverting/deleting a theme fork removes directory and cleans metadata."""
    base_dir = tmp_path / "base"
    base_dir.mkdir(parents=True)
    gtk4_dir = base_dir / "gtk-4.0"
    gtk4_dir.mkdir()
    (gtk4_dir / "gtk.css").write_text("@define-color theme_bg_color #fff;")

    fork_mgr = ThemeForkManager(
        user_themes_dir=tmp_path / "user_themes",
        state_file=tmp_path / "forks.json",
    )

    fork = fork_mgr.create_fork(
        base_theme_name="Base",
        base_theme_path=base_dir,
        custom_name="Base-Fork",
        colors={"theme_bg_color": "#000"},
    )
    assert fork.fork_path.is_dir()
    assert len(fork_mgr.list_forks()) == 1

    # Revert fork
    assert fork_mgr.revert_fork("Base-Fork") is True
    assert not fork.fork_path.exists()
    assert len(fork_mgr.list_forks()) == 0

    with pytest.raises(FileNotFoundError):
        fork_mgr.revert_fork("NonExistent")
