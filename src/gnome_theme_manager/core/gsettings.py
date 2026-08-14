# SPDX-License-Identifier: GPL-3.0-or-later

"""Wrapper sicuro per l'interazione con GSettings tramite PyGObject (Gio).

In ambiente GNOME, GSettings è il sistema centralizzato di memorizzazione
delle preferenze e configurazioni desktop (con backend principale in dconf).
Questo modulo astrae e incapsula tutte le chiamate di lettura e scrittura verso:
- `org.gnome.desktop.interface` (Temi GTK, Icone, Cursori, Color-Scheme)
- `org.gnome.shell.extensions.user-theme` (Tema della GNOME Shell)
"""

from enum import Enum
from pathlib import Path

from .constants import (
    GSETTINGS_KEY_COLOR_SCHEME,
    GSETTINGS_KEY_CURSOR_THEME,
    GSETTINGS_KEY_GTK_THEME,
    GSETTINGS_KEY_ICON_THEME,
    GSETTINGS_KEY_SHELL_THEME,
    GSETTINGS_SCHEMA_INTERFACE,
    GSETTINGS_SCHEMA_USER_THEME,
    GTK4_CONFIG_DIR,
)
from .errors import GSettingsUnavailableError
from .models import ThemeSet

# Import protetto di PyGObject
try:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    _GIO_AVAILABLE = True
except (ImportError, ValueError, AttributeError):
    Gio = None
    _GIO_AVAILABLE = False


class Gtk4OverrideStatus(Enum):
    """Stato del file di override GTK4/Libadwaita."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class GSettingsClient:
    """Client wrapper per leggere e modificare le impostazioni dei temi su GNOME."""

    def __init__(
        self,
        schema_name: str = GSETTINGS_SCHEMA_INTERFACE,
        shell_schema_name: str = GSETTINGS_SCHEMA_USER_THEME,
        custom_schema_dirs: list[Path] | None = None,
    ) -> None:
        """Inizializza il client GSettings e verifica la disponibilità degli schemi.

        Args:
            schema_name: Schema principale per i temi desktop (default: org.gnome.desktop.interface).
            shell_schema_name: Schema per il tema GNOME Shell (default: org.gnome.shell.extensions.user-theme).
            custom_schema_dirs: Cartelle aggiuntive in cui cercare file di schema (opzionale).

        Raises:
            GSettingsUnavailableError: Se PyGObject o lo schema principale dell'interfaccia non sono disponibili.
        """
        self.schema_name = schema_name
        self.shell_schema_name = shell_schema_name
        self.custom_schema_dirs = custom_schema_dirs or []

        # 1. Verifica disponibilità PyGObject
        if not _GIO_AVAILABLE or Gio is None:
            raise GSettingsUnavailableError(
                "PyGObject (gi.repository.Gio) non è disponibile nel sistema. "
                "Assicurati di essere su un ambiente Linux compatibile con GNOME "
                "e che i pacchetti python3-gi e libglib2.0 siano installati."
            )

        # 2. Inizializzazione schema interfaccia principale (obbligatorio)
        self._settings = self._get_settings_for_schema(schema_name)
        if self._settings is None:
            raise GSettingsUnavailableError(
                f"Lo schema GSettings '{schema_name}' non è installato nel sistema. "
                "Questo strumento richiede un ambiente desktop basato su GNOME."
            )

        # 3. Inizializzazione schema Shell User-Theme (cerca nei percorsi di sistema e nelle estensioni utente)
        self._shell_settings = self._get_settings_for_schema(shell_schema_name)

    @property
    def is_shell_theme_supported(self) -> bool:
        """Indica se l'estensione User Themes è installata e il tema Shell è configurabile."""
        return self._shell_settings is not None

    # -------------------------------------------------------------------------
    # Ricerca Dinamica degli Schemi (Inclusi Schemi Estensioni Utente)
    # -------------------------------------------------------------------------

    def _get_settings_for_schema(self, target_schema: str) -> object | None:
        """Trova e istanzia un oggetto Gio.Settings per uno schema.

        Cerca prima nei percorsi globali di sistema ($XDG_DATA_DIRS/glib-2.0/schemas).
        Se non lo trova (come accade spesso per le estensioni GNOME installate dall'utente in ~/.local),
        effettua una scansione nelle cartelle delle estensioni di sistema e utente.
        """
        schema_source = Gio.SettingsSchemaSource.get_default()
        if schema_source is not None:
            schema = schema_source.lookup(target_schema, True)
            if schema is not None:
                try:
                    if hasattr(Gio.Settings, "new_full"):
                        return Gio.Settings.new_full(schema, None, None)
                    return Gio.Settings.new(target_schema)
                except Exception:
                    pass

        # Percorsi delle estensioni GNOME (sia utente che di sistema)
        search_dirs = list(self.custom_schema_dirs)
        search_dirs.extend(
            [
                Path.home() / ".local" / "share" / "gnome-shell" / "extensions",
                Path("/usr/share/gnome-shell/extensions"),
                Path("/usr/local/share/gnome-shell/extensions"),
            ]
        )

        for base in search_dirs:
            if not base.is_dir():
                continue
            try:
                # Scandiamo le sottocartelle delle estensioni cercando le directory 'schemas'
                for entry in base.iterdir():
                    schema_dir = entry / "schemas" if entry.is_dir() else None
                    if schema_dir and schema_dir.is_dir():
                        try:
                            custom_source = Gio.SettingsSchemaSource.new_from_directory(
                                str(schema_dir),
                                schema_source,
                                False,
                            )
                            schema = custom_source.lookup(target_schema, True)
                            if schema is not None:
                                if hasattr(Gio.Settings, "new_full"):
                                    return Gio.Settings.new_full(schema, None, None)
                                return Gio.Settings.new_with_path(target_schema, None)
                        except Exception:  # noqa: S112
                            continue
            except Exception:  # noqa: S112
                continue

        return None

    # -------------------------------------------------------------------------
    # Metodi di Lettura
    # -------------------------------------------------------------------------

    def get_current(self) -> ThemeSet:
        """Legge e restituisce l'insieme dei temi attualmente attivi sul desktop.

        Returns:
            Un oggetto ThemeSet contenente i nomi dei temi GTK, icone, cursori,
            schema colori e tema Shell (se supportato).
        """
        gtk_theme = self._settings.get_string(GSETTINGS_KEY_GTK_THEME)
        icon_theme = self._settings.get_string(GSETTINGS_KEY_ICON_THEME)
        cursor_theme = self._settings.get_string(GSETTINGS_KEY_CURSOR_THEME)

        color_scheme: str | None = None
        if self._has_key(self._settings, GSETTINGS_KEY_COLOR_SCHEME):
            color_scheme = self._settings.get_string(GSETTINGS_KEY_COLOR_SCHEME)

        shell_theme: str | None = None
        if self._shell_settings is not None:
            shell_theme = self._shell_settings.get_string(GSETTINGS_KEY_SHELL_THEME)

        return ThemeSet(
            gtk_theme=gtk_theme,
            icon_theme=icon_theme,
            cursor_theme=cursor_theme,
            color_scheme=color_scheme,
            shell_theme=shell_theme,
        )

    # -------------------------------------------------------------------------
    # Metodi di Scrittura
    # -------------------------------------------------------------------------

    def apply(self, theme_set: ThemeSet) -> None:
        """Applica in blocco tutti i temi valorizzati presenti nel ThemeSet.

        Args:
            theme_set: Oggetto ThemeSet con le configurazioni da applicare.
        """
        if theme_set.gtk_theme is not None:
            self.set_gtk_theme(theme_set.gtk_theme)

        if theme_set.icon_theme is not None:
            self.set_icon_theme(theme_set.icon_theme)

        if theme_set.cursor_theme is not None:
            self.set_cursor_theme(theme_set.cursor_theme)

        if theme_set.color_scheme is not None:
            self.set_color_scheme(theme_set.color_scheme)

        if theme_set.shell_theme is not None:
            self.set_shell_theme(theme_set.shell_theme)

        self._sync()

    def set_gtk_theme(self, name: str) -> None:
        """Imposta il tema GTK."""
        self._settings.set_string(GSETTINGS_KEY_GTK_THEME, name)

    def set_icon_theme(self, name: str) -> None:
        """Imposta il set di icone."""
        self._settings.set_string(GSETTINGS_KEY_ICON_THEME, name)

    def set_cursor_theme(self, name: str) -> None:
        """Imposta il tema dei cursori."""
        self._settings.set_string(GSETTINGS_KEY_CURSOR_THEME, name)

    def set_color_scheme(self, scheme: str) -> None:
        """Imposta lo schema colori (chiaro/scuro, GNOME 42+)."""
        valid_schemes = ["default", "prefer-dark", "prefer-light"]
        if scheme not in valid_schemes:
            raise ValueError(
                f"Schema colore '{scheme}' non valido. Scelte ammesse: {valid_schemes}"
            )

        if self._has_key(self._settings, GSETTINGS_KEY_COLOR_SCHEME):
            self._settings.set_string(GSETTINGS_KEY_COLOR_SCHEME, scheme)

    def set_shell_theme(self, name: str) -> None:
        """Imposta il tema per la GNOME Shell.

        Args:
            name: Il nome del tema Shell (o stringa vuota per ripristinare default).

        Raises:
            GSettingsUnavailableError: Se l'estensione GNOME 'User Themes' non è installata.
        """
        if self._shell_settings is None:
            raise GSettingsUnavailableError(
                "Impossibile impostare il tema della Shell: l'estensione GNOME 'User Themes' "
                "(schema org.gnome.shell.extensions.user-theme) non è installata o abilitata. "
                "Puoi installarla su Ubuntu con: sudo apt install gnome-shell-extension-user-theme"
            )

        self._shell_settings.set_string(GSETTINGS_KEY_SHELL_THEME, name)

    # -------------------------------------------------------------------------
    # Helper Interni
    # -------------------------------------------------------------------------

    @staticmethod
    def _has_key(settings_obj: object | None, key: str) -> bool:
        """Verifica in modo sicuro se una chiave è supportata dallo schema corrente."""
        if settings_obj is None:
            return False
        try:
            if hasattr(settings_obj, "list_keys"):
                return key in settings_obj.list_keys()
            if hasattr(settings_obj, "keys"):
                return key in settings_obj
        except Exception:
            pass
        return False

    def _sync(self) -> None:
        """Sincronizza le modifiche con il backend dconf."""
        try:
            Gio.Settings.sync()
        except Exception:
            pass

    def detect_gtk4_override(self) -> Gtk4OverrideStatus:
        """Verifica se l'override GTK4 è attivo o inattivo.

        Returns:
            Gtk4OverrideStatus corrispondente allo stato reale del file gtk.css.
        """
        css_file = GTK4_CONFIG_DIR / "gtk.css"
        if css_file.is_file():
            return Gtk4OverrideStatus.ACTIVE
        return Gtk4OverrideStatus.INACTIVE
