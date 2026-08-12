"""Controller per la pagina 'Stato attuale' (Fase 5.2.1).

Questo modulo gestisce il caricamento dichiarativo e il ciclo di vita della vista
di diagnostica dello stato attuale del sistema. Espone il widget Adw.StatusPage
per l'integrazione nel Gtk.Stack dell'applicazione.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

# Percorso del file template UI dedicato
UI_FILE = Path(__file__).parent.parent / "ui" / "status_page.ui"


class StatusPage:
    """Controller della vista 'Stato attuale' per la GUI GTK4/Libadwaita."""

    PAGE_ID: str = "status"
    TITLE: str = "Stato attuale"
    ICON_NAME: str = "preferences-desktop-theme-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template status_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager (non utilizzata in questa fase).

        Raises:
            FileNotFoundError: Se il template status_page.ui non è presente nel filesystem.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = self.TITLE
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"File template UI non trovato: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE))

        # Recupero del widget principale AdwStatusPage
        self.widget: Adw.StatusPage = self.builder.get_object("page_root")

    def get_widget(self) -> Adw.StatusPage:
        """Restituisce il widget Adw.StatusPage per l'integrazione nel Gtk.Stack.

        Returns:
            Widget Adw.StatusPage pronto per essere inserito nello stack dei contenuti.
        """
        return self.widget
