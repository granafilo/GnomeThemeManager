"""Definizioni di costanti, percorsi XDG e schemi GSettings."""

import os
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

# Percorso per i preset/profili salvati dall'utente
PRESETS_DIR = Path.home() / ".config" / "gnome-theme-manager" / "presets"


# -----------------------------------------------------------------------------
# Risoluzione Dinamica dei Percorsi Temi e Icone (XDG Standard + Legacy Fallback)
# -----------------------------------------------------------------------------


def get_user_themes_dirs() -> list[Path]:
    """Restituisce le directory dei temi utente ($XDG_DATA_HOME/themes e ~/.themes)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = (
        Path(xdg_data).expanduser()
        if xdg_data and xdg_data.strip()
        else Path.home() / ".local" / "share"
    )
    dirs = [base / "themes", Path.home() / ".themes"]
    return list(dict.fromkeys(dirs))


def get_user_icons_dirs() -> list[Path]:
    """Restituisce le directory delle icone/cursori utente ($XDG_DATA_HOME/icons e ~/.icons)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = (
        Path(xdg_data).expanduser()
        if xdg_data and xdg_data.strip()
        else Path.home() / ".local" / "share"
    )
    dirs = [base / "icons", Path.home() / ".icons"]
    return list(dict.fromkeys(dirs))


def get_system_themes_dirs() -> list[Path]:
    """Restituisce le directory dei temi di sistema ($XDG_DATA_DIRS/themes e percorsi standard)."""
    xdg_dirs = os.environ.get("XDG_DATA_DIRS")
    if xdg_dirs and xdg_dirs.strip():
        dirs = [Path(p).expanduser() / "themes" for p in xdg_dirs.split(":") if p.strip()]
    else:
        dirs = [Path("/usr/share/themes"), Path("/usr/local/share/themes")]

    # Assicura sempre la presenza dei percorsi standard di fallback
    for default_path in [Path("/usr/local/share/themes"), Path("/usr/share/themes")]:
        if default_path not in dirs:
            dirs.append(default_path)

    return list(dict.fromkeys(dirs))


def get_system_icons_dirs() -> list[Path]:
    """Restituisce le directory di icone/cursori di sistema ($XDG_DATA_DIRS/icons e percorsi standard)."""
    xdg_dirs = os.environ.get("XDG_DATA_DIRS")
    if xdg_dirs and xdg_dirs.strip():
        dirs = [Path(p).expanduser() / "icons" for p in xdg_dirs.split(":") if p.strip()]
    else:
        dirs = [Path("/usr/share/icons"), Path("/usr/local/share/icons")]

    # Assicura sempre la presenza dei percorsi standard di fallback
    for default_path in [Path("/usr/local/share/icons"), Path("/usr/share/icons")]:
        if default_path not in dirs:
            dirs.append(default_path)

    return list(dict.fromkeys(dirs))


# Liste istantanee esportate per compatibilità
USER_THEMES_DIRS = get_user_themes_dirs()
USER_ICONS_DIRS = get_user_icons_dirs()
SYSTEM_THEMES_DIRS = get_system_themes_dirs()
SYSTEM_ICONS_DIRS = get_system_icons_dirs()
