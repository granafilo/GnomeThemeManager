"""Modulo contenente la finestra principale dell'applicazione (GnomeThemeWindow).

Gestisce la shell principale con GTK4 e Libadwaita (Fase 5.3):
- Adw.ToastOverlay per notifiche temporanee e dimensionamento minimo;
- Adw.NavigationSplitView con sidebar a sinistra (Gtk.ListBox) e content fisso a destra;
- Router centralizzato basato su Gtk.Stack all'interno del content Adw.NavigationPage;
- Aggiornamento della pagina visibile tramite set_visible_child_name() senza ri-parenting;
- Pulsante Refresh dedicato visibile unicamente quando la pagina attiva è 'status';
- Gestione della responsività adattiva tramite Adw.Breakpoint (collasso sotto i 700px).
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from ..core.manager import ThemeManager
from .pages import (
    InstallerPage,
    PresetsPage,
    SandboxPage,
    StatusPage,
    ThemesPage,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("gnome_theme_manager.gui_gtk.window")

# Percorso del template XML UI principale per la finestra
UI_FILE = Path(__file__).parent / "ui" / "window.ui"

# Soglia di larghezza (in pixel) per il collasso automatico in modalità compatta/mobile
COLLAPSE_BREAKPOINT_WIDTH: int = 700


class GnomeThemeWindow(Adw.ApplicationWindow):
    """Finestra principale dell'applicazione basata su Libadwaita e Adw.NavigationSplitView."""

    def __init__(self, app: Adw.Application, manager: ThemeManager | None = None) -> None:
        """Inizializza la finestra principale caricando il layout da GtkBuilder e impostando il router.

        Args:
            app: Istanza di Adw.Application proprietaria della finestra.
            manager: Istanza coordinatrice ThemeManager (creata automaticamente se non fornita).

        Raises:
            FileNotFoundError: Se il template window.ui non viene trovato.
        """
        super().__init__(application=app, title="Gnome Theme Manager")

        # Dimensionamento minimo (richiesto da Libadwaita) e dimensione iniziale consigliata
        self.set_size_request(760, 520)
        self.set_default_size(1000, 700)

        self.manager = manager or ThemeManager()

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"File di template UI non trovato: {UI_FILE}")

        # Caricamento del layout tramite Gtk.Builder
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE))

        # Recupero dei widget principali definiti nel template XML
        self.toast_overlay: Adw.ToastOverlay = self.builder.get_object("toast_overlay")
        self.split_view: Adw.NavigationSplitView = self.builder.get_object("split_view")
        self.sidebar_page: Adw.NavigationPage = self.builder.get_object("sidebar_page")
        self.sidebar_list_box: Gtk.ListBox = self.builder.get_object("sidebar_list_box")
        self.content_page: Adw.NavigationPage = self.builder.get_object("content_page")
        self.content_header_bar: Adw.HeaderBar = self.builder.get_object("content_header_bar")
        self.content_stack: Gtk.Stack = self.builder.get_object("content_stack")
        self.refresh_button: Gtk.Button = self.builder.get_object("refresh_button")

        # Recupero delle righe della sidebar per la navigazione
        self.row_status: Gtk.ListBoxRow = self.builder.get_object("row_status")
        self.row_themes: Gtk.ListBoxRow = self.builder.get_object("row_themes")
        self.row_presets: Gtk.ListBoxRow = self.builder.get_object("row_presets")
        self.row_installer: Gtk.ListBoxRow = self.builder.get_object("row_installer")
        self.row_sandbox: Gtk.ListBoxRow = self.builder.get_object("row_sandbox")

        # Impostazione del widget radice della finestra (Adw.ToastOverlay che racchiude la split view)
        self.set_content(self.toast_overlay)

        # Configurazione del comportamento responsive (Breakpoint)
        self._setup_breakpoint()

        # Inizializzazione univoca dei controller delle 5 pagine modulari (Router stabile)
        self.pages: dict[str, Any] = {
            "status": StatusPage(manager=self.manager),
            "themes": ThemesPage(manager=self.manager),
            "presets": PresetsPage(manager=self.manager),
            "installer": InstallerPage(manager=self.manager),
            "sandbox": SandboxPage(manager=self.manager),
        }

        # Aggiunta univoca dei widget delle pagine nello Gtk.Stack condiviso
        for page_id, controller in self.pages.items():
            self.content_stack.add_named(controller.get_widget(), page_id)

        # Mappatura bidirezionale tra righe Gtk.ListBox e ID pagina
        self._row_to_page_id: dict[Gtk.ListBoxRow, str] = {
            self.row_status: "status",
            self.row_themes: "themes",
            self.row_presets: "presets",
            self.row_installer: "installer",
            self.row_sandbox: "sandbox",
        }

        self._page_id_to_row: dict[str, Gtk.ListBoxRow] = {
            pid: row for row, pid in self._row_to_page_id.items()
        }

        # Tracciamento della pagina attiva
        self._current_page_id: str | None = None

        # Connessione del segnale di cambio selezione della sidebar
        self.sidebar_list_box.connect("row-selected", self._on_sidebar_row_selected)

        # Connessione del pulsante Refresh
        self.refresh_button.connect("clicked", self._on_refresh_button_clicked)

        # Connessione callback di caricamento per sincronizzare la sensibilità del pulsante Refresh
        status_ctrl: StatusPage = self.pages["status"]
        status_ctrl.on_loading_changed = self._on_status_loading_changed

        # Selezione iniziale della pagina Stato all'avvio dell'applicazione
        self.select_page("status")

        # Avvio del primo caricamento diagnostico della pagina Stato
        status_ctrl.refresh()

    def _setup_breakpoint(self) -> None:
        """Configura il breakpoint responsive di Libadwaita per il collasso automatico."""
        try:
            condition = Adw.BreakpointCondition.parse(f"max-width: {COLLAPSE_BREAKPOINT_WIDTH}px")
            breakpoint = Adw.Breakpoint.new(condition)
            breakpoint.add_setter(self.split_view, "collapsed", True)
            self.add_breakpoint(breakpoint)
        except Exception as err:
            logger.warning(
                "Impossibile registrare Adw.Breakpoint (possibile assenza supporto runtime): %s",
                err,
            )

    def _on_sidebar_row_selected(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Gestore del segnale 'row-selected' della Gtk.ListBox della sidebar.

        Args:
            list_box: Widget Gtk.ListBox emittente.
            row: Riga selezionata (None se la selezione è stata azzerata).
        """
        if row is None:
            return

        page_id = self._row_to_page_id.get(row)
        if page_id is not None:
            self.select_page(page_id)
        else:
            logger.warning("Riga della sidebar selezionata priva di associazione page_id: %s", row)

    def _on_refresh_button_clicked(self, button: Gtk.Button) -> None:
        """Gestore del click sul pulsante Refresh della testata.

        Args:
            button: Widget Gtk.Button cliccato.
        """
        if self._current_page_id == "status":
            self.pages["status"].refresh()

    def _on_status_loading_changed(self, is_loading: bool) -> None:
        """Aggiorna lo stato di abilitazione del pulsante Refresh durante il caricamento.

        Args:
            is_loading: True se un refresh è in corso, False altrimenti.
        """
        self.refresh_button.set_sensitive(not is_loading)

    def select_page(self, page_id: str) -> None:
        """Seleziona e visualizza la pagina specificata nel Gtk.Stack dei contenuti.

        Flusso operativo:
            1. Validazione dell'identificatore (se non valido, emette un warning e lascia intatta la vista);
            2. Cambio del figlio visibile in Gtk.Stack tramite set_visible_child_name();
            3. Aggiornamento del titolo di content_page;
            4. Gestione della visibilità del pulsante Refresh (visibile solo per 'status');
            5. Sincronizzazione della riga selezionata nella sidebar Gtk.ListBox;
            6. In modalità compatta (collapsed), imposta show_content=True per mostrare la pagina.

        Args:
            page_id: Identificatore della pagina ('status', 'themes', 'presets', 'installer', 'sandbox').
        """
        if page_id not in self.pages:
            logger.warning(
                "Tentativo di selezionare un page_id sconosciuto o non valido: '%s'",
                page_id,
            )
            return

        controller = self.pages[page_id]

        # Imposta la pagina visibile nello Gtk.Stack senza chiamare split_view.set_content()
        self.content_stack.set_visible_child_name(page_id)
        self.content_page.set_title(controller.title)
        self._current_page_id = page_id

        # Il pulsante refresh è specifico per la pagina Stato
        self.refresh_button.set_visible(page_id == "status")

        # Sincronizza la selezione visiva nella Gtk.ListBox senza generare loop ricorsivi
        target_row = self._page_id_to_row.get(page_id)
        if target_row is not None and self.sidebar_list_box.get_selected_row() != target_row:
            self.sidebar_list_box.select_row(target_row)

        # Su finestre strette (collapsed = True), porta l'utente alla vista del contenuto
        if self.split_view.get_collapsed():
            self.split_view.set_show_content(True)

    @property
    def current_page_id(self) -> str | None:
        """Restituisce l'identificatore della pagina attualmente visualizzata."""
        return self._current_page_id

    def add_toast(self, message: str, timeout: int = 3) -> None:
        """Visualizza una notifica non bloccante Adw.Toast sull'overlay.

        Args:
            message: Testo del messaggio da visualizzare.
            timeout: Secondi di permanenza del toast a schermo (default: 3).
        """
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)
