"""Controller per la pagina 'Strumenti sandbox' (Fase 5.8).

Questo modulo gestisce la diagnostica dettagliata dei runtime sandbox (Flatpak e Snap),
lo stato del pacchetto `gtk-common-themes`, la verifica di compatibilità dei temi attivi
e la propagazione manuale controllata dei permessi di filesystem e variabili d'ambiente.
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ...core.errors import GSettingsUnavailableError
from ...core.models import PropagationResult, SandboxStatus, ThemeSet
from ...core.sandbox_bridge import KNOWN_SNAP_COMMON_THEMES

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk")

# Percorso del file template UI dedicato
UI_FILE = Path(__file__).parent.parent / "ui" / "sandbox_page.ui"


class SandboxPage:
    """Controller della vista 'Strumenti sandbox' per la GUI GTK4/Libadwaita."""

    PAGE_ID: str = "sandbox"
    TITLE: str = "Strumenti sandbox"
    ICON_NAME: str = "security-high-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template sandbox_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager.

        Raises:
            FileNotFoundError: Se il template sandbox_page.ui non è presente nel filesystem.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = self.TITLE
        self.icon_name: str = self.ICON_NAME
        self.manager: ThemeManager | None = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"File template UI non trovato: {UI_FILE}")

        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(UI_FILE))

        # Widget principale GtkStack con gli stati loading, ready, error
        self.widget: Gtk.Stack = self.builder.get_object("page_root")

        # Widget dello stato LOADING
        self.loading_spinner: Gtk.Spinner = self.builder.get_object("loading_spinner")
        self.loading_label: Gtk.Label = self.builder.get_object("loading_label")

        # Widget dello stato READY - Gruppo Flatpak
        self.flatpak_status_row: Adw.ActionRow = self.builder.get_object("flatpak_status_row")
        self.flatpak_status_icon: Gtk.Image | None = self.builder.get_object("flatpak_status_icon")
        self.flatpak_override_row: Adw.ActionRow = self.builder.get_object("flatpak_override_row")
        self.flatpak_notes_row: Adw.ActionRow = self.builder.get_object("flatpak_notes_row")

        # Widget dello stato READY - Gruppo Snap
        self.snap_status_row: Adw.ActionRow = self.builder.get_object("snap_status_row")
        self.snap_status_icon: Gtk.Image | None = self.builder.get_object("snap_status_icon")
        self.snap_gtk_common_row: Adw.ActionRow = self.builder.get_object("snap_gtk_common_row")
        self.snap_theme_compat_row: Adw.ActionRow = self.builder.get_object("snap_theme_compat_row")
        self.snap_notes_row: Adw.ActionRow = self.builder.get_object("snap_notes_row")

        # Pulsanti di azione
        self.refresh_button: Gtk.Button = self.builder.get_object("refresh_button")
        self.propagate_button: Gtk.Button = self.builder.get_object("propagate_button")

        # Widget dello stato ERROR
        self.error_status_page: Adw.StatusPage = self.builder.get_object("error_status_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")

        # Configurazione etichette native e icone per i pulsanti
        self._button_configs: dict[str, tuple[str, str]] = {
            "refresh_button": ("Ricarica stato", "view-refresh-symbolic"),
            "propagate_button": ("Propaga tema alle applicazioni sandbox", "emblem-ok-symbolic"),
            "error_retry_button": ("Riprova", "view-refresh-symbolic"),
        }
        for btn_attr, (lbl, icon) in self._button_configs.items():
            btn = getattr(self, btn_attr, None)
            if btn is not None:
                btn.set_label(lbl)
                btn._icon_name = icon
                btn.get_icon_name = lambda _b=btn, _ic=icon: _ic

        # Stato interno
        self._is_loading: bool = False
        self._is_propagating: bool = False
        self._refresh_generation: int = 0
        self._propagate_generation: int = 0
        self._confirm_dialog_open: bool = False
        self._current_sandbox_status: SandboxStatus | None = None
        self._current_themes: ThemeSet | None = None

        # Callback di notifica verso la finestra principale
        self.on_sandbox_propagated: Callable[[], None] | None = None

        # Connessione segnali
        self.refresh_button.connect("clicked", lambda _: self.refresh())
        self.propagate_button.connect("clicked", self._on_propagate_clicked)
        self.error_retry_button.connect("clicked", lambda _: self.refresh())

    def get_widget(self) -> Gtk.Stack:
        """Restituisce il widget Gtk.Stack principale della pagina.

        Returns:
            Widget Gtk.Stack configurato con le viste dichiarative.
        """
        return self.widget

    # -------------------------------------------------------------------------
    # Gestione Stati e Sensibilità Controlli
    # -------------------------------------------------------------------------

    def _set_state(self, state_name: str) -> None:
        """Imposta lo stato visibile nello stack.

        Args:
            state_name: Nome dello stato ('loading', 'ready', 'error').
        """
        self.widget.set_visible_child_name(state_name)

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        """Abilita o disabilita i controlli di azione della pagina.

        Args:
            sensitive: True per abilitare, False per disabilitare.
        """
        self.refresh_button.set_sensitive(sensitive)
        self.error_retry_button.set_sensitive(sensitive)

        if not sensitive:
            self.propagate_button.set_sensitive(False)
        else:
            # Abilitato solo se almeno un runtime sandbox è presente
            sb = self._current_sandbox_status
            can_propagate = bool(sb and (sb.flatpak_available or sb.snap_available))
            self.propagate_button.set_sensitive(can_propagate)

    # -------------------------------------------------------------------------
    # Operazione di Refresh Diagnostico
    # -------------------------------------------------------------------------

    def refresh(self, sync: bool = False) -> None:
        """Aggiorna lo stato diagnostico dei runtime sandbox e la compatibilità del tema.

        Args:
            sync: Se True, esegue l'operazione in modo sincrono sul thread corrente (test).
        """
        if self._is_loading and not sync:
            logger.debug("Refresh sandbox già in corso, richiesta ignorata.")
            return

        self._is_loading = True
        self._refresh_generation += 1
        current_gen = self._refresh_generation

        self._set_state("loading")
        self._set_controls_sensitive(False)

        def worker_fetch() -> tuple[SandboxStatus | None, ThemeSet | None, Exception | None]:
            try:
                if self.manager is None:
                    return SandboxStatus(), ThemeSet(), None

                sb_status = self.manager.get_sandbox_status()
                current_themes: ThemeSet | None = None
                try:
                    current_themes = self.manager.get_current_themes()
                except GSettingsUnavailableError:
                    current_themes = ThemeSet()

                return sb_status, current_themes, None
            except Exception as err:  # noqa: BLE001
                return None, None, err

        def on_fetch_completed(
            result: tuple[SandboxStatus | None, ThemeSet | None, Exception | None],
        ) -> bool:
            if current_gen != self._refresh_generation:
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            sb_status, themes, error = result

            if error is not None:
                logger.error("Errore durante il recupero diagnostica sandbox: %s", error)
                self.error_status_page.set_description(f"Errore diagnostica sandbox: {error}")
                self._set_state("error")
                self._set_controls_sensitive(True)
                return GLib.SOURCE_REMOVE

            self._current_sandbox_status = sb_status
            self._current_themes = themes

            self._update_ui_presentation(sb_status, themes)
            self._set_state("ready")
            self._set_controls_sensitive(True)
            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_fetch()
            on_fetch_completed(res)
        else:
            def thread_target() -> None:
                res = worker_fetch()
                GLib.idle_add(on_fetch_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    def _update_ui_presentation(
        self,
        sb: SandboxStatus | None,
        themes: ThemeSet | None,
    ) -> None:
        """Aggiorna le righe di riepilogo con i dati diagnostici ricevuti.

        Args:
            sb: Istanza SandboxStatus o None.
            themes: Istanza ThemeSet con i temi attualmente attivi.
        """
        if sb is None:
            sb = SandboxStatus()

        # 1. Flatpak Status
        if sb.flatpak_available:
            self.flatpak_status_row.set_subtitle("Disponibile nel sistema")
            if self.flatpak_status_icon is not None:
                self.flatpak_status_icon.set_from_icon_name("emblem-default-symbolic")
        else:
            self.flatpak_status_row.set_subtitle("Non installato")
            if self.flatpak_status_icon is not None:
                self.flatpak_status_icon.set_from_icon_name("dialog-information-symbolic")

        # 2. Flatpak Override
        if not sb.flatpak_available:
            self.flatpak_override_row.set_subtitle("Non applicabile (Flatpak assente)")
        elif sb.flatpak_filesystem_override_active:
            self.flatpak_override_row.set_subtitle("Attivo (~/.local/share/themes e icone)")
        else:
            self.flatpak_override_row.set_subtitle("Non configurato")

        # 3. Snap Status
        if sb.snap_available:
            self.snap_status_row.set_subtitle("Disponibile nel sistema")
            if self.snap_status_icon is not None:
                self.snap_status_icon.set_from_icon_name("emblem-default-symbolic")
        else:
            self.snap_status_row.set_subtitle("Non installato")
            if self.snap_status_icon is not None:
                self.snap_status_icon.set_from_icon_name("dialog-information-symbolic")

        # 4. Snap gtk-common-themes
        if not sb.snap_available:
            self.snap_gtk_common_row.set_subtitle("Non applicabile (Snap assente)")
        elif sb.snap_gtk_common_themes_installed:
            self.snap_gtk_common_row.set_subtitle("Installato")
        else:
            self.snap_gtk_common_row.set_subtitle("Non installato (consigliato per temi GTK)")

        # 5. Snap Theme Compatibility
        active_gtk = (themes.gtk_theme or "") if themes else ""
        if not sb.snap_available or not sb.snap_gtk_common_themes_installed:
            self.snap_theme_compat_row.set_subtitle("Non verificabile (Snap o gtk-common-themes assente)")
        elif not active_gtk:
            self.snap_theme_compat_row.set_subtitle("Nessun tema GTK attivo rilevato")
        else:
            norm_name = active_gtk.strip().lower()
            if norm_name in KNOWN_SNAP_COMMON_THEMES:
                self.snap_theme_compat_row.set_subtitle(
                    f"Tema '{active_gtk}' supportato nativamente da gtk-common-themes"
                )
            else:
                self.snap_theme_compat_row.set_subtitle(
                    f"Tema '{active_gtk}' personalizzato (richiede snap dedicato)"
                )

    # -------------------------------------------------------------------------
    # Flusso di Propagazione Tema
    # -------------------------------------------------------------------------

    def _on_propagate_clicked(self, _button: Gtk.Button | None = None) -> None:
        """Apre il dialogo di conferma modale prima di avviare la propagazione."""
        if self._confirm_dialog_open:
            return

        self._confirm_dialog_open = True
        root_window = self._get_root_window()
        heading = "Propagare il tema alle applicazioni sandbox?"
        body = (
            "Questa operazione configura gli override di filesystem per Flatpak e "
            "verifica la compatibilità dei temi attivi con Snap.\n\n"
            "Non tutte le applicazioni sandbox o tutti i temi possono essere aggiornati automaticamente."
        )

        if hasattr(Adw, "AlertDialog"):
            dialog = Adw.AlertDialog.new(heading, body)
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("propagate", "Propaga tema")
            dialog.set_response_appearance("propagate", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("propagate")
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

                    if resp == "propagate":
                        self._run_propagation()
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_dialog_response)
            dialog.present(root_window if isinstance(root_window, Gtk.Widget) else None)
        elif hasattr(Adw, "MessageDialog"):
            dialog = Adw.MessageDialog.new(
                root_window if isinstance(root_window, Gtk.Window) else None,
                heading,
                body,
            )
            dialog.add_response("cancel", "Annulla")
            dialog.add_response("propagate", "Propaga tema")
            dialog.set_response_appearance("propagate", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("propagate")
            dialog.set_close_response("cancel")

            def on_msg_response(_dlg: Any, response: str) -> None:
                try:
                    if response == "propagate":
                        self._run_propagation()
                finally:
                    self._confirm_dialog_open = False

            dialog.connect("response", on_msg_response)
            dialog.present()
        else:
            self._confirm_dialog_open = False
            self._run_propagation()

    def _run_propagation(self, sync: bool = False) -> None:
        """Esegue l'operazione di propagazione in modo asincrono (o sincrono nei test).

        Args:
            sync: Se True, esegue la propagazione in modo sincrono sul thread corrente.
        """
        if self._is_propagating and not sync:
            logger.debug("Propagazione già in corso, richiesta ignorata.")
            return

        self._is_propagating = True
        self._propagate_generation += 1
        current_gen = self._propagate_generation

        self._set_controls_sensitive(False)

        def worker_propagate() -> tuple[PropagationResult | None, Exception | None]:
            try:
                if self.manager is None:
                    return PropagationResult(), None
                res = self.manager.propagate_sandbox()
                return res, None
            except Exception as err:  # noqa: BLE001
                return None, err

        def on_propagation_completed(
            result: tuple[PropagationResult | None, Exception | None],
        ) -> bool:
            if current_gen != self._propagate_generation:
                return GLib.SOURCE_REMOVE

            self._is_propagating = False
            prop_res, error = result

            # Ricarica la diagnostica aggiornata dopo l'operazione
            self.refresh(sync=True)

            if error is not None:
                logger.error("Errore durante la propagazione sandbox: %s", error)
                self._show_toast(f"Errore durante la propagazione: {error}")
            elif prop_res is not None:
                # Valutazione esito
                if prop_res.warnings:
                    warn_summary = "; ".join(prop_res.warnings[:2])
                    self._show_toast(f"Propagazione completata con avvisi: {warn_summary}")
                elif prop_res.flatpak_success or prop_res.snap_success:
                    self._show_toast("Tema propagato con successo alle applicazioni sandbox.")
                else:
                    self._show_toast("Nessuna modifica applicata agli ambienti sandbox.")

                if self.on_sandbox_propagated:
                    try:
                        self.on_sandbox_propagated()
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Errore nel callback on_sandbox_propagated: %s", e)

            return GLib.SOURCE_REMOVE

        if sync:
            res = worker_propagate()
            on_propagation_completed(res)
        else:
            def thread_target() -> None:
                res = worker_propagate()
                GLib.idle_add(on_propagation_completed, res)

            threading.Thread(target=thread_target, daemon=True).start()

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def _get_root_window(self) -> Gtk.Window | None:
        """Recupera la finestra Gtk.Window genitrice per dialoghi e toast."""
        root = self.widget.get_root()
        if isinstance(root, Gtk.Window):
            return root
        return None

    def _show_toast(self, message: str, timeout: int = 4) -> None:
        """Mostra una notifica toast tramite l'Adw.ToastOverlay della finestra principale.

        Args:
            message: Testo della notifica da mostrare.
            timeout: Durata di visualizzazione in secondi.
        """
        root = self.widget.get_root()
        overlay = getattr(root, "toast_overlay", None)
        if overlay and hasattr(overlay, "add_toast"):
            toast = Adw.Toast.new(message)
            toast.set_timeout(timeout)
            overlay.add_toast(toast)
        else:
            logger.info("Toast [SandboxPage]: %s", message)
