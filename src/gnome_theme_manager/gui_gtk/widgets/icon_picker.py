# SPDX-License-Identifier: GPL-3.0-or-later

"""Reusable custom icon picker widget for Global Themes.

Allows the user to choose a custom image asset (bundled or on-disk) that
represents a Global Theme. Falls back to a default symbolic icon when no
custom icon is set.
"""

import logging

import gi

from gnome_theme_manager import _

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

logger = logging.getLogger("gnome_theme_manager.gui_gtk.widgets.icon_picker")

DEFAULT_ICON_NAME = "preferences-desktop-theme-symbolic"
IMAGE_FILTER_MIME_TYPES = ("image/svg+xml", "image/png", "image/jpeg")


class IconPickerButton(Gtk.Box):
    """Horizontal control to pick, preview and clear a custom theme icon."""

    def __init__(self) -> None:
        """Initialize the icon picker with preview, choose and clear controls."""
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._icon_path: str | None = None

        self._preview = Gtk.Image()
        self._preview.set_pixel_size(36)
        self._preview.set_valign(Gtk.Align.CENTER)
        self.append(self._preview)

        self._choose_btn = Gtk.Button.new_with_label(_("Choose Icon…"))
        self._choose_btn.set_tooltip_text(
            _("Select an image asset (SVG/PNG) to represent this Global Theme")
        )
        self._choose_btn.connect("clicked", self._on_choose_clicked)
        self.append(self._choose_btn)

        self._clear_btn = Gtk.Button()
        self._clear_btn.set_icon_name("edit-clear-symbolic")
        self._clear_btn.set_tooltip_text(_("Reset to default icon"))
        self._clear_btn.add_css_class("flat")
        self._clear_btn.connect("clicked", self._on_clear_clicked)
        self.append(self._clear_btn)

        self._refresh_preview()

    # -- public API ---------------------------------------------------------
    def get_icon_path(self) -> str | None:
        """Return selected custom icon path or ``None`` for default."""
        return self._icon_path

    def set_icon_path(self, path: str | None) -> None:
        """Set the current custom icon path (``None`` resets to default)."""
        self._icon_path = path
        self._refresh_preview()

    # -- internals ----------------------------------------------------------
    def _refresh_preview(self) -> None:
        """Update the preview image from the current selection."""
        self._preview.set_from_icon_name(DEFAULT_ICON_NAME)
        if not self._icon_path:
            return
        try:
            self._preview.set_from_file(self._icon_path)
        except Exception as err:
            logger.warning("Failed to load custom icon '%s': %s", self._icon_path, err)
            self._preview.set_from_icon_name(DEFAULT_ICON_NAME)

    def _on_choose_clicked(self, _btn: Gtk.Button) -> None:
        """Open a file dialog to pick an image asset."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Choose Theme Icon"))

        file_filter = Gtk.FileFilter()
        for mime in IMAGE_FILTER_MIME_TYPES:
            file_filter.add_mime_type(mime)
        dialog.set_default_filter(file_filter)

        root = self.get_root()
        dialog.open(
            root if isinstance(root, Gtk.Window) else None,
            None,
            self._on_file_dialog_finished,
        )

    def _on_file_dialog_finished(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        """Handle file dialog completion."""
        try:
            file = dialog.open_finish(result)
        except Exception as err:
            logger.debug("Icon picker file dialog cancelled: %s", err)
            return

        if file is None:
            return
        path = file.get_path()
        if path:
            self._icon_path = path
            self._refresh_preview()

    def _on_clear_clicked(self, _btn: Gtk.Button) -> None:
        """Reset custom icon to default."""
        self._icon_path = None
        self._refresh_preview()