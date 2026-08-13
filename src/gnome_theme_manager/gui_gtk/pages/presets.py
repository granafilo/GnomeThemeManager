"""Controller per la pagina 'Profili e preset' (Fase 5.6).

Questo modulo implementa la gestione completa dei preset di configurazione desktop GNOME
tramite le API pubbliche di ThemeManager:
- Visualizzazione dei preset salvati (stati: loading, ready, empty, error);
- Salvataggio della configurazione attuale con dialogo di input e validazione nome;
- Applicazione di un preset esistente con conferma modale e riepilogo componenti;
- Eliminazione di un preset con conferma modale;
- Ricarica locale della lista senza refresh globale dell'interfaccia;
- Aggiornamento asincrono thread-safe tramite GLib.idle_add.

La GUI usa esclusivamente le API pubbliche di ThemeManager:
    manager.list_presets()
    manager.load_preset(name)
    manager.save_current_as_preset(name, overwrite)
    manager.apply_preset(name)
    manager.delete_preset(name)

Non accede a manager._presets né a percorsi filesystem.
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
gi.require_version("Pango", "1.0")
from gi.repository import Adw, GLib, Gtk, Pango

from ...core.errors import GnomeThemeManagerError
from ...core.models import ThemeSet

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.presets")

# Percorso del file template UI dedicato
UI_FILE = Path(__file__).parent.parent / "ui" / "presets_page.ui"

# Lunghezza massima consentita per il nome di un preset nel dialogo di input
PRESET_NAME_MAX_LEN: int = 255

# Etichette leggibili per i componenti del ThemeSet nel riepilogo dei preset
_COMPONENT_LABELS: dict[str, str] = {
    "gtk_theme": "GTK",
    "icon_theme": "Icone",
    "cursor_theme": "Cursori",
    "color_scheme": "Schema colori",
    "shell_theme": "GNOME Shell",
}


def _build_preset_summary(theme_set: ThemeSet) -> str:
    """Costruisce una stringa riepilogativa leggibile dei componenti di un ThemeSet.

    Mostra solo i componenti valorizzati (non None). Non include percorsi filesystem.

    Args:
        theme_set: Il ThemeSet del preset da descrivere.

    Returns:
        Stringa multiriga con i componenti del preset (es. 'GTK: Nordic\\nIcone: Papirus').
        Se il ThemeSet è vuoto restituisce 'Nessun componente valorizzato'.
    """
    lines: list[str] = []
    # Itera in ordine fisso per presentazione coerente
    for field, label in _COMPONENT_LABELS.items():
        value = getattr(theme_set, field, None)
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines) if lines else "Nessun componente valorizzato"


class _PresetRow(Adw.ActionRow):
    """Riga Libadwaita per la visualizzazione di un singolo preset nella lista.

    Ogni riga mostra il nome del preset, un riepilogo leggibile dei componenti,
    un pulsante 'Applica' e un pulsante 'Elimina'. Se il ThemeSet non è
    recuperabile (preset corrotto), viene mostrato uno stato di errore.
    """

    def __init__(
        self,
        preset_name: str,
        theme_set: ThemeSet | None,
        on_apply: Callable[[str], None],
        on_delete: Callable[[str], None],
    ) -> None:
        """Costruisce la riga per un singolo preset.

        Args:
            preset_name: Nome del preset (senza estensione .json).
            theme_set: ThemeSet con i componenti del preset, o None se corrotto.
            on_apply: Callback invocato con il nome del preset al click su 'Applica'.
            on_delete: Callback invocato con il nome del preset al click su 'Elimina'.
        """
        super().__init__()
        self._preset_name = preset_name

        self.set_title(preset_name)

        if theme_set is not None:
            # Riepilogo leggibile dei componenti
            summary = _build_preset_summary(theme_set)
            self.set_subtitle(summary)
        else:
            # Preset corrotto: stato di errore visivo
            self.set_subtitle("⚠ Preset non leggibile — dati corrotti o incompleti")
            self.add_css_class("error")

        # Icona del preset nella parte sinistra (prefix)
        icon = Gtk.Image.new_from_icon_name("document-save-as-symbolic")
        icon.set_pixel_size(32)
        self.add_prefix(icon)

        # Pulsante Applica (suffix destro)
        apply_btn = Gtk.Button()
        apply_btn.set_label("Applica")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.add_css_class("suggested-action")
        # Disabilita il pulsante se il preset è corrotto
        apply_btn.set_sensitive(theme_set is not None)
        apply_btn.connect("clicked", lambda _: on_apply(self._preset_name))
        self.add_suffix(apply_btn)

        # Pulsante Elimina (suffix destro, distruttivo)
        delete_btn = Gtk.Button()
        delete_btn.set_icon_name("user-trash-symbolic")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.add_css_class("destructive-action")
        delete_btn.set_tooltip_text(f"Elimina il preset '{preset_name}'")
        delete_btn.connect("clicked", lambda _: on_delete(self._preset_name))
        self.add_suffix(delete_btn)


class PresetsPage:
    """Controller della pagina 'Profili e preset' per la GUI GTK4/Libadwaita.

    Gestisce tutti e quattro gli stati della pagina (loading, ready, empty, error)
    e coordina le operazioni asincrone di caricamento, salvataggio, applicazione
    ed eliminazione dei preset tramite le API pubbliche di ThemeManager.

    Callback pubblici per la coordinazione con la finestra principale:
        on_preset_applied: Callable[[], None]
            Invocato quando un preset viene applicato con successo, in modo che
            GnomeThemeWindow possa aggiornare StatusPage e ThemesPage.
    """

    PAGE_ID: str = "presets"
    TITLE: str = "Profili e preset"
    ICON_NAME: str = "document-save-as-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template presets_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager. Tutte le operazioni
                     sui preset vengono delegate alle sue API pubbliche.

        Raises:
            FileNotFoundError: Se il template presets_page.ui non è presente.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = self.TITLE
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        # --- Caricamento del template UI ---
        if not UI_FILE.is_file():
            raise FileNotFoundError(f"File template UI non trovato: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE))

        # Widget principale: GtkStack con i 4 stati
        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        # Widget dello stato READY
        self.presets_list_box: Gtk.ListBox = self.builder.get_object("presets_list_box")
        self.save_preset_button: Gtk.Button = self.builder.get_object("save_preset_button")
        self.reload_presets_button: Gtk.Button = self.builder.get_object("reload_presets_button")

        # Widget dello stato EMPTY
        self.empty_save_button: Gtk.Button = self.builder.get_object("empty_save_button")

        # Widget dello stato ERROR
        self.error_message_label: Gtk.Label = self.builder.get_object("error_message_label")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        # --- Stato interno ---
        # Flag che indica se una operazione (caricamento, applicazione, ecc.) è in corso
        self._is_loading: bool = False
        self._is_applying: bool = False
        # Contatore per ignorare risultati di richieste di refresh obsolete
        self._load_generation: int = 0
        # Flag per evitare la doppia apertura del dialogo di conferma
        self._confirm_dialog_open: bool = False
        # Flag che indica se la pagina è stata caricata almeno una volta (usato
        # dalla finestra principale per il refresh automatico al primo accesso)
        self._has_loaded: bool = False

        # --- Callback pubblico per notificare la finestra principale ---
        # La window lo sovrascriverà per aggiornare StatusPage e ThemesPage
        self.on_preset_applied: Callable[[], None] | None = None

        # --- Connessione dei segnali UI ---
        self.save_preset_button.connect("clicked", self._on_save_clicked)
        self.empty_save_button.connect("clicked", self._on_save_clicked)
        self.reload_presets_button.connect("clicked", self._on_reload_clicked)
        self.error_retry_button.connect("clicked", self._on_reload_clicked)

    # -------------------------------------------------------------------------
    # API pubblica della pagina
    # -------------------------------------------------------------------------

    def get_widget(self) -> Gtk.Stack:
        """Restituisce il widget radice per l'integrazione nel Gtk.Stack della finestra.

        Returns:
            Istanza di Gtk.Stack con i 4 stati della pagina.
        """
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indica se è attualmente in corso un caricamento dei preset."""
        return self._is_loading

    @property
    def has_loaded(self) -> bool:
        """Indica se la pagina è stata caricata almeno una volta con successo o errore."""
        return self._has_loaded

    def refresh(self, sync: bool = False) -> None:
        """Avvia il caricamento (o il ricaricamento) della lista dei preset.

        Flusso operativo:
            1. Verifica che non vi siano refresh già in corso;
            2. Incrementa _load_generation per invalidare callback obsoleti;
            3. Mostra la schermata 'loading';
            4. Esegue la lettura (asincrona in produzione, sincrona se sync=True nei test);
            5. Applica i risultati sul main thread GTK.

        In modalità sync=True (usata nei test), worker e callback vengono eseguiti
        direttamente senza GLib.idle_add, garantendo che la UI sia aggiornata
        prima del return.

        Args:
            sync: Se True, carica i preset in modo sincrono e deterministico.
        """
        if self._is_loading and not sync:
            logger.debug("Caricamento preset già in corso, richiesta ignorata.")
            return

        self._is_loading = True
        self._load_generation += 1
        current_generation = self._load_generation
        self._set_state("loading")

        # --- Worker: raccoglie i dati dal backend ---
        def worker_fetch() -> tuple[list[tuple[str, ThemeSet | None]] | None, Exception | None]:
            """Raccoglie la lista dei preset e i relativi ThemeSet.

            Ogni preset corrotto viene incluso come (nome, None) senza bloccare
            il caricamento degli altri.

            Returns:
                Tupla (rows, error): rows è la lista di preset se successo,
                error è l'eccezione se fallimento totale.
            """
            try:
                if self.manager is None:
                    return [], None

                names = self.manager.list_presets()
                rows: list[tuple[str, ThemeSet | None]] = []
                for name in names:
                    try:
                        ts = self.manager.load_preset(name)
                        rows.append((name, ts))
                    except (ValueError, FileNotFoundError, OSError) as err:
                        logger.warning("Preset '%s' non leggibile: %s", name, err)
                        rows.append((name, None))
                return rows, None
            except Exception as err:
                return None, err

        # --- Callback: aggiorna la UI con i risultati ---
        def on_fetch_completed(
            result: tuple[list[tuple[str, ThemeSet | None]] | None, Exception | None],
        ) -> bool:
            """Eseguito nel main context GTK per aggiornare i widget.

            Returns:
                GLib.SOURCE_REMOVE per rimuovere il callback da idle_add.
            """
            # Se è iniziato un nuovo refresh nel frattempo, scarta questo risultato
            if current_generation != self._load_generation:
                logger.debug(
                    "Callback preset tardivo scartato: gen %d != %d",
                    current_generation,
                    self._load_generation,
                )
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            self._has_loaded = True
            rows, error = result

            if error is not None:
                logger.error("Errore durante il caricamento della lista preset: %s", error)
                self.error_message_label.set_text(str(error))
                self._set_state("error")
                return GLib.SOURCE_REMOVE

            # Svuota la lista esistente
            while True:
                child = self.presets_list_box.get_first_child()
                if child is None:
                    break
                self.presets_list_box.remove(child)

            if not rows:
                self._set_state("empty")
                return GLib.SOURCE_REMOVE

            # Popola la lista con le righe dei preset
            for name, theme_set in rows:
                row = _PresetRow(
                    preset_name=name,
                    theme_set=theme_set,
                    on_apply=self._on_apply_preset_requested,
                    on_delete=self._on_delete_preset_requested,
                )
                self.presets_list_box.append(row)

            self._set_state("ready")
            self._set_controls_sensitive(True)
            return GLib.SOURCE_REMOVE

        # --- Dispatch: sincrono o asincrono ---
        if sync:
            # Percorso sincrono deterministico (test): esecuzione immediata
            res = worker_fetch()
            on_fetch_completed(res)
        else:
            # Percorso asincrono (produzione): background thread + main context
            def thread_target() -> None:
                res = worker_fetch()
                GLib.idle_add(on_fetch_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    # -------------------------------------------------------------------------
    # Callbacks dei pulsanti della pagina
    # -------------------------------------------------------------------------

    def _on_reload_clicked(self, _button: Gtk.Button) -> None:
        """Ricarica la lista dei preset dal disco (ricarica locale, senza refresh globale)."""
        self.refresh()

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        """Apre il dialogo di input per il nome del nuovo preset."""
        if self.manager is None:
            return
        self._open_save_dialog()

    # -------------------------------------------------------------------------
    # Salvataggio preset — dialogo di input
    # -------------------------------------------------------------------------

    def _open_save_dialog(self, prefill_name: str = "") -> None:
        """Apre il dialogo di input per inserire il nome del preset da salvare.

        Crea un Adw.AlertDialog con un Gtk.Entry per l'inserimento del nome.
        Valida il nome prima di procedere con il salvataggio.

        Args:
            prefill_name: Nome precompilato nel campo di testo (per eventuali retry).
        """
        # Costruzione del contenuto del dialogo: box con entry
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_size_request(400, -1)

        lbl = Gtk.Label(label="Nome del preset:")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_wrap(False)
        box.append(lbl)

        entry = Gtk.Entry()
        entry.set_placeholder_text("es. Tema scuro lavoro")
        entry.set_max_length(PRESET_NAME_MAX_LEN)
        entry.set_activates_default(True)
        if prefill_name:
            entry.set_text(prefill_name)
        box.append(entry)

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new("Salva configurazione attuale", "")
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(box)
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("save", "Salva")
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                resp = str(response_param)
                if resp == "save":
                    name = entry.get_text().strip()
                    self._validate_and_save(name)

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                "Salva configurazione attuale",
                "",
            )
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(box)
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("save", "Salva")
            dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                if response_id == "save":
                    name = entry.get_text().strip()
                    self._validate_and_save(name)

            dialog.connect("response", on_md_response)
            dialog.present()

    def _validate_and_save(self, name: str) -> None:
        """Valida il nome inserito dall'utente e avvia il salvataggio.

        Esegue controlli di pre-validazione lato GUI (nome vuoto, nome già esistente)
        prima di delegare al backend. La sanitizzazione completa è delegata al core.

        Args:
            name: Nome del preset inserito dall'utente.
        """
        # Controllo nome vuoto o composto solo da spazi
        if not name or not name.strip():
            self._show_save_error_and_retry("Il nome del preset non può essere vuoto.", name)
            return

        # Normalizzazione: rimuove spazi superflui alle estremità (coerente con il core)
        name = name.strip()

        # Controllo duplicato: verifica tramite lista pubblica
        try:
            existing = self.manager.list_presets() if self.manager else []
        except Exception as err:
            logger.error("Errore durante il controllo duplicati: %s", err)
            existing = []

        if name in existing:
            # Chiediamo conferma per la sovrascrittura
            self._open_overwrite_confirm_dialog(name)
            return

        self._do_save_preset(name, overwrite=False)

    def _show_save_error_and_retry(self, message: str, prefill: str = "") -> None:
        """Mostra un toast di errore e riapre il dialogo di input.

        Args:
            message: Messaggio di errore da mostrare.
            prefill: Nome precompilato nel campo per il retry.
        """
        self._show_toast(message)
        self._open_save_dialog(prefill_name=prefill)

    def _open_overwrite_confirm_dialog(self, name: str) -> None:
        """Apre un dialogo di conferma per la sovrascrittura di un preset esistente.

        Args:
            name: Nome del preset già esistente.
        """
        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                f'Sovrascrivere il preset "{name}"?',
                "Un preset con questo nome esiste già. Sovrascrivendolo i dati precedenti andranno persi.",
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("overwrite", "Sovrascrivi")
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                if str(response_param) == "overwrite":
                    self._do_save_preset(name, overwrite=True)

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                f'Sovrascrivere il preset "{name}"?',
                "Un preset con questo nome esiste già.",
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("overwrite", "Sovrascrivi")
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                if response_id == "overwrite":
                    self._do_save_preset(name, overwrite=True)

            dialog.connect("response", on_md_response)
            dialog.present()

    def _do_save_preset(self, name: str, overwrite: bool = False) -> None:
        """Esegue il salvataggio del preset tramite API pubblica, in modo sincrono.

        Il salvataggio è veloce (scrittura JSON locale) quindi non richiede
        un thread separato. Aggiorna la lista dopo il successo.

        Args:
            name: Nome del preset da salvare.
            overwrite: Se True, sovrascrive un preset esistente con lo stesso nome.
        """
        if self.manager is None:
            return
        try:
            self.manager.save_current_as_preset(name, overwrite=overwrite)
            self._show_toast(f'Preset "{name}" salvato.')
            self.refresh()
        except (ValueError, FileExistsError, OSError, GnomeThemeManagerError) as err:
            logger.error("Errore salvataggio preset '%s': %s", name, err)
            self._show_toast(f"Errore: {err}")

    # -------------------------------------------------------------------------
    # Applicazione preset — dialogo di conferma e operazione asincrona
    # -------------------------------------------------------------------------

    def _on_apply_preset_requested(self, name: str) -> None:
        """Apre il dialogo di conferma per l'applicazione di un preset.

        Args:
            name: Nome del preset da applicare.
        """
        if self._confirm_dialog_open or self._is_applying:
            logger.debug("Operazione già in corso, richiesta applicazione ignorata.")
            return

        # Recupera il ThemeSet per il riepilogo nel dialogo
        try:
            ts = self.manager.load_preset(name) if self.manager else None
        except Exception:
            ts = None

        summary = _build_preset_summary(ts) if ts else "Dettagli non disponibili."

        self._confirm_dialog_open = True

        # Costruzione del contenuto descrittivo del dialogo
        extra_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        extra_box.set_size_request(460, -1)
        extra_box.set_margin_top(6)
        extra_box.set_margin_bottom(12)
        extra_box.set_margin_start(16)
        extra_box.set_margin_end(16)

        for line in summary.splitlines():
            lbl = Gtk.Label(label=line)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_wrap(False)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            extra_box.append(lbl)

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(f'Applicare il preset "{name}"?', "")
            if hasattr(dialog, "set_extra_child"):
                dialog.set_extra_child(extra_box)
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("apply", "Applica")
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                try:
                    if str(response_param) == "apply":
                        self._run_apply_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                f'Applicare il preset "{name}"?',
                summary,
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("apply", "Applica")
            dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("apply")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                try:
                    if response_id == "apply":
                        self._run_apply_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_md_response)
            dialog.present()
        else:
            # Nessun dialogo disponibile: reset flag
            self._confirm_dialog_open = False

    def _run_apply_preset(self, name: str, sync: bool = False) -> None:
        """Esegue l'applicazione del preset.

        Disabilita i controlli durante l'applicazione, impedisce operazioni
        concorrenti e riabilita i controlli al termine (successo o errore).

        In modalità sync=True (usata nei test), l'intera operazione viene
        completata prima del ritorno del metodo, senza callback pendenti.

        Args:
            name: Nome del preset da applicare.
            sync: Se True, esegue l'applicazione in modo sincrono e deterministico.
        """
        if self._is_applying:
            logger.debug("Applicazione già in corso, richiesta ignorata.")
            return

        self._is_applying = True
        self._set_controls_sensitive(False)

        if sync:
            self._do_apply_preset(name, sync=True)
        else:
            threading.Thread(
                target=self._do_apply_preset,
                args=(name,),
                daemon=True,
            ).start()

    def _do_apply_preset(self, name: str, sync: bool = False) -> None:
        """Chiama manager.apply_preset() e gestisce il risultato.

        In modalità sync=True il risultato viene applicato direttamente sul
        thread corrente; altrimenti viene schedulato sul main context GTK.

        Args:
            name: Nome del preset da applicare.
            sync: Se True, esegue la gestione del risultato in modo sincrono.
        """
        try:
            if self.manager is None:
                raise GnomeThemeManagerError("Manager non disponibile.")
            result = self.manager.apply_preset(name)
            if sync:
                self._on_apply_done(name, result, None)
            else:
                GLib.idle_add(self._on_apply_done, name, result, None)
        except Exception as err:
            logger.error("Errore applicazione preset '%s': %s", name, err)
            if sync:
                self._on_apply_done(name, None, err)
            else:
                GLib.idle_add(self._on_apply_done, name, None, err)

    def _on_apply_done(self, name: str, result: Any, error: Exception | None) -> bool:
        """Aggiorna la UI dopo l'applicazione del preset. Eseguito sul main context.

        Args:
            name: Nome del preset applicato.
            result: ApplyResult in caso di successo, None in caso di errore.
            error: Eccezione sollevata in caso di errore, None in caso di successo.

        Returns:
            False per rimuovere il callback da GLib.idle_add.
        """
        self._is_applying = False
        self._set_controls_sensitive(True)

        if error is not None:
            self._show_toast(f'Errore nell\'applicazione del preset "{name}": {error}')
            return False

        # Costruisce il feedback finale
        if result is not None:
            warnings = getattr(result, "warnings", [])
            if warnings:
                self._show_toast(
                    f'Preset "{name}" applicato con avvisi: {"; ".join(str(w) for w in warnings)}'
                )
            else:
                self._show_toast(f'Preset "{name}" applicato con successo.')
        else:
            self._show_toast(f'Preset "{name}" applicato.')

        # Notifica la finestra principale per aggiornare StatusPage e ThemesPage
        if self.on_preset_applied is not None:
            try:
                self.on_preset_applied()
            except Exception as cb_err:
                logger.warning("Errore nel callback on_preset_applied: %s", cb_err)

        return False

    # -------------------------------------------------------------------------
    # Eliminazione preset — dialogo di conferma
    # -------------------------------------------------------------------------

    def _on_delete_preset_requested(self, name: str) -> None:
        """Apre il dialogo di conferma per l'eliminazione di un preset.

        Args:
            name: Nome del preset da eliminare.
        """
        if self._confirm_dialog_open:
            return

        self._confirm_dialog_open = True

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(
                f'Eliminare il preset "{name}"?',
                "L'operazione rimuoverà il file del preset. I temi installati non saranno modificati.",
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("delete", "Elimina")
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_response(d: Any, response_param: Any) -> None:
                try:
                    if str(response_param) == "delete":
                        self._do_delete_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_response)
            parent = self.widget.get_root()
            dialog.present(parent if isinstance(parent, Gtk.Widget) else None)

        elif hasattr(Adw, "MessageDialog"):
            parent = self.widget.get_root()
            dialog = Adw.MessageDialog.new(
                parent if isinstance(parent, Gtk.Window) else None,
                f'Eliminare il preset "{name}"?',
                "L'operazione rimuoverà il file del preset. I temi installati non saranno modificati.",
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("delete", "Elimina")
            dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")

            def on_md_response(d: Any, response_id: str) -> None:
                try:
                    if response_id == "delete":
                        self._do_delete_preset(name)
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_md_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False

    def _do_delete_preset(self, name: str) -> None:
        """Esegue l'eliminazione del preset tramite API pubblica.

        Il delete è un'operazione su file locale veloce; eseguita sul main thread.
        Non cancella temi installati e non modifica il tema attivo.

        Args:
            name: Nome del preset da eliminare.
        """
        if self.manager is None:
            return
        try:
            self.manager.delete_preset(name)
            self._show_toast(f'Preset "{name}" eliminato.')
            self.refresh()
        except (FileNotFoundError, ValueError, OSError, GnomeThemeManagerError) as err:
            logger.error("Errore eliminazione preset '%s': %s", name, err)
            self._show_toast(f"Errore nell'eliminazione: {err}")

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        """Imposta lo stato visibile della pagina (loading, ready, empty, error).

        Args:
            state: Nome dello stato Gtk.Stack da mostrare.
        """
        self.widget.set_visible_child_name(state)

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        """Abilita o disabilita i controlli principali della pagina.

        Args:
            sensitive: True per abilitare i pulsanti, False per disabilitarli.
        """
        self.save_preset_button.set_sensitive(sensitive)
        self.reload_presets_button.set_sensitive(sensitive)
        self.empty_save_button.set_sensitive(sensitive)
        self.error_retry_button.set_sensitive(sensitive)

    def _clear_toast(self) -> None:
        """Richiede la chiusura del feedback persistente alla finestra principale."""
        root = self.widget.get_root()
        if root is not None and hasattr(root, "clear_feedback"):
            root.clear_feedback()

    def _show_toast(self, message: str, timeout: int = 0) -> None:
        """Mostra una notifica di feedback persistente tramite la finestra principale.

        Args:
            message: Testo del messaggio da mostrare.
            timeout: Durata della notifica in secondi (0 = persistente).
        """
        root = self.widget.get_root()
        if root is not None and hasattr(root, "add_toast"):
            root.add_toast(message, timeout=timeout)
        else:
            logger.info("[Feedback PresetsPage]: %s", message)
