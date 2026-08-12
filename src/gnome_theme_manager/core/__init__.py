"""Modulo core di GnomeThemeManager."""

from .constants import (
    GSETTINGS_COLOR_SCHEMES,
    GSETTINGS_KEY_COLOR_SCHEME,
    GSETTINGS_KEY_CURSOR_THEME,
    GSETTINGS_KEY_GTK_THEME,
    GSETTINGS_KEY_ICON_THEME,
    GSETTINGS_KEY_SHELL_THEME,
    GSETTINGS_SCHEMA_INTERFACE,
    GSETTINGS_SCHEMA_USER_THEME,
    GTK4_CONFIG_DIR,
    SYSTEM_ICONS_DIRS,
    SYSTEM_THEMES_DIRS,
    USER_ICONS_DIRS,
    USER_THEMES_DIRS,
)
from .errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from .gsettings import GSettingsClient
from .gtk4_linker import GTK4ThemeLinker
from .models import Theme, ThemeSet, ThemeType
from .scanner import ThemeScanner

__all__ = [
    "GSETTINGS_SCHEMA_INTERFACE",
    "GSETTINGS_SCHEMA_USER_THEME",
    "GSETTINGS_KEY_GTK_THEME",
    "GSETTINGS_KEY_ICON_THEME",
    "GSETTINGS_KEY_CURSOR_THEME",
    "GSETTINGS_KEY_COLOR_SCHEME",
    "GSETTINGS_KEY_SHELL_THEME",
    "GSETTINGS_COLOR_SCHEMES",
    "GTK4_CONFIG_DIR",
    "USER_THEMES_DIRS",
    "USER_ICONS_DIRS",
    "SYSTEM_THEMES_DIRS",
    "SYSTEM_ICONS_DIRS",
    "GnomeThemeManagerError",
    "GSettingsUnavailableError",
    "ThemeNotFoundError",
    "ThemeValidationError",
    "ArchiveExtractionError",
    "Theme",
    "ThemeSet",
    "ThemeType",
    "ThemeScanner",
    "GSettingsClient",
    "GTK4ThemeLinker",
]
