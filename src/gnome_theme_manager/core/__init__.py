"""Modulo core di GnomeThemeManager."""

from .constants import (
    GSETTINGS_SCHEMA_INTERFACE,
    GSETTINGS_KEY_GTK_THEME,
    GSETTINGS_KEY_ICON_THEME,
    GSETTINGS_KEY_CURSOR_THEME,
    GSETTINGS_KEY_COLOR_SCHEME,
    USER_THEMES_DIRS,
    USER_ICONS_DIRS,
    SYSTEM_THEMES_DIRS,
    SYSTEM_ICONS_DIRS,
)
from .errors import (
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
    ArchiveExtractionError,
)
from .models import Theme, ThemeSet, ThemeType

__all__ = [
    "GSETTINGS_SCHEMA_INTERFACE",
    "GSETTINGS_KEY_GTK_THEME",
    "GSETTINGS_KEY_ICON_THEME",
    "GSETTINGS_KEY_CURSOR_THEME",
    "GSETTINGS_KEY_COLOR_SCHEME",
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
]
