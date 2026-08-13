"""Modulo contenente la finestra principale dell'applicazione (GnomeThemeWindow).

Gestisce la shell principale con GTK4 e Libadwaita (Fase 5.4 revisionata):
- Adw.ToastOverlay per notifiche temporanee unificate;
- Adw.NavigationSplitView con sidebar a sinistra (Gtk.ListBox) e content fisso a destra;
- 4 sezioni dedicate per componente (GNOME Shell, GTK, Icone, Cursori) senza duplicazione di controller o widget;
- Router centralizzato basato su Gtk.Stack all'interno del content Adw.NavigationPage;
- Pulsante Refresh contestuale visibile unicamente quando la pagina attiva è 'status' o una categoria 'themes';
- Gestione della responsività adattiva tramite Adw.Breakpoint (collasso sotto i 700px).
"""

import logging
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk

from ..core.manager import ThemeManager
from ..core.models import ThemeType
from .pages import (
    InstallerPage,
    PresetsPage,
    SandboxPage,
    StatusPage,
    ThemesPage,
)

logger = logging.getLogger("gnome_theme_manager.gui_gtk.window")

# Percorso del file template UI associato
UI_FILE = Path(__file__).parent / "ui" / "window.ui"

# Soglia di larghezza minima per il collasso automatico in visualizzazione compatta (sidebar a scomparsa)
COLLAPSE_BREAKPOINT_WIDTH: int = 700


class GnomeThemeWindow(Adw.ApplicationWindow):
    """Finestra principale dell'applicazione GTK4 / Libadwaita."""

    def __init__(self, app: Adw.Application, manager: ThemeManager | None = None) -> None:
        """Inizializza la finestra principale caricando il template window.ui.

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

        # Recupero dei widget di notifica superiore (Top Responsive Feedback)
        self.feedback_revealer: Gtk.Revealer = self.builder.get_object("feedback_revealer")
        self.feedback_box: Gtk.Box = self.builder.get_object("feedback_box")
        self.feedback_icon: Gtk.Image = self.builder.get_object("feedback_icon")
        self.feedback_label: Gtk.Label = self.builder.get_object("feedback_label")
        self.feedback_close_button: Gtk.Button = self.builder.get_object("feedback_close_button")
        self._feedback_timeout_id: int | None = None

        if self.feedback_close_button is not None:
            self.feedback_close_button.connect("clicked", self._on_feedback_close_clicked)

        # Recupero delle righe della sidebar per la navigazione
        self.row_status: Gtk.ListBoxRow = self.builder.get_object("row_status")
        self.row_themes_shell: Gtk.ListBoxRow = self.builder.get_object("row_themes_shell")
        self.row_themes_gtk: Gtk.ListBoxRow = self.builder.get_object("row_themes_gtk")
        self.row_themes_icon: Gtk.ListBoxRow = self.builder.get_object("row_themes_icon")
        self.row_themes_cursor: Gtk.ListBoxRow = self.builder.get_object("row_themes_cursor")
        self.row_presets: Gtk.ListBoxRow = self.builder.get_object("row_presets")
        self.row_installer: Gtk.ListBoxRow = self.builder.get_object("row_installer")
        self.row_sandbox: Gtk.ListBoxRow = self.builder.get_object("row_sandbox")

        # Impostazione del widget radice della finestra (Adw.ToastOverlay che racchiude la split view)
        self.set_content(self.toast_overlay)

        # Configurazione del comportamento responsive (Breakpoint)
        self._setup_breakpoint()

        # Inizializzazione dei controller delle pagine (ThemesPage è unico e gestisce le 4 categorie)
        self.status_page = StatusPage(manager=self.manager)
        self.themes_page = ThemesPage(manager=self.manager)
        self.presets_page = PresetsPage(manager=self.manager)
        self.installer_page = InstallerPage(manager=self.manager)
        self.sandbox_page = SandboxPage(manager=self.manager)

        self.pages: dict[str, Any] = {
            "status": self.status_page,
            "themes": self.themes_page,
            "themes_shell": self.themes_page,
            "themes_gtk": self.themes_page,
            "themes_icon": self.themes_page,
            "themes_cursor": self.themes_page,
            "presets": self.presets_page,
            "installer": self.installer_page,
            "sandbox": self.sandbox_page,
        }

        # Aggiunta dei widget univoci nello Gtk.Stack condiviso
        self.content_stack.add_named(self.status_page.get_widget(), "status")
        self.content_stack.add_named(self.themes_page.get_widget(), "themes")
        self.content_stack.add_named(self.presets_page.get_widget(), "presets")
        self.content_stack.add_named(self.installer_page.get_widget(), "installer")
        self.content_stack.add_named(self.sandbox_page.get_widget(), "sandbox")

        # Mappatura bidirezionale tra righe Gtk.ListBox e ID pagina
        self._row_to_page_id: dict[Gtk.ListBoxRow, str] = {
            self.row_status: "status",
            self.row_themes_shell: "themes_shell",
            self.row_themes_gtk: "themes_gtk",
            self.row_themes_icon: "themes_icon",
            self.row_themes_cursor: "themes_cursor",
            self.row_presets: "presets",
            self.row_installer: "installer",
            self.row_sandbox: "sandbox",
        }

        self._page_id_to_row: dict[str, Gtk.ListBoxRow] = {
            pid: row for row, pid in self._row_to_page_id.items()
        }
        # Alias per compatibilità con selezioni generiche 'themes'
        self._page_id_to_row["themes"] = self.row_themes_gtk

        # Tracciamento della pagina attiva
        self._current_page_id: str | None = None

        # Connessione del segnale di cambio selezione della sidebar
        self.sidebar_list_box.connect("row-selected", self._on_sidebar_row_selected)

        # Connessione del pulsante Refresh
        self.refresh_button.connect("clicked", self._on_refresh_button_clicked)

        # Connessione callback di caricamento per sincronizzare la sensibilità del pulsante Refresh
        self.status_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "status", is_l
        )
        self.themes_page.on_loading_changed = lambda is_l: self._on_page_loading_changed(
            "themes", is_l
        )

        # Connessione callback di applicazione tema (sincronizza la diagnostica senza duplicare il Toast)
        def _on_theme_applied_callback(item: Any, result: Any) -> None:
            self.status_page.refresh()

        self.themes_page.on_theme_applied = _on_theme_applied_callback

        # Connessione callback di applicazione preset (aggiorna StatusPage e ThemesPage)
        def _on_preset_applied_callback() -> None:
            # Rinfreschiamo la pagina Stato per riflettere i nuovi temi attivi
            self.status_page.refresh()
            # Rinfreschiamo ThemesPage per aggiornare la card del tema attivo e le alternative
            if self.themes_page.current_snapshot is not None or not self.themes_page.is_loading:
                self.themes_page.refresh()

        self.presets_page.on_preset_applied = _on_preset_applied_callback

        # Connessione callback di installazione tema (aggiorna Esplora Temi)
        def _on_theme_installed_callback() -> None:
            self.themes_page.refresh()

        self.installer_page.on_theme_installed = _on_theme_installed_callback

        # Connessione callback di installazione e applicazione tema (aggiorna Stato ed Esplora Temi)
        def _on_theme_installed_and_applied_callback() -> None:
            self.status_page.refresh()
            self.themes_page.refresh()

        self.installer_page.on_theme_applied = _on_theme_installed_and_applied_callback

        # Connessione callback di propagazione sandbox (aggiorna la pagina Stato)
        def _on_sandbox_propagated_callback() -> None:
            self.status_page.refresh()

        self.sandbox_page.on_sandbox_propagated = _on_sandbox_propagated_callback

        # Selezione iniziale della pagina Stato all'avvio dell'applicazione
        self.select_page("status")

        # Avvio del primo caricamento diagnostico della pagina Stato
        self.status_page.refresh()

    def _setup_breakpoint(self) -> None:
        """Configura il breakpoint responsive di Libadwaita per il collasso automatico."""
        try:
            condition = Adw.BreakpointCondition.parse(f"max-width: {COLLAPSE_BREAKPOINT_WIDTH}px")
            breakpoint = Adw.Breakpoint.new(condition)
            breakpoint.add_setter(self.split_view, "collapsed", True)
            self.add_breakpoint(breakpoint)
        except (GLib.GError, AttributeError, TypeError, ValueError) as err:
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
            self.status_page.refresh()
        elif self._current_page_id and (
            self._current_page_id == "themes" or self._current_page_id.startswith("themes_")
        ):
            self.themes_page.refresh()

    def _on_page_loading_changed(self, page_id: str, is_loading: bool) -> None:
        """Aggiorna lo stato di abilitazione del pulsante Refresh durante il caricamento della pagina corrente.

        Args:
            page_id: Identificatore della pagina che ha modificato lo stato.
            is_loading: True se un refresh è in corso, False altrimenti.
        """
        if self._current_page_id == page_id or (
            page_id == "themes"
            and self._current_page_id
            and self._current_page_id.startswith("themes_")
        ):
            self.refresh_button.set_sensitive(not is_loading)

    def select_page(self, page_id: str) -> None:
        """Seleziona e visualizza la pagina specificata nel Gtk.Stack dei contenuti.

        Flusso operativo:
            1. Validazione dell'identificatore (se non valido, emette un warning e lascia intatta la vista);
            2. Chiusura del banner di feedback precedente (clear_feedback);
            3. Configurazione della categoria attiva in ThemesPage per le 4 viste di temi;
            4. Cambio del figlio visibile in Gtk.Stack tramite set_visible_child_name();
            5. Aggiornamento del titolo di content_page;
            6. Gestione della visibilità del pulsante Refresh;
            7. Caricamento automatico al primo accesso se la pagina non è ancora stata popolata;
            8. Sincronizzazione della riga selezionata nella sidebar Gtk.ListBox;
            9. In modalità compatta (collapsed), imposta show_content=True per mostrare la pagina.

        Args:
            page_id: Identificatore della pagina ('status', 'themes_shell', 'themes_gtk', etc.).
        """
        # Chiude il feedback persistente al cambio pagina
        self.clear_feedback()

        if page_id == "themes":
            page_id = "themes_gtk"

        if page_id not in self.pages:
            logger.warning(
                "Tentativo di selezionare un page_id sconosciuto o non valido: '%s'",
                page_id,
            )
            return

        if page_id == "themes_shell":
            self.themes_page.set_category(ThemeType.SHELL)
            stack_id = "themes"
            page_title = "GNOME Shell"
        elif page_id == "themes_gtk":
            self.themes_page.set_category(ThemeType.GTK)
            stack_id = "themes"
            page_title = "Applicazioni (GTK)"
        elif page_id == "themes_icon":
            self.themes_page.set_category(ThemeType.ICON)
            stack_id = "themes"
            page_title = "Icone"
        elif page_id == "themes_cursor":
            self.themes_page.set_category(ThemeType.CURSOR)
            stack_id = "themes"
            page_title = "Cursori"
        else:
            stack_id = page_id
            page_title = self.pages[page_id].title

        # Imposta la pagina visibile nello Gtk.Stack
        self.content_stack.set_visible_child_name(stack_id)
        self.content_page.set_title(page_title)
        self._current_page_id = page_id

        # Il pulsante refresh è attivo per le pagine con caricamento dati (status e categorie themes)
        is_refreshable = page_id in (
            "status",
            "themes_shell",
            "themes_gtk",
            "themes_icon",
            "themes_cursor",
        )
        self.refresh_button.set_visible(is_refreshable)
        if is_refreshable:
            ctrl = self.pages[page_id]
            if hasattr(ctrl, "is_loading"):
                self.refresh_button.set_sensitive(not ctrl.is_loading)

        # Caricamento automatico al primo accesso se la pagina non è ancora stata popolata
        if (
            page_id.startswith("themes")
            and self.themes_page.current_snapshot is None
            and not self.themes_page.is_loading
        ):
            self.themes_page.refresh()
        elif (
            page_id == "status"
            and self.status_page.current_snapshot is None
            and not self.status_page.is_loading
        ):
            self.status_page.refresh()
        elif (
            page_id == "presets"
            and not self.presets_page.has_loaded
            and not self.presets_page.is_loading
        ):
            self.presets_page.refresh()
        elif (
            page_id == "sandbox"
            and self.sandbox_page._current_sandbox_status is None
            and not self.sandbox_page._is_loading
        ):
            self.sandbox_page.refresh()

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

    def clear_feedback(self) -> None:
        """Chiude e nasconde la notifica di feedback superiore corrente."""
        if self._feedback_timeout_id is not None:
            GLib.source_remove(self._feedback_timeout_id)
            self._feedback_timeout_id = None
        if self.feedback_revealer is not None:
            self.feedback_revealer.set_reveal_child(False)

    def _on_feedback_close_clicked(self, _btn: Gtk.Button | None = None) -> None:
        """Chiude manualmente la notifica di feedback superiore tramite il pulsante [✕]."""
        self.clear_feedback()

    def add_toast(self, message: str, timeout: int = 0) -> None:
        """Visualizza una notifica di feedback persistente nella parte alta della finestra.

        La notifica compare con animazione slide-down sotto l'header bar, ha una
        larghezza massima controllata da Adw.Clamp (560px), supporta il testo
        multilinea con wrapping automatico e rimane visibile fino alla successiva
        azione dell'utente (o click sul pulsante di chiusura).

        Args:
            message: Testo del messaggio da visualizzare.
            timeout: Secondi di permanenza del messaggio (default: 0 = persistente fino alla prossima azione).
        """
        # Annulla eventuale timer o messaggio precedente
        if self._feedback_timeout_id is not None:
            GLib.source_remove(self._feedback_timeout_id)
            self._feedback_timeout_id = None

        if self.feedback_label is not None:
            self.feedback_label.set_label(message)

        # Scelta dell'icona in base alla severità del messaggio
        if self.feedback_icon is not None:
            msg_lower = message.lower()
            if "errore" in msg_lower or "fallit" in msg_lower or "impossibile" in msg_lower:
                self.feedback_icon.set_from_icon_name("dialog-error-symbolic")
            elif "avvis" in msg_lower or "parziale" in msg_lower or "limitat" in msg_lower:
                self.feedback_icon.set_from_icon_name("dialog-warning-symbolic")
            elif "rimoss" in msg_lower or "eliminat" in msg_lower:
                self.feedback_icon.set_from_icon_name("user-trash-symbolic")
            else:
                self.feedback_icon.set_from_icon_name("emblem-ok-symbolic")

        if self.feedback_revealer is not None:
            self.feedback_revealer.set_reveal_child(True)

        if timeout > 0:

            def _auto_hide() -> bool:
                if self.feedback_revealer is not None:
                    self.feedback_revealer.set_reveal_child(False)
                self._feedback_timeout_id = None
                return GLib.SOURCE_REMOVE

            self._feedback_timeout_id = GLib.timeout_add_seconds(timeout, _auto_hide)

        # Fallback sull'overlay Adw.Toast per ambienti che non caricano GtkRevealer
        if self.feedback_revealer is None and self.toast_overlay is not None:
            toast = Adw.Toast.new(message)
            if timeout > 0:
                toast.set_timeout(timeout)
            self.toast_overlay.add_toast(toast)
