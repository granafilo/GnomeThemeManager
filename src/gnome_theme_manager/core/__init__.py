# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo core di GnomeThemeManager."""

from .constants import (
    GLOBAL_THEMES_FILE,
    GSETTINGS_COLOR_SCHEMES,
    GSETTINGS_KEY_COLOR_SCHEME,
    GSETTINGS_KEY_CURSOR_THEME,
    GSETTINGS_KEY_GTK_THEME,
    GSETTINGS_KEY_ICON_THEME,
    GSETTINGS_KEY_SHELL_THEME,
    GSETTINGS_SCHEMA_INTERFACE,
    GSETTINGS_SCHEMA_USER_THEME,
    GTK4_CONFIG_DIR,
    PRESETS_DIR,
    STATE_DIR,
    SYSTEM_ICONS_DIRS,
    SYSTEM_THEMES_DIRS,
    USER_ICONS_DIRS,
    USER_THEMES_DIRS,
)
from .css_extractor import ExtractedColors, extract_theme_colors, parse_css_define_colors
from .errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from .global_themes import GlobalTheme, GlobalThemeManager
from .gsettings import GSettingsClient
from .gtk4_linker import GTK4ThemeLinker
from .installer import (
    ThemeInstaller,
    detect_theme_types,
    inspect_extracted_tree,
    safe_extract,
)
from .manager import ThemeManager
from .models import (
    ApplyResult,
    PropagationResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from .presets import PresetManager
from .sandbox_bridge import SandboxBridge
from .scanner import ThemeScanner
from .theme_editor import ThemeComposition, ThemeMixer
from .theme_validator import ThemeValidationResult, ThemeValidator

__all__ = [
    "GLOBAL_THEMES_FILE",
    "GSETTINGS_COLOR_SCHEMES",
    "GSETTINGS_KEY_COLOR_SCHEME",
    "GSETTINGS_KEY_CURSOR_THEME",
    "GSETTINGS_KEY_GTK_THEME",
    "GSETTINGS_KEY_ICON_THEME",
    "GSETTINGS_KEY_SHELL_THEME",
    "GSETTINGS_SCHEMA_INTERFACE",
    "GSETTINGS_SCHEMA_USER_THEME",
    "GTK4_CONFIG_DIR",
    "PRESETS_DIR",
    "STATE_DIR",
    "SYSTEM_ICONS_DIRS",
    "SYSTEM_THEMES_DIRS",
    "USER_ICONS_DIRS",
    "USER_THEMES_DIRS",
    "ApplyResult",
    "ArchiveExtractionError",
    "ExtractedColors",
    "GSettingsClient",
    "GSettingsUnavailableError",
    "GTK4ThemeLinker",
    "GlobalTheme",
    "GlobalThemeManager",
    "GnomeThemeManagerError",
    "PresetManager",
    "PropagationResult",
    "SandboxBridge",
    "SandboxStatus",
    "SystemStatus",
    "Theme",
    "ThemeComposition",
    "ThemeInstaller",
    "ThemeManager",
    "ThemeMixer",
    "ThemeNotFoundError",
    "ThemeScanner",
    "ThemeSet",
    "ThemeType",
    "ThemeValidationError",
    "ThemeValidationResult",
    "ThemeValidator",
    "detect_theme_types",
    "extract_theme_colors",
    "inspect_extracted_tree",
    "parse_css_define_colors",
    "safe_extract",
]
