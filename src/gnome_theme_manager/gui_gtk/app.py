# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo principale dell'applicazione Libadwaita (GnomeThemeApplication)."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
from gi.repository import Adw, Gio

from ..core.manager import ThemeManager
from .window import GnomeThemeWindow

APPLICATION_ID = "org.gnome.ThemeManager"


class GnomeThemeApplication(Adw.Application):
    """Applicazione nativa GNOME basata su Libadwaita."""

    def __init__(self, manager: ThemeManager | None = None) -> None:
        """Inizializza l'applicazione Libadwaita con application_id e flag standard.

        Args:
            manager: Istanza coordinatrice ThemeManager opzionale.
        """
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.manager = manager or ThemeManager()
        self.window: GnomeThemeWindow | None = None

    def do_activate(self) -> None:
        """Gestore del segnale di attivazione dell'applicazione (activate).

        Crea o porta in primo piano la finestra principale GnomeThemeWindow.
        """
        if self.window is None:
            self.window = GnomeThemeWindow(app=self, manager=self.manager)
        self.window.present()
