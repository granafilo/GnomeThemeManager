"""Controller per la pagina 'Esplora temi' con Card Tema Attivo e Lista Temi Disponibili (Fase 5.4.x).

Questo modulo implementa la visualizzazione separata del tema attualmente applicato (Card)
e dell'elenco dei temi alternativi disponibili per ciascun componente (GNOME Shell, GTK, Icone, Cursori).
Garantisce l'aggiornamento immediato del cursore in-process tramite Gdk.Display / Gtk.Settings,
l'immutabilità degli snapshot di stato e un feedback unificato.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from ...core.errors import GnomeThemeManagerError
from ...core.models import ApplyResult, Theme, ThemeSet, ThemeType

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.themes")

# Percorso del file template UI dedicato
UI_FILE = Path(__file__).parent.parent / "ui" / "themes_page.ui"

# Icone simboliche standard per ciascuna categoria
CATEGORY_ICONS: dict[ThemeType, str] = {
    ThemeType.GTK: "preferences-desktop-theme-symbolic",
    ThemeType.ICON: "applications-graphics-symbolic",
    ThemeType.CURSOR: "input-mouse-symbolic",
    ThemeType.SHELL: "preferences-system-windows-symbolic",
}

# Etichette di presentazione per ciascuna categoria
CATEGORY_LABELS: dict[ThemeType, str] = {
    ThemeType.GTK: "Applicazioni (GTK)",
    ThemeType.ICON: "Icone",
    ThemeType.CURSOR: "Cursori",
    ThemeType.SHELL: "GNOME Shell",
}

# Nomi sintetici delle categorie per il dialogo di conferma
DIALOG_CATEGORY_NAMES: dict[ThemeType, str] = {
    ThemeType.SHELL: "GNOME Shell",
    ThemeType.GTK: "GTK",
    ThemeType.ICON: "Icone",
    ThemeType.CURSOR: "Cursori",
}

# Titoli completi della testata di categoria
CATEGORY_TITLES: dict[ThemeType, str] = {
    ThemeType.GTK: "Temi per Applicazioni (GTK)",
    ThemeType.ICON: "Temi Icone",
    ThemeType.CURSOR: "Temi Cursori",
    ThemeType.SHELL: "Temi GNOME Shell",
}


# =============================================================================
# Modello di Presentazione UI (Immutabile)
# =============================================================================


@dataclass(frozen=True)
class ThemeItemPresentation:
    """Modello immutabile di presentazione per una riga di tema."""

    name: str
    theme_type: ThemeType
    category_display: str
    icon_name: str
    path_display: str
    origin_display: str
    is_user_level: bool


@dataclass(frozen=True)
class ThemesSnapshot:
    """Istantanea immutabile della lista completa dei temi scansionati e dei temi attivi."""

    items: list[ThemeItemPresentation]
    active_themes: dict[ThemeType, str | None]


def build_theme_presentation(theme: Theme) -> ThemeItemPresentation:
    """Costruisce un modello di presentazione a partire dall'oggetto di dominio Theme.

    Args:
        theme: Oggetto Theme proveniente dal core.

    Returns:
        Istanza immutabile di ThemeItemPresentation con dati formattati per la UI.
    """
    category_display = CATEGORY_LABELS.get(theme.theme_type, str(theme.theme_type.value).upper())
    icon_name = CATEGORY_ICONS.get(theme.theme_type, "applications-graphics-symbolic")
    origin_display = "Utente (~/.local/share/...)" if theme.is_user_level else "Sistema (/usr/share/...)"

    return ThemeItemPresentation(
        name=theme.name,
        theme_type=theme.theme_type,
        category_display=category_display,
        icon_name=icon_name,
        path_display=str(theme.path),
        origin_display=origin_display,
        is_user_level=theme.is_user_level,
    )


# =============================================================================
# Controller Pagina Esplora Temi
# =============================================================================


class ThemesPage:
    """Controller per la visualizzazione separata di Tema Attivo e Altri Temi Disponibili."""

    PAGE_ID: str = "themes"
    TITLE: str = "Esplora temi"
    ICON_NAME: str = "applications-graphics-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template dichiarativo themes_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager.

        Raises:
            FileNotFoundError: Se il template themes_page.ui non viene trovato.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = self.TITLE
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        # Categoria attualmente attiva (default: GTK)
        self.active_category: ThemeType = ThemeType.GTK

        # Tema attualmente selezionato nella lista delle alternative
        self._selected_theme: ThemeItemPresentation | None = None

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"Template UI non trovato: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE))

        # Widget principali dello Stack e degli stati
        self.widget: Gtk.Stack = self.builder.get_object("page_root")
        self.loading_spinner: Gtk.Spinner = self.builder.get_object("loading_spinner")
        self.category_title_label: Gtk.Label = self.builder.get_object("category_title_label")

        # Card del Tema Attivo
        self.active_theme_group: Adw.PreferencesGroup = self.builder.get_object("active_theme_group")
        self.active_theme_row: Adw.ActionRow = self.builder.get_object("active_theme_row")
        self.active_theme_icon: Gtk.Image = self.builder.get_object("active_theme_icon")
        self.active_theme_badge: Gtk.Label = self.builder.get_object("active_theme_badge")

        # Sezione Altri Temi Disponibili e Ricerca
        self.available_section_title: Gtk.Label = self.builder.get_object("available_section_title")
        self.search_entry: Gtk.SearchEntry = self.builder.get_object("search_entry")
        self.themes_scrolled_window: Gtk.ScrolledWindow = self.builder.get_object("themes_scrolled_window")
        self.count_label: Gtk.Label = self.builder.get_object("count_label")
        self.themes_list_box: Gtk.ListBox = self.builder.get_object("themes_list_box")
        self.no_results_page: Adw.StatusPage = self.builder.get_object("no_results_page")

        # Barra inferiore e pulsante Applica principale
        self.selection_info_label: Gtk.Label = self.builder.get_object("selection_info_label")
        self.apply_button: Gtk.Button = self.builder.get_object("apply_button")

        # Pagine e pulsanti di retry
        self.empty_page: Adw.StatusPage = self.builder.get_object("empty_page")
        self.empty_refresh_button: Gtk.Button = self.builder.get_object("empty_refresh_button")
        self.error_page: Adw.StatusPage = self.builder.get_object("error_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        # Connessione segnali di ricerca
        self.search_entry.connect("search-changed", self._on_filter_criteria_changed)
        self.search_entry.connect("changed", self._on_filter_criteria_changed)

        # Connessione segnali lista: selezione e attivazione (doppio click nativo con activate-on-single-click=False)
        self.themes_list_box.set_activate_on_single_click(False)
        self.themes_list_box.connect("row-selected", self._on_row_selected)
        self.themes_list_box.connect("row-activated", self._on_row_activated)

        # Connessione pulsante Applica principale
        self.apply_button.connect("clicked", lambda _: self.confirm_and_apply_selected())

        # Connessione pulsanti di retry
        self.empty_refresh_button.connect("clicked", lambda _: self.refresh())
        self.error_retry_button.connect("clicked", lambda _: self.refresh())

        # Stato interno di caricamento e sequenza refresh per evitare race condition
        self._is_loading: bool = False
        self._generation_id: int = 0
        self.on_loading_changed: Callable[[bool], None] | None = None

        # Stato interno di applicazione per prevenire azioni concorrenti
        self._is_applying: bool = False
        self._apply_generation_id: int = 0
        self.on_theme_applied: Callable[[ThemeItemPresentation, ApplyResult], None] | None = None

        # Protezione da dialoghi di conferma concorrenti
        self._confirm_dialog_open: bool = False

        # Snapshot corrente dei temi acquisiti (immutabile)
        self._snapshot: ThemesSnapshot | None = None

        # Inizializza intestazione per la categoria predefinita
        self._update_category_header()

    def get_widget(self) -> Gtk.Widget:
        """Restituisce il widget radice per l'inserimento nel Gtk.Stack della finestra."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indica se è attualmente in corso un'operazione di scansione."""
        return self._is_loading

    @property
    def is_applying(self) -> bool:
        """Indica se è attualmente in corso un'operazione di applicazione tema."""
        return self._is_applying

    @property
    def current_snapshot(self) -> ThemesSnapshot | None:
        """Restituisce l'ultimo snapshot dei temi caricato con successo."""
        return self._snapshot

    @property
    def selected_theme(self) -> ThemeItemPresentation | None:
        """Restituisce il tema attualmente selezionato nella lista."""
        return self._selected_theme

    def set_category(self, category: ThemeType) -> None:
        """Imposta la categoria attiva visualizzata nella pagina.

        Args:
            category: Tipologia di tema da visualizzare (ThemeType.SHELL, GTK, ICON, CURSOR).
        """
        self.active_category = category
        self.title = CATEGORY_LABELS.get(category, "Temi")
        self._selected_theme = None
        self.apply_button.set_sensitive(False)
        self.selection_info_label.set_text("Seleziona un tema dall'elenco per applicarlo")
        self._update_category_header()

        if self._snapshot is not None and self.widget.get_visible_child_name() == "ready":
            self._update_filtered_list()

    def _update_category_header(self) -> None:
        """Aggiorna il titolo della categoria e della sezione temi disponibili."""
        title_text = CATEGORY_TITLES.get(self.active_category, "Temi")
        self.category_title_label.set_text(title_text)

    def refresh(self, sync: bool = False) -> None:
        """Avvia la scansione e l'aggiornamento dei temi installati dal backend.

        Args:
            sync: Se True, esegue l'operazione in modo sincrono e deterministico (usato nei test).
        """
        if (self._is_loading or self._is_applying) and not sync:
            logger.debug("Operazione già in corso: richiesta di refresh ignorata.")
            return

        self._is_loading = True
        self._generation_id += 1
        current_generation = self._generation_id

        # Notifica cambio stato, disabilita i controlli e passa alla vista loading
        if self.on_loading_changed:
            self.on_loading_changed(True)
        self.search_entry.set_sensitive(False)
        self.apply_button.set_sensitive(False)
        self.widget.set_visible_child_name("loading")

        def worker_fetch() -> tuple[ThemesSnapshot | None, Exception | None]:
            """Esegue la scansione dei temi e il recupero dello stato attivo interrogando il Facade ThemeManager."""
            try:
                if self.manager is None:
                    raise GnomeThemeManagerError("ThemeManager non disponibile o non inizializzato.")

                # Scansione di tutti i temi tramite API pubblica del Facade
                themes_list = self.manager.list_themes(theme_type=None, user_only=False)
                presentation_items = [build_theme_presentation(t) for t in themes_list]

                # Recupero dei temi attualmente attivi nel desktop
                active_map: dict[ThemeType, str | None] = {}
                try:
                    current_set = self.manager.get_current_themes()
                    if isinstance(current_set, ThemeSet):
                        active_map = {
                            ThemeType.GTK: current_set.gtk_theme if isinstance(current_set.gtk_theme, str) else None,
                            ThemeType.ICON: current_set.icon_theme if isinstance(current_set.icon_theme, str) else None,
                            ThemeType.CURSOR: current_set.cursor_theme if isinstance(current_set.cursor_theme, str) else None,
                            ThemeType.SHELL: current_set.shell_theme if isinstance(current_set.shell_theme, str) else None,
                        }
                except (GnomeThemeManagerError, OSError, PermissionError, GLib.GError, AttributeError, TypeError, ValueError) as err:
                    logger.warning("Impossibile recuperare i temi attivi correnti: %s", err)

                snapshot = ThemesSnapshot(items=presentation_items, active_themes=active_map)
                return snapshot, None
            except (GnomeThemeManagerError, OSError, PermissionError, TimeoutError) as err:
                return None, err
            except Exception as err:  # noqa: BLE001
                return None, GnomeThemeManagerError(f"Errore imprevisto durante la scansione: {err}")

        def on_fetch_completed(result: tuple[ThemesSnapshot | None, Exception | None]) -> bool:
            """Eseguito nel main context GTK per aggiornare i widget."""
            if current_generation != self._generation_id:
                logger.debug("Callback tardivo scartato: gen %d != %d", current_generation, self._generation_id)
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            if self.on_loading_changed:
                self.on_loading_changed(False)

            self.search_entry.set_sensitive(True)

            snapshot, error = result

            if error is not None:
                logger.error("Errore durante la scansione dei temi: %s", error)
                self._handle_error(error)
            elif snapshot is not None and not snapshot.items:
                self._snapshot = snapshot
                self._update_filtered_list()
                self.widget.set_visible_child_name("empty")
            elif snapshot is not None:
                self._snapshot = snapshot
                self._update_filtered_list()
                self.widget.set_visible_child_name("ready")
            else:
                self.widget.set_visible_child_name("empty")

            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_fetch()
            on_fetch_completed(res)
        else:
            def thread_target() -> None:
                res = worker_fetch()
                GLib.idle_add(on_fetch_completed, res)

            thread = threading.Thread(target=thread_target, daemon=True)
            thread.start()

    def _on_filter_criteria_changed(self, *args: Any) -> None:
        """Gestore dei cambiamenti nel testo di ricerca."""
        if self._snapshot is not None and self.widget.get_visible_child_name() == "ready":
            self._update_filtered_list()

    def _on_row_selected(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Gestore della selezione di una riga nella lista dei temi disponibili."""
        if row is not None and hasattr(row, "_theme_item"):
            self._selected_theme = row._theme_item
            self.apply_button.set_sensitive(not self._is_applying and not self._is_loading)
            self.selection_info_label.set_text(f"Selezionato: {self._selected_theme.name}")
        else:
            self._selected_theme = None
            self.apply_button.set_sensitive(False)
            self.selection_info_label.set_text("Seleziona un tema dall'elenco per applicarlo")

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Gestore dell'attivazione riga tramite doppio click (o tasto Invio).

        Seleziona la riga e avvia il percorso canonico confirm_and_apply_selected()
        per aprire il dialogo di conferma (senza applicare direttamente).
        """
        if row is None or not hasattr(row, "_theme_item"):
            return
        if self._is_loading or self._is_applying or self._confirm_dialog_open:
            return

        item: ThemeItemPresentation = row._theme_item
        logger.debug("row-activated: %s", item.name)

        list_box.select_row(row)
        self._selected_theme = item
        self.apply_button.set_sensitive(True)
        self.selection_info_label.set_text(f"Selezionato: {item.name}")

        self.confirm_and_apply_selected()

    def _update_filtered_list(self) -> None:
        """Aggiorna la card del tema attivo ed il contenuto filtrato della lista delle alternative."""
        if self._snapshot is None:
            return

        target_category = self.active_category
        active_theme_raw = self._snapshot.active_themes.get(target_category)
        active_theme_name = active_theme_raw if isinstance(active_theme_raw, str) else None

        # ---------------------------------------------------------------------
        # 1. Aggiornamento Card 'Tema Attivo'
        # ---------------------------------------------------------------------
        active_item: ThemeItemPresentation | None = None
        for item in self._snapshot.items:
            if item.theme_type == target_category and item.name == active_theme_name:
                active_item = item
                break

        icon_name = CATEGORY_ICONS.get(target_category, "preferences-desktop-theme-symbolic")
        self.active_theme_icon.set_from_icon_name(icon_name)

        if active_item is not None:
            self.active_theme_row.set_title(active_item.name)
            self.active_theme_row.set_subtitle(f"{active_item.origin_display}\n{active_item.path_display}")
            self.active_theme_badge.set_text("In uso")
            self.active_theme_badge.set_visible(True)
        elif active_theme_name:
            self.active_theme_row.set_title(active_theme_name)
            self.active_theme_row.set_subtitle("Tema non trovato nell'elenco locale")
            self.active_theme_badge.set_text("Non presente")
            self.active_theme_badge.set_visible(True)
        else:
            self.active_theme_row.set_title("Non disponibile")
            self.active_theme_row.set_subtitle("Nessuna impostazione rilevata o backend non disponibile")
            self.active_theme_badge.set_visible(False)

        # ---------------------------------------------------------------------
        # 2. Filtro Lista Altri Temi Disponibili (Esclude il tema attivo)
        # ---------------------------------------------------------------------
        query = self.search_entry.get_text().strip().lower()

        filtered: list[ThemeItemPresentation] = []
        for item in self._snapshot.items:
            if item.theme_type != target_category:
                continue
            # Esclusione logica del tema attualmente attivo dalla lista
            if active_theme_name is not None and item.name == active_theme_name:
                continue
            # Filtro per ricerca testuale
            if query and query not in item.name.lower():
                continue
            filtered.append(item)

        # Ordinamento deterministico con priorità:
        # 1. Temi Utente prima dei temi di Sistema (not is_user_level)
        # 2. Ordine alfabetico case-insensitive (name.casefold())
        # 3. Percorso di installazione deterministico (path_display)
        filtered.sort(key=lambda it: (not it.is_user_level, it.name.casefold(), it.path_display))

        # Svuotamento della lista precedente
        while child := self.themes_list_box.get_first_child():
            self.themes_list_box.remove(child)

        self._selected_theme = None
        self.apply_button.set_sensitive(False)
        self.selection_info_label.set_text("Seleziona un tema dall'elenco per applicarlo")

        # Aggiornamento widget risultati
        cat_label = CATEGORY_LABELS.get(target_category, "temi").lower()
        if not filtered:
            self.no_results_page.set_visible(True)
            self.themes_list_box.set_visible(False)
            if query:
                self.count_label.set_text(f"Nessun tema corrispondente a '{query}'")
            else:
                self.count_label.set_text(f"Nessun altro tema alternativo per {cat_label}")
        else:
            self.no_results_page.set_visible(False)
            self.themes_list_box.set_visible(True)
            self.count_label.set_text(f"{len(filtered)} altri {cat_label} disponibili")

            for item in filtered:
                row = Adw.ActionRow()
                row.set_title(item.name)
                row.set_subtitle(item.path_display)
                row.set_subtitle_lines(1)
                row.set_activatable(True)
                row._theme_item = item

                img = Gtk.Image.new_from_icon_name(item.icon_name)
                img.set_pixel_size(24)
                row.add_prefix(img)

                badge = Gtk.Label(label="Utente" if item.is_user_level else "Sistema")
                badge.add_css_class("caption")
                badge.add_css_class("dim-label")
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)

                self.themes_list_box.append(row)

    def confirm_and_apply_selected(self, parent_window: Gtk.Window | None = None, sync: bool = False) -> None:
        """Avvia la conferma e applicazione del tema attualmente selezionato."""
        if self._selected_theme is None:
            logger.warning("Tentativo di applicare un tema senza alcuna selezione attiva.")
            return
        if self._confirm_dialog_open:
            logger.debug("Dialogo di conferma già aperto: richiesta ignorata.")
            return

        self.confirm_and_apply_theme(self._selected_theme, parent_window=parent_window, sync=sync)

    def confirm_and_apply_theme(
        self,
        item: ThemeItemPresentation,
        parent_window: Gtk.Window | None = None,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
        sync: bool = False,
    ) -> None:
        """Mostra una finestra di conferma esplicita prima di procedere con l'applicazione del tema.

        Il dialogo presenta un layout pulito, leggibile e confortevole (larghezza minima ~500px):
        - Titolo: «Applicare “NOME_TEMA” a CATEGORIA?»
        - Categoria
        - Tema attualmente attivo (se presente nello snapshot)
        - Pulsanti «Annulla» (secondario) e «Applica» (principale/suggested).

        Args:
            item: Oggetto di presentazione del tema selezionato.
            parent_window: Finestra genitore per il dialogo (ricavata automaticamente se None).
            on_complete: Callback opzionale invocato al termine dell'applicazione.
            sync: Se True, esegue l'applicazione del backend in modo sincrono dopo la conferma.
        """
        if self._confirm_dialog_open:
            logger.debug("Dialogo di conferma già aperto per '%s': richiesta ignorata.", item.name)
            return

        win = parent_window or self.widget.get_root()

        cat_name = DIALOG_CATEGORY_NAMES.get(item.theme_type, item.category_display)
        heading = f"Applicare “{item.name}” a {cat_name}?"

        # Recupero del tema attualmente attivo per la categoria corrente
        active_theme_raw = self._snapshot.active_themes.get(item.theme_type) if self._snapshot else None
        active_name = active_theme_raw if isinstance(active_theme_raw, str) and active_theme_raw.strip() else None

        # Costruzione del contenitore descrittivo con larghezza confortevole (500px) e senza a capo
        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra_box.set_size_request(500, -1)
        extra_box.set_margin_top(6)
        extra_box.set_margin_bottom(12)
        extra_box.set_margin_start(16)
        extra_box.set_margin_end(16)
        extra_box.set_halign(Gtk.Align.CENTER)

        lbl_cat = Gtk.Label(label=f"Categoria: {cat_name}")
        lbl_cat.set_wrap(False)
        if hasattr(Pango, "EllipsizeMode"):
            lbl_cat.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_cat.set_halign(Gtk.Align.CENTER)
        extra_box.append(lbl_cat)

        if active_name:
            lbl_active = Gtk.Label(label=f"Tema attualmente attivo: {active_name}")
            lbl_active.set_wrap(False)
            if hasattr(Pango, "EllipsizeMode"):
                lbl_active.set_ellipsize(Pango.EllipsizeMode.END)
            lbl_active.add_css_class("dim-label")
            lbl_active.set_halign(Gtk.Align.CENTER)
            extra_box.append(lbl_active)

        # Dialogo moderno Libadwaita
        if hasattr(Adw, "AlertDialog"):
            self._confirm_dialog_open = True
            dialog = Adw.AlertDialog.new(heading=heading, body="")
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("apply", "Applica")
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_dialog_response(d: Any, response_param: Any) -> None:
                try:
                    if hasattr(d, "choose_finish") and not isinstance(response_param, str):
                        try:
                            resp = d.choose_finish(response_param)
                        except (GLib.GError, TypeError, ValueError):
                            resp = str(response_param)
                    else:
                        resp = str(response_param)

                    if resp == "apply":
                        self.apply_theme(item, on_complete=on_complete, sync=sync)
                    elif on_complete:
                        on_complete(None, None)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_dialog_response)
            dialog.present(win if isinstance(win, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            self._confirm_dialog_open = True
            dialog = Adw.MessageDialog.new(
                win if isinstance(win, Gtk.Window) else None,
                heading,
                "",
            )
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("apply", "Applica")
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                try:
                    if response_id == "apply":
                        self.apply_theme(item, on_complete=on_complete, sync=sync)
                    elif on_complete:
                        on_complete(None, None)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_md_response)
            dialog.present()

        else:
            self._confirm_dialog_open = False
            self.apply_theme(item, on_complete=on_complete, sync=sync)

    def apply_theme(
        self,
        item: ThemeItemPresentation,
        on_complete: Callable[[ApplyResult | None, Exception | None], None] | None = None,
        sync: bool = False,
    ) -> None:
        """Applica il singolo tema selezionato tramite il Facade ThemeManager.

        Mappatura per componente:
            - GTK -> ThemeSet(gtk_theme=item.name)
            - ICON -> ThemeSet(icon_theme=item.name)
            - CURSOR -> ThemeSet(cursor_theme=item.name)
            - SHELL -> ThemeSet(shell_theme=item.name)

        Args:
            item: Oggetto di presentazione del tema da applicare.
            on_complete: Callback opzionale (result, error) eseguito a completamento.
            sync: Se True, esegue l'operazione in modo sincrono (utile per i test).
        """
        if self._is_applying:
            logger.warning("Un'applicazione tema è già in corso. Richiesta scartata.")
            if on_complete:
                on_complete(None, GnomeThemeManagerError("Applicazione già in corso."))
            return

        self._is_applying = True
        self._apply_generation_id += 1
        current_apply_gen = self._apply_generation_id

        # Disabilita controlli e pulsanti per prevenire azioni concorrenti
        self._set_ui_applying_state(True)

        theme_set = self._build_theme_set_for_item(item)

        def worker_apply() -> tuple[ApplyResult | None, Exception | None]:
            """Esegue l'applicazione nel worker di background."""
            try:
                if self.manager is None:
                    raise GnomeThemeManagerError("ThemeManager non disponibile o non inizializzato.")

                result = self.manager.apply_themes(
                    theme_set=theme_set,
                    apply_gtk4_override=True,
                    propagate_sandbox=True,
                )
                return result, None
            except Exception as err:  # noqa: BLE001
                return None, err

        def on_apply_completed(result: tuple[ApplyResult | None, Exception | None]) -> bool:
            """Eseguito nel main context GTK per notificare l'esito e aggiornare i widget."""
            if current_apply_gen != self._apply_generation_id:
                logger.debug("Callback di applicazione tardivo scartato.")
                return GLib.SOURCE_REMOVE

            self._is_applying = False
            self._set_ui_applying_state(False)

            apply_result, error = result

            if error is not None:
                logger.error("Errore durante l'applicazione del tema '%s': %s", item.name, error)
                self._show_toast(f"Errore durante l'applicazione di '{item.name}': {error}")
            elif apply_result is not None:
                # 1. Verifica specifica per GNOME Shell (estensione User Themes mancante)
                if item.theme_type == ThemeType.SHELL and apply_result.shell_theme is None:
                    warning_text = (
                        f"Impossibile applicare il tema Shell '{item.name}': "
                        "estensione 'User Themes' non attiva o non supportata."
                    )
                    logger.warning(warning_text)
                    self._show_toast(warning_text)
                else:
                    # 2. Creazione di un nuovo Snapshot immutabile con il nuovo tema attivo
                    new_active_map = dict(self._snapshot.active_themes) if self._snapshot else {}
                    new_active_map[item.theme_type] = item.name

                    current_items = list(self._snapshot.items) if self._snapshot else [item]
                    self._snapshot = ThemesSnapshot(items=current_items, active_themes=new_active_map)

                    # 3. Propagazione immediata del cursore in-process (per tema Cursore)
                    if item.theme_type == ThemeType.CURSOR:
                        self._propagate_cursor_theme_in_process(item.name)

                    # 4. Aggiornamento visivo della Card e della Lista (esclusione nuovo tema attivo)
                    self._update_filtered_list()

                    # 5. Notifica di successo univoca
                    if item.theme_type == ThemeType.CURSOR:
                        logger.info("Tema cursore '%s' applicato: mostro alert informativo", item.name)
                        self._show_cursor_info_alert(item.name)
                    else:
                        cat_name = CATEGORY_LABELS.get(item.theme_type, "Tema")
                        if item.theme_type == ThemeType.GTK:
                            if apply_result.gtk4_override_applied:
                                msg = f"Tema GTK «{item.name}» applicato (con override GTK4/Libadwaita)"
                            else:
                                msg = f"Tema GTK «{item.name}» applicato"
                        else:
                            msg = f"Tema {cat_name} «{item.name}» applicato"

                        if apply_result.warnings:
                            msg += f" (Avvisi: {'; '.join(apply_result.warnings)})"

                        logger.info("Tema '%s' applicato: %s", item.name, msg)
                        self._show_toast(msg)

                    # Notifica listener esterno (StatusPage) senza duplicare il Toast
                    if self.on_theme_applied:
                        self.on_theme_applied(item, apply_result)

            if on_complete:
                on_complete(apply_result, error)

            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_apply()
            on_apply_completed(res)
        else:
            def thread_target() -> None:
                res = worker_apply()
                GLib.idle_add(on_apply_completed, res)

            thread = threading.Thread(target=thread_target, daemon=True)
            thread.start()

    def _propagate_cursor_theme_in_process(self, cursor_theme_name: str) -> bool:
        """Propaga immediatamente il nuovo tema del cursore al display GTK dell'applicazione.

        Aggiorna il setting in-process `gtk-cursor-theme-name` sul display GDK attivo,
        evitando il ritardo di propagazione asincrona di dconf/GSettings.

        Args:
            cursor_theme_name: Nome del tema cursore appena applicato.

        Returns:
            True se la proprietà in-process è stata impostata con successo, False altrimenti.
        """
        try:
            display = Gdk.Display.get_default() if hasattr(Gdk, "Display") else None
            if display is None:
                return False

            if hasattr(Gtk.Settings, "get_for_display"):
                gtk_settings = Gtk.Settings.get_for_display(display)
            elif hasattr(Gtk.Settings, "get_default"):
                gtk_settings = Gtk.Settings.get_default()
            else:
                gtk_settings = None

            if gtk_settings is not None and hasattr(gtk_settings, "set_property"):
                gtk_settings.set_property("gtk-cursor-theme-name", cursor_theme_name)
                logger.debug(
                    "Propagato immediatamente gtk-cursor-theme-name='%s' al display GTK in-process.",
                    cursor_theme_name,
                )

            # Resetta il cursore della finestra principale per forzare il refresh della forma
            root = self.widget.get_root()
            if root is not None and hasattr(root, "set_cursor"):
                root.set_cursor(None)

            return True
        except (GLib.GError, AttributeError, TypeError, ValueError, RuntimeError) as err:
            logger.warning("Impossibile aggiornare gtk-cursor-theme-name in-process: %s", err)
            return False

    def _show_cursor_info_alert(self, cursor_name: str) -> None:
        """Mostra un dialogo informativo non distruttivo dopo l'applicazione di un tema cursore."""
        win = self.widget.get_root()
        heading = "Tema cursore applicato"
        body = (
            f"Il tema dei cursori «{cursor_name}» è stato configurato nel sistema.\n\n"
            "Il nuovo cursore potrebbe non essere visibile immediatamente in tutte le finestre.\n"
            "Cambia finestra oppure riapri l'applicazione interessata per visualizzare sicuramente il cambiamento."
        )

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(heading=heading, body=body)
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.set_close_response("ok")
            dialog.present(win if isinstance(win, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                win if isinstance(win, Gtk.Window) else None,
                heading,
                body,
            )
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.set_close_response("ok")
            dialog.present()

    def _build_theme_set_for_item(self, item: ThemeItemPresentation) -> ThemeSet:
        """Crea un'istanza ThemeSet configurando esclusivamente il componente specificato.

        Args:
            item: Oggetto di presentazione del tema.

        Returns:
            Istanza ThemeSet con il campo target impostato.
        """
        if item.theme_type == ThemeType.GTK:
            return ThemeSet(gtk_theme=item.name)
        elif item.theme_type == ThemeType.ICON:
            return ThemeSet(icon_theme=item.name)
        elif item.theme_type == ThemeType.CURSOR:
            return ThemeSet(cursor_theme=item.name)
        elif item.theme_type == ThemeType.SHELL:
            return ThemeSet(shell_theme=item.name)
        return ThemeSet()

    def _set_ui_applying_state(self, is_applying: bool) -> None:
        """Abilita o disabilita i controlli durante l'applicazione del tema."""
        self.search_entry.set_sensitive(not is_applying)
        self.themes_list_box.set_sensitive(not is_applying)
        if self._selected_theme is not None:
            self.apply_button.set_sensitive(not is_applying)
        else:
            self.apply_button.set_sensitive(False)

    def _show_toast(self, message: str) -> None:
        """Invia un toast unico alla finestra principale se disponibile."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "add_toast"):
            root.add_toast(message)

    def _handle_error(self, error: Exception) -> None:
        """Gestisce gli errori di scansione impostando la schermata 'error'.

        Args:
            error: Eccezione verificatasi durante la scansione.
        """
        if isinstance(error, GnomeThemeManagerError):
            user_msg = str(error)
        elif isinstance(error, PermissionError):
            user_msg = "Permessi insufficienti per accedere ad alcune cartelle dei temi."
        elif isinstance(error, OSError):
            user_msg = f"Errore di accesso al filesystem: {error}"
        else:
            user_msg = f"Si è verificato un errore durante la scansione: {error}"

        self.error_page.set_description(user_msg)
        self.widget.set_visible_child_name("error")
