# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for IconPackPreview widget and preview functionality (Task 1.4)."""

from pathlib import Path

import pytest

from gnome_theme_manager.gui_gtk import is_gtk_available

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk

    from gnome_theme_manager.gui_gtk.widgets.icon_pack_preview import (
        PREVIEW_ICON_NAMES,
        IconPackPreview,
        create_icon_preview_grid,
    )


def test_preview_icon_names_constants() -> None:
    """Verify that the standard preview icon list is defined and contains standard GNOME icons."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    assert len(PREVIEW_ICON_NAMES) >= 6
    assert "folder" in PREVIEW_ICON_NAMES
    assert "user-home" in PREVIEW_ICON_NAMES
    assert "user-trash" in PREVIEW_ICON_NAMES
    assert "org.gnome.Nautilus" in PREVIEW_ICON_NAMES


def test_icon_pack_preview_widget_creation(tmp_path: Path) -> None:
    """Verify that IconPackPreview widget is correctly instantiated with a theme path."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    theme_dir = tmp_path / "MyTestIcons"
    theme_dir.mkdir(parents=True)
    (theme_dir / "index.theme").write_text("[Icon Theme]\nName=MyTestIcons\n", encoding="utf-8")

    preview = IconPackPreview(theme_name="MyTestIcons", theme_path=theme_dir, icon_size=48)
    assert isinstance(preview, Gtk.Widget)
    assert preview.theme_name == "MyTestIcons"
    assert preview.theme_path == theme_dir

    grid = preview.get_grid()
    assert isinstance(grid, (Gtk.Grid, Gtk.Box, Gtk.FlowBox))


def test_create_icon_preview_grid_with_system_theme() -> None:
    """Verify creation of preview grid for a system theme like Adwaita."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    widget = create_icon_preview_grid(theme_name="Adwaita", icon_size=32)
    assert isinstance(widget, Gtk.Widget)


def test_icon_pack_preview_does_not_mutate_default_icon_theme() -> None:
    """Verify that preview uses an isolated Gtk.IconTheme without modifying the default/global theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    import gi

    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    if display is not None:
        default_theme = Gtk.IconTheme.get_for_display(display)
        orig_name = default_theme.get_theme_name()

        _preview = IconPackPreview(theme_name="NonExistentThemeXYZ")
        current_name = default_theme.get_theme_name()
        assert current_name == orig_name
