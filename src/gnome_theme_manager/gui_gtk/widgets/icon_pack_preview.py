# SPDX-License-Identifier: GPL-3.0-or-later

"""Icon pack visual preview widget (Task 1.4).

Renders a preview grid of standard GNOME application and system icons
using an isolated Gtk.IconTheme instance without modifying the active desktop system theme.
"""

import logging
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

logger = logging.getLogger("gnome_theme_manager.gui_gtk.widgets.icon_pack_preview")

# Semantic groups representing the primary user-visible icons of the GNOME desktop
PREVIEW_ICON_GROUPS: list[list[str]] = [
    # 1. Home folder
    ["user-home", "folder-home"],
    # 2. Standard directory / folder
    ["folder", "folder-documents"],
    # 3. Downloads directory
    ["folder-download", "emblem-downloads"],
    # 4. Music folder
    ["folder-music", "folder-sound"],
    # 5. Pictures folder
    ["folder-pictures", "folder-images"],
    # 6. Trash bin
    ["user-trash", "user-trash-full", "trash-empty"],
    # 7. File Manager (Nautilus)
    ["org.gnome.Nautilus", "system-file-manager", "file-manager"],
    # 8. GNOME Settings (Control Center)
    ["org.gnome.Settings", "preferences-system", "gnome-control-center"],
    # 9. App Store (Software Center)
    ["org.gnome.Software", "system-software-install", "software-store"],
    # 10. Calculator
    ["org.gnome.Calculator", "gnome-calculator", "accessories-calculator"],
    # 11. Text Editor
    ["org.gnome.TextEditor", "org.gnome.gedit", "text-editor"],
    # 12. Terminal
    ["utilities-terminal", "org.gnome.Terminal", "terminal"],
]

# Legacy compatibility list of base icon identifiers
PREVIEW_ICON_NAMES: list[str] = [g[0] for g in PREVIEW_ICON_GROUPS]


class IconPackPreview(Gtk.Box):
    """Widget that renders a live visual preview grid for a given icon theme."""

    def __init__(
        self,
        theme_name: str,
        theme_path: Path | None = None,
        icon_size: int = 36,
        **kwargs: Any,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, **kwargs)
        self.theme_name = theme_name
        self.theme_path = theme_path
        self.icon_size = icon_size

        self._icon_theme = Gtk.IconTheme.new()

        # Add custom path if icon pack is located outside standard directories
        if theme_path is not None and theme_path.is_dir():
            parent_dir = theme_path.parent
            self._icon_theme.add_search_path(str(parent_dir))

        self._icon_theme.set_theme_name(theme_name)

        self._grid = Gtk.FlowBox()
        self._grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self._grid.set_max_children_per_line(6)
        self._grid.set_min_children_per_line(4)
        self._grid.set_row_spacing(8)
        self._grid.set_column_spacing(8)
        self._grid.set_homogeneous(True)
        self._grid.set_halign(Gtk.Align.CENTER)

        self._populate_icons()
        self.append(self._grid)

    def _populate_icons(self) -> None:
        """Populate grid with icons looked up from the isolated icon theme."""
        for candidates in PREVIEW_ICON_GROUPS:
            paintable = None
            resolved_name = candidates[0]

            for candidate in candidates:
                try:
                    if self._icon_theme.has_icon(candidate):
                        p = self._icon_theme.lookup_icon(
                            candidate,
                            None,
                            self.icon_size,
                            1,
                            Gtk.TextDirection.NONE,
                            0,
                        )
                        if p is not None and hasattr(p, "get_file") and p.get_file() is not None:
                            paintable = p
                            resolved_name = candidate
                            break
                except Exception as ex:
                    logger.debug("Failed looking up candidate icon '%s': %s", candidate, ex)
                    continue

            img: Gtk.Image
            if paintable is not None:
                img = Gtk.Image.new_from_paintable(paintable)
            else:
                img = Gtk.Image.new_from_icon_name(resolved_name)

            img.set_pixel_size(self.icon_size)
            img.set_tooltip_text(resolved_name)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_halign(Gtk.Align.CENTER)
            box.append(img)

            self._grid.append(box)

    def get_grid(self) -> Gtk.FlowBox:
        """Return the flowbox containing icon previews."""
        return self._grid


def create_icon_preview_grid(
    theme_name: str,
    theme_path: Path | None = None,
    icon_size: int = 36,
) -> IconPackPreview:
    """Convenience helper to create an IconPackPreview widget."""
    return IconPackPreview(theme_name=theme_name, theme_path=theme_path, icon_size=icon_size)
