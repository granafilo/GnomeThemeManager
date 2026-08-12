"""Controller per la pagina 'Profili e preset' (Fase 5.2.1).

Questo modulo gestisce il caricamento dichiarativo della vista per la gestione,
salvataggio e applicazione dei profili di configurazione temi.
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
UI_FILE = Path(__file__).parent.parent / "ui" / "presets_page.ui"


class PresetsPage:
    """Controller della vista 'Profili e preset' per la GUI GTK4/Libadwaita."""

    PAGE_ID: str = "presets"
    TITLE: str = "Profili e preset"
    ICON_NAME: str = "document-save-as-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template presets_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager (non utilizzata in questa fase).

        Raises:
            FileNotFoundError: Se il template presets_page.ui non è presente nel filesystem.
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
