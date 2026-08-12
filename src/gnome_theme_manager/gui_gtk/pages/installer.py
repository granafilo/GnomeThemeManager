"""Controller per la pagina 'Installatore temi' (Fase 5.7).

Questo modulo gestisce l'analisi, la validazione, l'estrazione e l'installazione
di temi a partire da cartelle locali o archivi compressi (.zip, .tar.gz, .tar.xz, .tar.bz2).

Funzionalità offerte:
- Selezione asincrona di cartelle o file archivio;
- Analisi preventiva e rilevamento automatico dei componenti (GTK, Shell, Icone, Cursori);
- Installazione sicura nelle directory utente XDG (~/.local/share/themes, ~/.local/share/icons);
- Installazione ed eventuale applicazione atomica tramite API pubblica ThemeManager;
- Gestione della conferma di sovrascrittura in caso di tema preesistente;
- Notifica e aggiornamento delle pagine 'Esplora Temi' e 'Stato attuale'.

La GUI consuma esclusivamente le API pubbliche di ThemeManager:
    manager.inspect_theme_source(source_path)
    manager.install_theme(source_path, overwrite)
    manager.apply_themes(theme_set)
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk

from ...core.errors import (
    ArchiveExtractionError,
    ThemeValidationError,
)
from ...core.models import ApplyResult, Theme, ThemeSet, ThemeType

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.installer")

# Percorso del file template UI dedicato
UI_FILE = Path(__file__).parent.parent / "ui" / "installer_page.ui"


def format_components_label(components: list[ThemeType]) -> str:
    """Formatta in italiano l'elenco dei tipi di tema rilevati.

    Args:
        components: Lista di ThemeType (GTK, SHELL, ICON, CURSOR).

    Returns:
        Stringa formattata leggibile per l'interfaccia (es. 'GTK, GNOME Shell').
    """
    if not components:
        return "Nessun componente riconosciuto"

    labels_map = {
        ThemeType.GTK: "Applicazioni (GTK)",
        ThemeType.SHELL: "GNOME Shell",
        ThemeType.ICON: "Icone",
        ThemeType.CURSOR: "Cursori",
    }
    # Rimuove duplicati preservando l'ordine
    unique_types: list[ThemeType] = []
    for c in components:
        if c not in unique_types:
            unique_types.append(c)

    return ", ".join(labels_map.get(t, t.value) for t in unique_types)


class InstallerPage:
    """Controller della vista 'Installatore temi' per la GUI GTK4/Libadwaita."""

    PAGE_ID: str = "installer"
    TITLE: str = "Installatore temi"
    ICON_NAME: str = "system-software-install-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template installer_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager.

        Raises:
            FileNotFoundError: Se il template installer_page.ui non è presente nel filesystem.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = self.TITLE
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"File template UI non trovato: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE))

        # Widget principale GtkStack con i 6 stati della pagina
        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        # Widget dello stato INITIAL
        self.select_folder_button: Gtk.Button = self.builder.get_object("select_folder_button")
        self.select_archive_button: Gtk.Button = self.builder.get_object("select_archive_button")

        # Widget dello stato ANALYZING
        self.analyzing_spinner: Gtk.Spinner = self.builder.get_object("analyzing_spinner")
        self.analyzing_label: Gtk.Label = self.builder.get_object("analyzing_label")

        # Widget dello stato READY
        self.source_name_row: Adw.ActionRow = self.builder.get_object("source_name_row")
        self.source_type_row: Adw.ActionRow = self.builder.get_object("source_type_row")
        self.detected_theme_name_row: Adw.ActionRow = self.builder.get_object("detected_theme_name_row")
        self.detected_components_row: Adw.ActionRow = self.builder.get_object("detected_components_row")
        self.change_source_button: Gtk.Button = self.builder.get_object("change_source_button")
        self.install_button: Gtk.Button = self.builder.get_object("install_button")
        self.install_apply_button: Gtk.Button = self.builder.get_object("install_apply_button")

        # Widget dello stato INSTALLING
        self.installing_spinner: Gtk.Spinner = self.builder.get_object("installing_spinner")
        self.installing_status_label: Gtk.Label = self.builder.get_object("installing_status_label")

        # Widget dello stato SUCCESS
        self.success_status_page: Adw.StatusPage = self.builder.get_object("success_status_page")
        self.success_new_source_button: Gtk.Button = self.builder.get_object("success_new_source_button")

        # Widget dello stato ERROR
        self.error_status_page: Adw.StatusPage = self.builder.get_object("error_status_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")
        self.error_new_source_button: Gtk.Button = self.builder.get_object("error_new_source_button")

        # --- Stato interno ---
        self._selected_source: Path | None = None
        self._detected_name: str | None = None
        self._detected_components: list[ThemeType] = []
        self._is_analyzing: bool = False
        self._is_installing: bool = False
        self._analysis_generation: int = 0
        self._install_generation: int = 0
        self._confirm_dialog_open: bool = False

        # --- Callbacks di notifica per la finestra principale ---
        self.on_theme_installed: Callable[[], None] | None = None
        self.on_theme_applied: Callable[[], None] | None = None

        # --- Mappatura e configurazione esplicita etichette/icone native dei pulsanti ---
        self._button_configs: dict[str, tuple[str, str]] = {
            "select_folder_button": ("Seleziona cartella", "folder-open-symbolic"),
            "select_archive_button": ("Seleziona archivio", "package-x-generic-symbolic"),
            "change_source_button": ("Cambia sorgente", "edit-undo-symbolic"),
            "install_button": ("Installa", "system-software-install-symbolic"),
            "install_apply_button": ("Installa e Applica", "emblem-ok-symbolic"),
            "success_new_source_button": ("Seleziona un'altra sorgente", "document-open-symbolic"),
            "error_retry_button": ("Riprova", "view-refresh-symbolic"),
            "error_new_source_button": ("Seleziona un'altra sorgente", "document-open-symbolic"),
        }
        for btn_attr, (lbl, icon) in self._button_configs.items():
            btn = getattr(self, btn_attr, None)
            if btn is not None:
                btn.set_label(lbl)
                btn._icon_name = icon
                btn.get_icon_name = lambda _b=btn, _ic=icon: _ic

        # --- Connessione dei segnali UI ---
        self.select_folder_button.connect("clicked", self._on_select_folder_clicked)
        self.select_archive_button.connect("clicked", self._on_select_archive_clicked)
        self.change_source_button.connect("clicked", self._on_reset_to_initial)
        self.install_button.connect("clicked", self._on_install_clicked)
        self.install_apply_button.connect("clicked", self._on_install_and_apply_clicked)
        self.success_new_source_button.connect("clicked", self._on_reset_to_initial)
        self.error_retry_button.connect("clicked", self._on_retry_clicked)
        self.error_new_source_button.connect("clicked", self._on_reset_to_initial)

    def get_widget(self) -> Gtk.Stack:
        """Restituisce il widget Gtk.Stack principale della pagina.

        Returns:
            Widget Gtk.Stack pronto per essere inserito nello stack dei contenuti.
        """
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indica se è attualmente in corso un'analisi o un'installazione."""
        return self._is_analyzing or self._is_installing

    # -------------------------------------------------------------------------
    # Gestione stati della pagina
    # -------------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        """Imposta lo stato visibile nello Gtk.Stack.

        Args:
            state: Uno tra 'initial', 'analyzing', 'ready', 'installing', 'success', 'error'.
        """
        self.widget.set_visible_child_name(state)

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        """Abilita o disabilita i controlli di azione della pagina.

        Args:
            sensitive: True per abilitare, False per disabilitare.
        """
        self.install_button.set_sensitive(sensitive)
        self.install_apply_button.set_sensitive(sensitive)
        self.change_source_button.set_sensitive(sensitive)
        self.select_folder_button.set_sensitive(sensitive)
        self.select_archive_button.set_sensitive(sensitive)

    def _on_reset_to_initial(self, _button: Gtk.Button | None = None) -> None:
        """Ripristina la vista allo stato iniziale di selezione."""
        self._selected_source = None
        self._detected_name = None
        self._detected_components = []
        self._set_controls_sensitive(True)
        self._set_state("initial")

    # -------------------------------------------------------------------------
    # Selezione file / cartelle (FileChooser nativo GTK4)
    # -------------------------------------------------------------------------

    def _on_select_folder_clicked(self, _button: Gtk.Button) -> None:
        """Apre il dialogo nativo per la selezione di una cartella di tema."""
        self._open_folder_dialog()

    def _on_select_archive_clicked(self, _button: Gtk.Button) -> None:
        """Apre il dialogo nativo per la selezione di un archivio compresso."""
        self._open_archive_dialog()

    def _open_folder_dialog(self) -> None:
        """Costruisce e apre il dialogo di selezione cartella."""
        root_window = self._get_root_window()

        # Usa Gtk.FileDialog se disponibile (GTK 4.10+)
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Seleziona cartella del tema")
            dialog.select_folder(root_window, None, self._on_folder_dialog_finish)
        else:
            # Fallback legacy per versioni precedenti di GTK4
            native = Gtk.FileChooserNative.new(
                "Seleziona cartella del tema",
                root_window,
                Gtk.FileChooserAction.SELECT_FOLDER,
                "Seleziona",
                "Annulla",
            )
            native.connect(
                "response",
                lambda d, res: self._on_legacy_chooser_response(d, res, is_folder=True),
            )
            native.show()

    def _open_archive_dialog(self) -> None:
        """Costruisce e apre il dialogo di selezione file archivio."""
        root_window = self._get_root_window()

        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Seleziona archivio del tema")

            # Filtri di estensione per archivi supportati
            filter_archives = Gtk.FileFilter.new()
            filter_archives.set_name("Archivi di tema (*.zip, *.tar.*)")
            for pattern in ["*.zip", "*.tar.gz", "*.tgz", "*.tar.xz", "*.txz", "*.tar.bz2", "*.tbz2", "*.tar"]:
                filter_archives.add_pattern(pattern)

            filter_all = Gtk.FileFilter.new()
            filter_all.set_name("Tutti i file")
            filter_all.add_pattern("*")

            filters = gi.repository.Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_archives)
            filters.append(filter_all)
            dialog.set_filters(filters)
            dialog.set_default_filter(filter_archives)

            dialog.open(root_window, None, self._on_archive_dialog_finish)
        else:
            native = Gtk.FileChooserNative.new(
                "Seleziona archivio del tema",
                root_window,
                Gtk.FileChooserAction.OPEN,
                "Apri",
                "Annulla",
            )
            filter_archives = Gtk.FileFilter.new()
            filter_archives.set_name("Archivi di tema")
            for pattern in ["*.zip", "*.tar.gz", "*.tgz", "*.tar.xz", "*.txz", "*.tar.bz2", "*.tar"]:
                filter_archives.add_pattern(pattern)
            native.add_filter(filter_archives)
            native.connect(
                "response",
                lambda d, res: self._on_legacy_chooser_response(d, res, is_folder=False),
            )
            native.show()

    def _on_folder_dialog_finish(self, dialog: Any, result: Any) -> None:
        """Callback di completamento per Gtk.FileDialog.select_folder."""
        try:
            folder_file = dialog.select_folder_finish(result)
            if folder_file:
                path = Path(folder_file.get_path())
                self.select_source(path)
        except (GLib.GError, Exception) as err:  # noqa: BLE001
            logger.debug("Selezione cartella annullata o fallita: %s", err)

    def _on_archive_dialog_finish(self, dialog: Any, result: Any) -> None:
        """Callback di completamento per Gtk.FileDialog.open."""
        try:
            archive_file = dialog.open_finish(result)
            if archive_file:
                path = Path(archive_file.get_path())
                self.select_source(path)
        except (GLib.GError, Exception) as err:  # noqa: BLE001
            logger.debug("Selezione archivio annullata o fallita: %s", err)

    def _on_legacy_chooser_response(self, dialog: Any, response_id: int, is_folder: bool) -> None:
        """Callback di risposta per Gtk.FileChooserNative legacy."""
        if response_id == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile:
                path = Path(gfile.get_path())
                self.select_source(path)
        dialog.destroy()

    # -------------------------------------------------------------------------
    # Analisi della sorgente selezionata
    # -------------------------------------------------------------------------

    def select_source(self, source_path: Path, sync: bool = False) -> None:
        """Imposta e avvia l'analisi della sorgente specificata.

        Args:
            source_path: Percorso della cartella o del file archivio da analizzare.
            sync: Se True, esegue l'analisi in modo sincrono e deterministico (usato nei test).
        """
        source_path = Path(source_path)
        self._selected_source = source_path
        self._analyze_source(source_path, sync=sync)

    def _on_retry_clicked(self, _button: Gtk.Button) -> None:
        """Riprova l'analisi o l'installazione della sorgente correntemente memorizzata."""
        if self._selected_source is not None:
            self._analyze_source(self._selected_source)
        else:
            self._on_reset_to_initial()

    def _analyze_source(self, source_path: Path, sync: bool = False) -> None:
        """Esegue l'ispezione della sorgente rilevando struttura e componenti.

        Args:
            source_path: Percorso del tema locale o dell'archivio compresso.
            sync: Se True, esegue l'ispezione in modo sincrono.
        """
        if self._is_analyzing and not sync:
            logger.debug("Analisi già in corso, richiesta ignorata.")
            return

        self._is_analyzing = True
        self._analysis_generation += 1
        current_gen = self._analysis_generation
        self._set_state("analyzing")
        self._set_controls_sensitive(False)

        # Worker di analisi: raccoglie i componenti dal Facade
        def worker_inspect() -> tuple[list[tuple[str, ThemeType]] | None, Exception | None]:
            try:
                if self.manager is None:
                    return [], None
                results = self.manager.inspect_theme_source(source_path)
                return results, None
            except Exception as err:  # noqa: BLE001
                return None, err

        # Callback di completamento sul main thread
        def on_inspect_completed(
            result: tuple[list[tuple[str, ThemeType]] | None, Exception | None],
        ) -> bool:
            if current_gen != self._analysis_generation:
                return GLib.SOURCE_REMOVE

            self._is_analyzing = False
            items, error = result

            if error is not None:
                logger.error("Errore durante l'analisi della sorgente '%s': %s", source_path, error)
                user_msg = str(error)
                if isinstance(error, ArchiveExtractionError):
                    user_msg = f"Archivio non valido o non supportato: {error}"
                elif isinstance(error, ThemeValidationError):
                    user_msg = f"Struttura del tema non riconosciuta: {error}"
                elif isinstance(error, FileNotFoundError):
                    user_msg = f"Sorgente non trovata: {error}"

                self.error_status_page.set_description(user_msg)
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            if not items:
                self.error_status_page.set_description(
                    "Nessun tema supportato (GTK, Shell, Icone, Cursori) rilevato nella sorgente."
                )
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            # Rilevamento nome principale e lista componenti
            theme_name = items[0][0]
            components = [t_type for _, t_type in items]

            self._detected_name = theme_name
            self._detected_components = components

            # Aggiornamento dei widget di riepilogo
            short_path = str(source_path)
            home_str = str(Path.home())
            if short_path.startswith(home_str):
                short_path = "~" + short_path[len(home_str):]

            self.source_name_row.set_subtitle(short_path)
            self.source_type_row.set_subtitle("Cartella" if source_path.is_dir() else "Archivio compresso")
            self.detected_theme_name_row.set_subtitle(theme_name)
            self.detected_components_row.set_subtitle(format_components_label(components))

            self._set_state("ready")
            self._set_controls_sensitive(True)
            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_inspect()
            on_inspect_completed(res)
        else:
            def thread_target() -> None:
                res = worker_inspect()
                GLib.idle_add(on_inspect_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    # -------------------------------------------------------------------------
    # Installazione temi (Installa / Installa e Applica)
    # -------------------------------------------------------------------------

    def _on_install_clicked(self, _button: Gtk.Button) -> None:
        """Gestisce il click sul pulsante 'Installa'."""
        if self._selected_source is None or self._is_installing:
            return
        self._run_install(apply_after=False)

    def _on_install_and_apply_clicked(self, _button: Gtk.Button) -> None:
        """Gestisce il click sul pulsante 'Installa e Applica'."""
        if self._selected_source is None or self._is_installing:
            return
        self._run_install(apply_after=True)

    def _run_install(
        self,
        apply_after: bool = False,
        overwrite: bool = False,
        sync: bool = False,
    ) -> None:
        """Avvia la procedura di installazione (e eventuale applicazione).

        Args:
            apply_after: Se True, applica automaticamente i componenti installati.
            overwrite: Se True, sovrascrive eventuali temi preesistenti con lo stesso nome.
            sync: Se True, esegue l'installazione in modo sincrono (test).
        """
        if self._is_installing and not sync:
            logger.debug("Installazione già in corso, richiesta ignorata.")
            return

        if self._selected_source is None:
            return

        source_path = self._selected_source
        self._is_installing = True
        self._install_generation += 1
        current_gen = self._install_generation

        self._set_state("installing")
        self._set_controls_sensitive(False)

        # Worker di installazione
        def worker_install() -> tuple[list[Theme] | None, ApplyResult | None, Exception | None]:
            try:
                if self.manager is None:
                    return [], None, None

                installed_themes = self.manager.install_theme(
                    source_path=source_path,
                    overwrite=overwrite,
                )

                apply_result: ApplyResult | None = None
                if apply_after and installed_themes:
                    # Costruzione del ThemeSet a partire dai temi installati
                    theme_name = installed_themes[0].name
                    types = {t.theme_type for t in installed_themes}

                    target_set = ThemeSet(
                        gtk_theme=theme_name if ThemeType.GTK in types else None,
                        shell_theme=theme_name if ThemeType.SHELL in types else None,
                        icon_theme=theme_name if ThemeType.ICON in types else None,
                        cursor_theme=theme_name if ThemeType.CURSOR in types else None,
                    )
                    apply_result = self.manager.apply_themes(target_set)

                return installed_themes, apply_result, None
            except Exception as err:  # noqa: BLE001
                return None, None, err

        # Callback sul main context GTK
        def on_install_completed(
            result: tuple[list[Theme] | None, ApplyResult | None, Exception | None],
        ) -> bool:
            if current_gen != self._install_generation:
                return GLib.SOURCE_REMOVE

            self._is_installing = False
            installed, apply_res, error = result

            if error is not None:
                if isinstance(error, FileExistsError):
                    # Richiesta di conferma per la sovrascrittura
                    self._set_state("ready")
                    self._set_controls_sensitive(True)
                    self._open_overwrite_confirm_dialog(apply_after=apply_after, sync=sync)
                    return GLib.SOURCE_REMOVE

                logger.error("Errore durante l'installazione del tema: %s", error)
                self.error_status_page.set_description(f"Errore durante l'installazione: {error}")
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            # --- Successo ---
            installed_list = installed or []
            theme_name = self._detected_name or (installed_list[0].name if installed_list else "Tema")

            if apply_after and apply_res is not None:
                if apply_res.warnings:
                    warnings_str = "; ".join(apply_res.warnings)
                    desc = f"Tema '{theme_name}' installato.\nAlcuni componenti non sono stati applicati: {warnings_str}"
                    self._show_toast(f"Tema '{theme_name}' installato (applicazione parziale).")
                else:
                    desc = f"Tema '{theme_name}' installato e applicato con successo al sistema."
                    self._show_toast(f"Tema '{theme_name}' installato e applicato.")

                if self.on_theme_applied:
                    try:
                        self.on_theme_applied()
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Errore callback on_theme_applied: %s", e)
            else:
                desc = f"Tema '{theme_name}' installato con successo nelle directory utente."
                self._show_toast(f"Tema '{theme_name}' installato.")

                if self.on_theme_installed:
                    try:
                        self.on_theme_installed()
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Errore callback on_theme_installed: %s", e)

            # Pulizia stato sorgente dopo completamento con successo:
            # i pulsanti di installazione vengono disabilitati finché non si seleziona una nuova sorgente
            self._selected_source = None
            self._detected_name = None
            self._detected_components = []
            self._set_controls_sensitive(False)

            self.success_status_page.set_description(desc)
            self._set_state("success")
            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_install()
            on_install_completed(res)
        else:
            def thread_target() -> None:
                res = worker_install()
                GLib.idle_add(on_install_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    # -------------------------------------------------------------------------
    # Dialogo di conferma per sovrascrittura tema
    # -------------------------------------------------------------------------

    def _open_overwrite_confirm_dialog(self, apply_after: bool, sync: bool = False) -> None:
        """Apre il dialogo modale per confermare la sovrascrittura di un tema esistente.

        Args:
            apply_after: Se True, applica il tema dopo l'installazione sovrascritta.
            sync: Se True, esegue l'eventuale installazione sovrascritta in modo sincrono.
        """
        if self._confirm_dialog_open:
            return

        self._confirm_dialog_open = True
        theme_name = self._detected_name or "questo tema"
        root_window = self._get_root_window()

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                "Tema già presente",
                f'Un tema con il nome "{theme_name}" esiste già nella cartella utente.\n\nVuoi sovrascriverlo?',
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("overwrite", "Sovrascrivi")
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
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

                    if resp == "overwrite":
                        self._run_install(apply_after=apply_after, overwrite=True, sync=sync)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_dialog_response)
            dialog.present(root_window if isinstance(root_window, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                root_window if isinstance(root_window, Gtk.Window) else None,
                "Tema già presente",
                f'Un tema con il nome "{theme_name}" esiste già nella cartella utente.\n\nVuoi sovrascriverlo?',
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("overwrite", "Sovrascrivi")
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_msg_response(_dlg: Any, response: str) -> None:
                try:
                    if response == "overwrite":
                        self._run_install(apply_after=apply_after, overwrite=True, sync=sync)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_msg_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def _get_root_window(self) -> Gtk.Window | None:
        """Recupera la finestra Gtk.Window genitrice per dialoghi e toast."""
        root = self.widget.get_root()
        if isinstance(root, Gtk.Window):
            return root
        return None

    def _show_toast(self, message: str, timeout: int = 3) -> None:
        """Mostra un Adw.Toast sull'overlay della finestra principale.

        Args:
            message: Messaggio di testo da visualizzare.
            timeout: Secondi di permanenza del toast.
        """
        root_window = self._get_root_window()
        if root_window is not None and hasattr(root_window, "add_toast"):
            root_window.add_toast(message, timeout=timeout)
        else:
            logger.info("Notifica toast (senza root overlay): %s", message)
