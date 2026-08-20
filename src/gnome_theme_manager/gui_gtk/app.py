# SPDX-License-Identifier: GPL-3.0-or-later

"""Main module for the Libadwaita application (GnomeThemeApplication)."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
from gi.repository import Adw, Gio

from ..core.manager import ThemeManager
from .window import GnomeThemeWindow

APPLICATION_ID = "org.gnome.ThemeManager"


class GnomeThemeApplication(Adw.Application):
    """Native GNOME application based on Libadwaita."""

    def __init__(self, manager: ThemeManager | None = None) -> None:
        """Initialize Libadwaita application with application_id and standard flags.

        Args:
            manager: Optional ThemeManager coordinator instance.
        """
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.manager = manager or ThemeManager()
        self.window: GnomeThemeWindow | None = None
        self.connect("shutdown", self._on_shutdown)

    def do_activate(self) -> None:
        """Handle application activation signal.

        Create or present the main GnomeThemeWindow.
        """
        if self.window is None:
            self.window = GnomeThemeWindow(app=self, manager=self.manager)
        self.window.present()

    def _on_shutdown(self, _app: "GnomeThemeApplication") -> None:
        """Handle application shutdown signal.

        Automatically roll back any active system theme preview.
        """
        if self.manager is not None and self.manager.is_preview_active:
            self.manager.cancel_theme_preview()
