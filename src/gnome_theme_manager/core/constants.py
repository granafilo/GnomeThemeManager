# SPDX-License-Identifier: GPL-3.0-or-later

"""Constant definitions, XDG paths, and GSettings schemas."""

import os
from pathlib import Path

# GNOME GSettings schemas and keys (Desktop Interface)
GSETTINGS_SCHEMA_INTERFACE = "org.gnome.desktop.interface"

GSETTINGS_KEY_GTK_THEME = "gtk-theme"
GSETTINGS_KEY_ICON_THEME = "icon-theme"
GSETTINGS_KEY_CURSOR_THEME = "cursor-theme"
GSETTINGS_KEY_COLOR_SCHEME = "color-scheme"

# Font keys (org.gnome.desktop.interface) - FASE 4 Task 4.3
GSETTINGS_KEY_FONT_NAME = "font-name"
GSETTINGS_KEY_DOCUMENT_FONT_NAME = "document-font-name"
GSETTINGS_KEY_MONOSPACE_FONT_NAME = "monospace-font-name"
GSETTINGS_KEY_TEXT_SCALING_FACTOR = "text-scaling-factor"

# Schema and key for GNOME Shell theme (User Themes extension)
GSETTINGS_SCHEMA_USER_THEME = "org.gnome.shell.extensions.user-theme"
GSETTINGS_KEY_SHELL_THEME = "name"

# Schema and keys for GNOME Desktop Background (Wallpaper)
GSETTINGS_SCHEMA_BACKGROUND = "org.gnome.desktop.background"
GSETTINGS_KEY_PICTURE_URI = "picture-uri"
GSETTINGS_KEY_PICTURE_URI_DARK = "picture-uri-dark"

# Supported GNOME color schemes (light/dark preference, GNOME 42+)
GSETTINGS_COLOR_SCHEMES = ("default", "prefer-dark", "prefer-light")

# GTK4 / Libadwaita user configuration directory
GTK4_CONFIG_DIR = Path.home() / ".config" / "gtk-4.0"

# Application state directory (~/.local/state/gnome-theme-manager/)
STATE_DIR = Path.home() / ".local" / "state" / "gnome-theme-manager"

# Directory for user-saved presets and profiles
PRESETS_DIR = Path.home() / ".config" / "gnome-theme-manager" / "presets"

# Global themes state file
GLOBAL_THEMES_FILE = STATE_DIR / "global_themes.json"

# Theme color forks state file (~/.local/state/gnome-theme-manager/theme_forks.json)
THEME_FORKS_FILE = STATE_DIR / "theme_forks.json"

# Persistent editor draft state file (~/.local/state/gnome-theme-manager/editor_draft.json)
EDITOR_DRAFT_FILE = STATE_DIR / "editor_draft.json"

# Persistent editor settings state file (~/.local/state/gnome-theme-manager/editor_settings.json)
EDITOR_SETTINGS_FILE = STATE_DIR / "editor_settings.json"

# Persistent fallback configuration file (~/.local/state/gnome-theme-manager/fallbacks.json)
FALLBACKS_FILE = STATE_DIR / "fallbacks.json"

# Persistent UI preferences file (~/.local/state/gnome-theme-manager/ui_prefs.json)
UI_PREFS_FILE = STATE_DIR / "ui_prefs.json"


# -----------------------------------------------------------------------------
# Dynamic Theme and Icon Path Resolution (XDG Standard + Legacy Fallback)
# -----------------------------------------------------------------------------


def get_user_themes_dirs() -> list[Path]:
    """Return user theme directories (~/.local/share/themes, ~/.themes, and $XDG_DATA_HOME/themes)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    dirs = [
        Path.home() / ".local" / "share" / "themes",
        Path.home() / ".themes",
    ]
    if xdg_data and xdg_data.strip():
        dirs.append(Path(xdg_data).expanduser() / "themes")
    return list(dict.fromkeys(dirs))


def get_user_icons_dirs() -> list[Path]:
    """Return user icon and cursor directories (~/.local/share/icons, ~/.icons, and $XDG_DATA_HOME/icons)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    dirs = [
        Path.home() / ".local" / "share" / "icons",
        Path.home() / ".icons",
    ]
    if xdg_data and xdg_data.strip():
        dirs.append(Path(xdg_data).expanduser() / "icons")
    return list(dict.fromkeys(dirs))


def get_system_themes_dirs() -> list[Path]:
    """Return system theme directories prioritizing host directories over container runtimes."""
    host_dirs = [
        Path("/run/host/usr/share/themes"),
        Path("/run/host/usr/local/share/themes"),
        Path("/run/host/share/themes"),
        Path("/run/host/user-share/themes"),
    ]
    xdg_dirs = os.environ.get("XDG_DATA_DIRS")
    if xdg_dirs and xdg_dirs.strip():
        # Exclude flatpak internal runtime compatibility shims from high-priority system themes
        parsed_dirs = [
            Path(p).expanduser() / "themes"
            for p in xdg_dirs.split(":")
            if p.strip() and "/runtime/" not in p
        ]
    else:
        parsed_dirs = [Path("/usr/share/themes"), Path("/usr/local/share/themes")]

    fallback_dirs = [
        Path("/app/share/themes"),
        Path("/usr/local/share/themes"),
        Path("/usr/share/themes"),
        Path("/usr/share/runtime/share/themes"),
    ]

    all_dirs = host_dirs + parsed_dirs + fallback_dirs
    return list(dict.fromkeys(all_dirs))


def get_system_icons_dirs() -> list[Path]:
    """Return system icon and cursor directories prioritizing host directories over container runtimes."""
    host_dirs = [
        Path("/run/host/usr/share/icons"),
        Path("/run/host/usr/local/share/icons"),
        Path("/run/host/share/icons"),
        Path("/run/host/user-share/icons"),
    ]
    xdg_dirs = os.environ.get("XDG_DATA_DIRS")
    if xdg_dirs and xdg_dirs.strip():
        parsed_dirs = [
            Path(p).expanduser() / "icons"
            for p in xdg_dirs.split(":")
            if p.strip() and "/runtime/" not in p
        ]
    else:
        parsed_dirs = [Path("/usr/share/icons"), Path("/usr/local/share/icons")]

    fallback_dirs = [
        Path("/app/share/icons"),
        Path("/usr/local/share/icons"),
        Path("/usr/share/icons"),
        Path("/usr/share/runtime/share/icons"),
    ]

    all_dirs = host_dirs + parsed_dirs + fallback_dirs
    return list(dict.fromkeys(all_dirs))


# Exported lists for backward compatibility
USER_THEMES_DIRS = get_user_themes_dirs()
USER_ICONS_DIRS = get_user_icons_dirs()
SYSTEM_THEMES_DIRS = get_system_themes_dirs()
SYSTEM_ICONS_DIRS = get_system_icons_dirs()
