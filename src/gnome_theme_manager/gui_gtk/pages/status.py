# SPDX-License-Identifier: GPL-3.0-or-later

"""Controller per la pagina 'Stato attuale' e diagnostica di sistema (Fase 5.3).

Questo modulo implementa la logica di presentazione dello stato dei temi e della
diagnostica del sistema GNOME consumando esclusivamente le API pubbliche del Facade
`ThemeManager`. Gestisce gli stati UI tramite Gtk.Stack (loading, ready, empty, error),
la formattazione dei dati, il banner dei warning e il refresh asincrono thread-safe.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import gi

from gnome_theme_manager import _

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk

from ...core.errors import GnomeThemeManagerError, GSettingsUnavailableError
from ...core.gsettings import Gtk4OverrideStatus
from ...core.models import SystemStatus, ThemeSet, ThemeType

if TYPE_CHECKING:
    from ...core.manager import ThemeManager

logger = logging.getLogger("gnome_theme_manager.gui_gtk.pages.status")

# Percorso del file template UI dedicato
UI_FILE = Path(__file__).parent.parent / "ui" / "status_page.ui"


# =============================================================================
# Modello Dati di Presentazione UI (Immutabile)
# =============================================================================


@dataclass(frozen=True)
class StatusSnapshot:
    """Istantanea immutabile per la presentazione dei dati di diagnostica e temi."""

    themes: ThemeSet
    system_status: SystemStatus
    gtk_path: str | None = None
    icon_path: str | None = None
    cursor_path: str | None = None
    shell_path: str | None = None
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# Funzioni di Formattazione e Presentazione (Localizzabili)
# =============================================================================


def format_optional_value(value: str | None, default: str = _("Non impostato")) -> str:
    """Formatta un valore testuale opzionale.

    Args:
        value: Valore stringa opzionale.
        default: Valore di fallback se None o stringa vuota.

    Returns:
        Stringa formattata leggibile per l'utente.
    """
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def format_boolean(
    value: bool | None,
    true_label: str = _("Sì"),
    false_label: str = _("No"),
    default: str = _("Non disponibile"),
) -> str:
    """Formatta un valore booleano in una stringa utente descrittiva.

    Args:
        value: Valore booleano opzionale.
        true_label: Etichetta in caso di True.
        false_label: Etichetta in caso di False.
        default: Etichetta in caso di None.

    Returns:
        Stringa utente.
    """
    if value is None:
        return default
    return true_label if value else false_label


def format_path(path: Path | str | None, default: str = _("Non disponibile")) -> str:
    """Formatta un percorso filesystem per la visualizzazione nella UI.

    Args:
        path: Percorso Path o stringa.
        default: Valore di fallback.

    Returns:
        Rappresentazione stringa del percorso.
    """
    if path is None:
        return default
    return str(path)


def format_color_scheme(scheme: str | None) -> str:
    """Formatta lo schema colori GNOME (chiaro/scuro).

    Args:
        scheme: Valore GSettings dello schema colori.

    Returns:
        Descrizione chiara e comprensibile per l'utente.
    """
    if not scheme or scheme == "default":
        return _("Predefinito (Chiaro)")
    elif scheme == "prefer-dark":
        return _("Scuro (Preferisci scuro)")
    elif scheme == "prefer-light":
        return _("Chiaro (Preferisci chiaro)")
    return str(scheme)


def format_shell_theme(shell_theme: str | None, is_supported: bool) -> str:
    """Formatta lo stato del tema GNOME Shell tenendo conto dell'estensione User Themes.

    Args:
        shell_theme: Nome del tema shell attivo.
        is_supported: Se l'estensione 'User Themes' è supportata nel sistema.

    Returns:
        Stringa descrittiva dello stato del tema shell.
    """
    if not is_supported:
        return _("Non gestito (estensione 'User Themes' non attiva)")
    if not shell_theme:
        return _("Default di sistema")
    return shell_theme


def format_sandbox_status(
    available: bool,
    active_or_installed: bool,
    active_label: str,
    inactive_label: str,
) -> str:
    """Formatta lo stato di un runtime sandbox (Snap o Flatpak).

    Args:
        available: Se il binario è presente nel sistema.
        active_or_installed: Se l'estensione/override è presente.
        active_label: Etichetta descrittiva se attivo.
        inactive_label: Etichetta descrittiva se non attivo.

    Returns:
        Descrizione dello stato sandbox.
    """
    if not available:
        return _("Non disponibile (non installato)")
    if active_or_installed:
        return f"{_('Disponibile')} ({active_label})"
    return f"{_('Disponibile')} ({inactive_label})"


# =============================================================================
# Controller Pagina Stato
# =============================================================================


class StatusPage:
    """Controller per la pagina di stato attuale e diagnostica di sistema."""

    PAGE_ID: str = "status"
    TITLE: str = _("Stato attuale")
    ICON_NAME: str = "preferences-desktop-theme-symbolic"

    def __init__(self, manager: "ThemeManager | None" = None) -> None:
        """Inizializza il controller caricando il template dichiarativo status_page.ui.

        Args:
            manager: Istanza coordinatrice ThemeManager.

        Raises:
            FileNotFoundError: Se il template status_page.ui non viene trovato.
        """
        self.page_id: str = self.PAGE_ID
        self.title: str = self.TITLE
        self.icon_name: str = self.ICON_NAME
        self.manager = manager

        if not UI_FILE.is_file():
            raise FileNotFoundError(f"Template UI non trovato: {UI_FILE}")

        # Caricamento interfaccia tramite Gtk.Builder
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("gnomethememanager")
        self.builder.add_from_file(str(UI_FILE))

        # Recupero widget dello stack degli stati
        self.widget: Gtk.Stack = self.builder.get_object("page_root")
        self.banner_warning: Adw.Banner = self.builder.get_object("banner_warning")

        # Righe di preferenza per i dati reali
        self.row_gtk_theme: Adw.ActionRow = self.builder.get_object("row_gtk_theme")
        self.row_icon_theme: Adw.ActionRow = self.builder.get_object("row_icon_theme")
        self.row_cursor_theme: Adw.ActionRow = self.builder.get_object("row_cursor_theme")
        self.row_shell_theme: Adw.ActionRow = self.builder.get_object("row_shell_theme")
        self.row_color_scheme: Adw.ActionRow = self.builder.get_object("row_color_scheme")
        self.row_gtk4_override: Adw.ActionRow = self.builder.get_object("row_gtk4_override")
        self.row_gsettings_status: Adw.ActionRow = self.builder.get_object("row_gsettings_status")
        self.row_user_themes_path: Adw.ActionRow = self.builder.get_object("row_user_themes_path")
        self.row_user_icons_path: Adw.ActionRow = self.builder.get_object("row_user_icons_path")
        self.row_flatpak_status: Adw.ActionRow = self.builder.get_object("row_flatpak_status")
        self.row_snap_status: Adw.ActionRow = self.builder.get_object("row_snap_status")

        # Pagine e pulsanti di retry
        self.error_page: Adw.StatusPage = self.builder.get_object("error_page")
        self.error_retry_button: Gtk.Button = self.builder.get_object("error_retry_button")
        self.empty_retry_button: Gtk.Button = self.builder.get_object("empty_retry_button")

        # Collegamento pulsanti di riprova
        self.error_retry_button.connect("clicked", lambda _: self.refresh())
        self.empty_retry_button.connect("clicked", lambda _: self.refresh())

        # Stato interno di caricamento e sequenza refresh per evitare race condition
        self._is_loading: bool = False
        self._generation_id: int = 0
        self.on_loading_changed: Callable[[bool], None] | None = None

        # Ultimo snapshot acquisito
        self._last_snapshot: StatusSnapshot | None = None

    def get_widget(self) -> Gtk.Widget:
        """Restituisce il widget radice per l'inserimento nel Gtk.Stack della finestra."""
        return self.widget

    @property
    def is_loading(self) -> bool:
        """Indica se è attualmente in corso un'operazione di refresh."""
        return self._is_loading

    @property
    def current_snapshot(self) -> StatusSnapshot | None:
        """Restituisce l'ultimo snapshot di dati caricato con successo."""
        return self._last_snapshot

    def refresh(self, sync: bool = False) -> None:
        """Avvia l'aggiornamento dei dati di diagnostica e temi dal backend.

        Flusso operativo:
            1. Verifica che non vi siano refresh già in corso;
            2. Incrementa generation_id per invalidare callback obsoleti;
            3. Mostra la schermata 'loading' e notifica il cambio stato;
            4. Esegue la lettura (asincrona in produzione, sincrona se sync=True nei test);
            5. Applica i risultati sul main thread GTK tramite GLib.idle_add.

        Args:
            sync: Se True, esegue l'operazione in modo sincrono e deterministico (usato nei test).
        """
        if self._is_loading and not sync:
            logger.debug("Refresh già in corso: richiesta ignorata.")
            return

        self._is_loading = True
        self._generation_id += 1
        current_generation = self._generation_id

        # Notifica cambio stato e passa alla vista loading
        if self.on_loading_changed:
            self.on_loading_changed(True)
        self.widget.set_visible_child_name("loading")

        def worker_fetch() -> tuple[StatusSnapshot | None, Exception | None]:
            """Raccoglie i dati dal Facade ThemeManager in background."""
            try:
                if self.manager is None:
                    raise GnomeThemeManagerError(
                        _("ThemeManager non disponibile o non inizializzato.")
                    )

                # 1. Lettura temi correnti e stato di sistema tramite API pubbliche del Facade
                themes = self.manager.get_current_themes()
                system_status = self.manager.get_system_status()

                # 2. Risoluzione dei percorsi fisici dei temi attivi (se disponibili)
                gtk_path: str | None = None
                if themes.gtk_theme:
                    found = self.manager.find_theme(themes.gtk_theme, ThemeType.GTK)
                    if found:
                        gtk_path = str(found.path)

                icon_path: str | None = None
                if themes.icon_theme:
                    found = self.manager.find_theme(themes.icon_theme, ThemeType.ICON)
                    if found:
                        icon_path = str(found.path)

                cursor_path: str | None = None
                if themes.cursor_theme:
                    found = self.manager.find_theme(themes.cursor_theme, ThemeType.CURSOR)
                    if found:
                        cursor_path = str(found.path)

                shell_path: str | None = None
                if themes.shell_theme:
                    found = self.manager.find_theme(themes.shell_theme, ThemeType.SHELL)
                    if found:
                        shell_path = str(found.path)

                # 3. Rilevamento di avvertenze o limitazioni note
                warnings: list[str] = []
                if not system_status.gsettings_available:
                    warnings.append(_("GSettings non disponibile in questo ambiente."))
                if not system_status.shell_theme_supported:
                    warnings.append(_("Estensione GNOME Shell 'User Themes' non attiva."))
                if system_status.sandbox_status:
                    sb = system_status.sandbox_status
                    if sb.snap_available and not sb.snap_gtk_common_themes_installed:
                        warnings.append(_("Snap: 'gtk-common-themes' non installato."))
                    if sb.flatpak_available and not sb.flatpak_filesystem_override_active:
                        warnings.append(_("Flatpak: override filesystem temi utente non attivo."))

                snapshot = StatusSnapshot(
                    themes=themes,
                    system_status=system_status,
                    gtk_path=gtk_path,
                    icon_path=icon_path,
                    cursor_path=cursor_path,
                    shell_path=shell_path,
                    warnings=warnings,
                )
                return snapshot, None
            except Exception as err:
                return None, err

        def on_fetch_completed(result: tuple[StatusSnapshot | None, Exception | None]) -> bool:
            """Eseguito nel main context GTK per aggiornare i widget."""
            # Se è iniziato un nuovo refresh nel frattempo, scarta questo risultato obsoleto
            if current_generation != self._generation_id:
                logger.debug(
                    "Callback tardivo scartato: gen %d != %d",
                    current_generation,
                    self._generation_id,
                )
                return GLib.SOURCE_REMOVE

            self._is_loading = False
            if self.on_loading_changed:
                self.on_loading_changed(False)

            snapshot, error = result

            if error is not None:
                logger.error("Errore durante il recupero dello stato: %s", error)
                self._handle_error(error)
            elif snapshot is not None:
                self._apply_snapshot(snapshot)
            else:
                self.widget.set_visible_child_name("empty")

            return GLib.SOURCE_REMOVE

        if sync:
            # Esecuzione sincrona (per test unitari immediati)
            res = worker_fetch()
            on_fetch_completed(res)
        else:
            # Esecuzione in background worker
            def thread_target() -> None:
                res = worker_fetch()
                GLib.idle_add(on_fetch_completed, res)

            thread = threading.Thread(target=thread_target, daemon=True)
            thread.start()

    def _apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        """Applica i dati dello snapshot ai widget della vista 'ready'.

        Args:
            snapshot: Dati immutabili pronti per la visualizzazione.
        """
        self._last_snapshot = snapshot

        # Se non c'è alcuna informazione configurata, mostra la schermata vuota
        if snapshot.themes.is_empty() and not snapshot.system_status.gsettings_available:
            self.widget.set_visible_child_name("empty")
            return

        t = snapshot.themes
        s = snapshot.system_status

        # 1. Temi attivi
        self.row_gtk_theme.set_subtitle(
            f"{format_optional_value(t.gtk_theme)} ({snapshot.gtk_path})"
            if snapshot.gtk_path
            else format_optional_value(t.gtk_theme)
        )
        self.row_icon_theme.set_subtitle(
            f"{format_optional_value(t.icon_theme)} ({snapshot.icon_path})"
            if snapshot.icon_path
            else format_optional_value(t.icon_theme)
        )
        self.row_cursor_theme.set_subtitle(
            f"{format_optional_value(t.cursor_theme)} ({snapshot.cursor_path})"
            if snapshot.cursor_path
            else format_optional_value(t.cursor_theme)
        )
        self.row_shell_theme.set_subtitle(
            format_shell_theme(t.shell_theme, s.shell_theme_supported)
        )
        self.row_color_scheme.set_subtitle(format_color_scheme(t.color_scheme))

        # 2. GTK4 Override (Letto tramite API pubblica del Facade ThemeManager)
        if s.gtk4_override_status == Gtk4OverrideStatus.ACTIVE:
            self.row_gtk4_override.set_subtitle(_("Attivo"))
        else:
            self.row_gtk4_override.set_subtitle(_("Non attivo"))

        # 3. Ambiente desktop e percorsi utente
        self.row_gsettings_status.set_subtitle(
            format_boolean(s.gsettings_available, _("Disponibile"), _("Non disponibile"))
        )
        self.row_user_themes_path.set_subtitle(format_path(s.user_themes_path))
        self.row_user_icons_path.set_subtitle(format_path(s.user_icons_path))

        # 4. Integrazione Sandbox
        if s.sandbox_status is not None:
            sb = s.sandbox_status
            self.row_flatpak_status.set_subtitle(
                format_sandbox_status(
                    available=sb.flatpak_available,
                    active_or_installed=sb.flatpak_filesystem_override_active,
                    active_label=_("Override filesystem attivo"),
                    inactive_label=_("Override non attivo"),
                )
            )
            self.row_snap_status.set_subtitle(
                format_sandbox_status(
                    available=sb.snap_available,
                    active_or_installed=sb.snap_gtk_common_themes_installed,
                    active_label=_("gtk-common-themes installato"),
                    inactive_label=_("gtk-common-themes non installato"),
                )
            )
        else:
            self.row_flatpak_status.set_subtitle(_("Non disponibile"))
            self.row_snap_status.set_subtitle(_("Non disponibile"))

        # 5. Gestione Banner Avvertenze
        if snapshot.warnings:
            self.banner_warning.set_title(_("Avvisi: ") + " • ".join(snapshot.warnings))
            self.banner_warning.set_revealed(True)
        else:
            self.banner_warning.set_revealed(False)

        # Mostra la pagina ready
        self.widget.set_visible_child_name("ready")

    def _handle_error(self, error: Exception) -> None:
        """Gestisce gli errori di lettura impostando la schermata 'error'.

        Args:
            error: Eccezione verificatasi durante la lettura.
        """
        if isinstance(error, GSettingsUnavailableError):
            user_msg = _(
                "GSettings non è disponibile nel sistema. Assicurati di essere in un "
                "ambiente GNOME e che PyGObject (Gio) sia installato."
            )
        elif isinstance(error, GnomeThemeManagerError):
            user_msg = f"{_('Errore del gestore temi:')} {error}"
        else:
            user_msg = f"{_('Si è verificato un errore durante la lettura dello stato:')} {error}"

        self.error_page.set_description(user_msg)
        self.widget.set_visible_child_name("error")
