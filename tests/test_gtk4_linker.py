# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GTK4ThemeLinker module.

Verifies correct creation, replacement, removal, and integrity checking
of symbolic links (symlinks) in user configuration directory ~/.config/gtk-4.0/.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gnome_theme_manager.core.gtk4_linker import GTK4ThemeLinker


@pytest.fixture(autouse=True)
def isolate_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate XDG configuration and data directories for tests."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))


@pytest.fixture
def mock_gtk4_environment(tmp_path: Path):
    """Create a mock theme structure and ~/.config/gtk-4.0/ directory for tests."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    theme_dir = tmp_path / "themes" / "Nordic"

    # Create theme files with gtk-4.0 directory and assets
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
    """Verify that apply_override properly creates symlinks for gtk.css and assets."""
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
    """Verify that gtk-3.0 folder is used as fallback if gtk-4.0 does not exist."""
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
    """Verify that apply_override returns False if no CSS files are found."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    theme_dir = tmp_path / "themes" / "EmptyTheme"
    theme_dir.mkdir(parents=True, exist_ok=True)

    linker = GTK4ThemeLinker(config_dir=config_dir)
    success = linker.apply_override(theme_dir)

    assert success is False
    assert not (config_dir / "gtk.css").exists()


def test_gtk4_linker_apply_no_css_removes_previous_override(mock_gtk4_environment):
    """Verify that applying a theme without GTK4/3 styles removes a previously active override."""
    env = mock_gtk4_environment
    linker = GTK4ThemeLinker(config_dir=env["config_dir"])

    # 1. First apply theme A with valid GTK4 styles
    assert linker.apply_override(env["theme_dir"]) is True
    assert linker.is_override_active() is True
    assert (env["config_dir"] / "gtk.css").exists()

    # 2. Apply theme B without GTK4/3 styles
    empty_theme_dir = env["theme_dir"].parent / "EmptyTheme"
    empty_theme_dir.mkdir(parents=True, exist_ok=True)

    success = linker.apply_override(empty_theme_dir)
    assert success is False
    # Previous override must have been removed
    assert not (env["config_dir"] / "gtk.css").exists()
    assert not (env["config_dir"] / "gtk-dark.css").exists()
    assert not (env["config_dir"] / "assets").exists()
    assert linker.is_override_active() is False


def test_gtk4_linker_apply_no_css_when_no_previous_override(tmp_path: Path):
    """Verify that applying a theme without GTK4/3 styles when no override existed raises no exceptions."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    empty_theme_dir = tmp_path / "themes" / "EmptyTheme"
    empty_theme_dir.mkdir(parents=True, exist_ok=True)

    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.apply_override(empty_theme_dir) is False
    assert linker.is_override_active() is False


def test_gtk4_linker_remove_override(mock_gtk4_environment):
    """Verify that remove_override deletes previously created symlinks."""
    env = mock_gtk4_environment
    linker = GTK4ThemeLinker(config_dir=env["config_dir"])

    linker.apply_override(env["theme_dir"])
    assert (env["config_dir"] / "gtk.css").exists()

    linker.remove_override()
    assert not (env["config_dir"] / "gtk.css").exists()
    assert not (env["config_dir"] / "gtk-dark.css").exists()
    assert not (env["config_dir"] / "assets").exists()


def test_gtk4_linker_is_override_active_true(mock_gtk4_environment):
    """Verify that is_override_active returns True when symlinks are valid."""
    env = mock_gtk4_environment
    linker = GTK4ThemeLinker(config_dir=env["config_dir"])

    assert linker.is_override_active() is False

    linker.apply_override(env["theme_dir"])
    assert linker.is_override_active() is True


def test_gtk4_linker_is_override_active_false_when_empty(tmp_path: Path):
    """Verify that is_override_active returns False on an empty or non-existent directory."""
    config_dir = tmp_path / "non_existent_gtk4"
    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.is_override_active() is False


def test_gtk4_linker_is_override_active_false_when_dangling_symlink(tmp_path: Path):
    """Verify that is_override_active returns False if gtk.css is a broken/dangling symlink."""
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
    """Verify that is_override_active returns False if an optional linked file is dangling."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    config_dir.mkdir(parents=True, exist_ok=True)

    # valid gtk.css
    valid_css_source = tmp_path / "valid_theme" / "gtk.css"
    valid_css_source.parent.mkdir(parents=True, exist_ok=True)
    valid_css_source.write_text("/* valid */")
    (config_dir / "gtk.css").symlink_to(valid_css_source)

    # broken gtk-dark.css
    (config_dir / "gtk-dark.css").symlink_to(tmp_path / "deleted" / "gtk-dark.css")

    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.is_override_active() is False


def test_gtk4_linker_is_override_active_true_run_host_symlink(tmp_path: Path):
    """Verify that is_override_active returns True when symlink points to /run/host/<real_file>."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    config_dir.mkdir(parents=True, exist_ok=True)

    real_css = tmp_path / "usr" / "share" / "themes" / "Colloid" / "gtk.css"
    real_css.parent.mkdir(parents=True, exist_ok=True)
    real_css.write_text("/* valid */")

    # Symlink points to /run/host + real_css
    (config_dir / "gtk.css").symlink_to(Path(f"/run/host{real_css}"))

    linker = GTK4ThemeLinker(config_dir=config_dir)
    assert linker.is_override_active() is True


def test_gtk4_linker_apply_override_strips_run_host(tmp_path: Path):
    """Verify that apply_override strips /run/host from target symlink when running in sandbox."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    theme_dir = tmp_path / "run" / "host" / "usr" / "share" / "themes" / "MyTheme"
    theme_gtk4 = theme_dir / "gtk-4.0"
    theme_gtk4.mkdir(parents=True, exist_ok=True)
    (theme_gtk4 / "gtk.css").write_text("/* theme */")

    linker = GTK4ThemeLinker(config_dir=config_dir)
    # Patch resolve of source_file to simulate /run/host/usr/share/themes/MyTheme/gtk-4.0/gtk.css
    with patch(
        "pathlib.Path.resolve",
        return_value=Path("/run/host/usr/share/themes/MyTheme/gtk-4.0/gtk.css"),
    ):
        success = linker.apply_override(theme_dir)
        assert success is True

    linked_target = os.readlink(config_dir / "gtk.css")
    assert not linked_target.startswith("/run/host")
    assert linked_target == "/usr/share/themes/MyTheme/gtk-4.0/gtk.css"
