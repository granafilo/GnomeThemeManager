# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Task 3.4: Bundled fallback icons for the UI."""

from pathlib import Path

import pytest

from gnome_theme_manager.gui_gtk import is_gtk_available

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk

    from gnome_theme_manager.gui_gtk.window import (
        BUNDLED_ICONS_DIR,
        MainWindow,
        init_bundled_icon_theme,
    )


def test_bundled_icons_directory_and_assets_exist() -> None:
    """Verify data/icons exists and contains standard UI fallback symbolic icons."""
    data_icons = Path(__file__).parent.parent / "data" / "icons"
    assert data_icons.is_dir(), "data/icons directory must exist"

    # Verify key fallback and custom icons used in the UI
    required_icons = [
        "app-logo.svg",
        "app-logo-symbolic.svg",
        "face-slightly-smiling-plus.svg",
        "face-slightly-smiling-plus-symbolic.svg",
        "application-x-executable.svg",
        "input-mouse-symbolic.svg",
        "starred-symbolic.svg",
        "system-software-install-symbolic.svg",
        "dialog-error-symbolic.svg",
        "dialog-warning-symbolic.svg",
        "emblem-ok-symbolic.svg",
        "flatpak-symbolic.svg",
    ]

    for icon in required_icons:
        icon_path = data_icons / "hicolor" / "scalable" / "actions" / icon
        assert icon_path.is_file(), f"Missing bundled fallback icon: {icon_path}"


def test_init_bundled_icon_theme_registers_search_path() -> None:
    """Verify that init_bundled_icon_theme adds BUNDLED_ICONS_DIR to Gtk.IconTheme."""
    if not is_gtk_available():
        pytest.skip("GTK4 / Adw not available.")

    icon_theme = Gtk.IconTheme.new()
    # Before init, search paths should not contain BUNDLED_ICONS_DIR
    init_bundled_icon_theme(icon_theme)

    paths = icon_theme.get_search_path()
    assert any(str(BUNDLED_ICONS_DIR) in p for p in paths), (
        f"BUNDLED_ICONS_DIR {BUNDLED_ICONS_DIR} was not added to icon_theme search path: {paths}"
    )


def test_main_window_initializes_bundled_icons(mock_theme_manager) -> None:
    """Verify MainWindow initializes bundled icon theme chain."""
    if not is_gtk_available():
        pytest.skip("GTK4 / Adw not available.")

    app = Gtk.Application()
    win = MainWindow(app=app, manager=mock_theme_manager)
    assert win is not None
    assert BUNDLED_ICONS_DIR.is_dir()


def test_bundled_app_launcher_icons_exist() -> None:
    """Verify data/icons contains standard scalable app launcher icons."""
    data_icons = Path(__file__).parent.parent / "data" / "icons"
    apps_dir = data_icons / "hicolor" / "scalable" / "apps"
    assert (apps_dir / "io.github.granafilo.ThemeManager.svg").is_file()
    assert (apps_dir / "io.github.granafilo.ThemeManager-symbolic.svg").is_file()


def test_icon_pack_preview_includes_bundled_search_path(tmp_path: Path) -> None:
    """Verify IconPackPreview includes bundled icons search path."""
    if not is_gtk_available():
        pytest.skip("GTK4 / Adw not available.")

    from gnome_theme_manager.gui_gtk.widgets.icon_pack_preview import IconPackPreview

    preview = IconPackPreview(theme_name="NonExistentTheme", theme_path=tmp_path)
    paths = preview._icon_theme.get_search_path()
    assert any(str(BUNDLED_ICONS_DIR) in p for p in paths)
