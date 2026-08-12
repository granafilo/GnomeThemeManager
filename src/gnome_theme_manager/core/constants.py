"""Definizioni di costanti, percorsi XDG e schemi GSettings."""

from pathlib import Path

# Schemi e chiavi GSettings GNOME (Interfaccia Desktop)
GSETTINGS_SCHEMA_INTERFACE = "org.gnome.desktop.interface"

GSETTINGS_KEY_GTK_THEME = "gtk-theme"
GSETTINGS_KEY_ICON_THEME = "icon-theme"
GSETTINGS_KEY_CURSOR_THEME = "cursor-theme"
GSETTINGS_KEY_COLOR_SCHEME = "color-scheme"

# Schema e chiave per il tema della GNOME Shell (estensione User Themes)
GSETTINGS_SCHEMA_USER_THEME = "org.gnome.shell.extensions.user-theme"
GSETTINGS_KEY_SHELL_THEME = "name"

# Opzioni consentite per lo schema colori di GNOME (modalità chiara/scura, GNOME 42+)
GSETTINGS_COLOR_SCHEMES = ("default", "prefer-dark", "prefer-light")

# Percorso configurazione utente GTK4 / Libadwaita
GTK4_CONFIG_DIR = Path.home() / ".config" / "gtk-4.0"

# Directory temi e icone utente (XDG Data Home + Legacy fallback)
USER_THEMES_DIRS = [
    Path.home() / ".local" / "share" / "themes",
    Path.home() / ".themes",
]

USER_ICONS_DIRS = [
    Path.home() / ".local" / "share" / "icons",
    Path.home() / ".icons",
]

# Directory temi e icone a livello di sistema
SYSTEM_THEMES_DIRS = [
    Path("/usr/share/themes"),
    Path("/usr/local/share/themes"),
]

SYSTEM_ICONS_DIRS = [
    Path("/usr/share/icons"),
    Path("/usr/local/share/icons"),
]
