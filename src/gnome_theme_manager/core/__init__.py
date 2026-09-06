# SPDX-License-Identifier: GPL-3.0-or-later

"""Core module for GnomeThemeManager."""

from .constants import (
    FALLBACKS_FILE,
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
from .desktop_integration import integrate_desktop
from .editor_draft import EditorDraft, EditorDraftManager
from .errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    StoreDownloadError,
    StoreError,
    StoreItemNotFoundError,
    StoreNetworkError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from .extensions import (
    ExtensionsManager,
    GnomeExtension,
    UIPrefs,
)
from .fallback import (
    FallbackConfig,
    FallbackManager,
    ThemeAvailabilityChecker,
)
from .global_themes import GlobalTheme, GlobalThemeManager
from .gsettings import GSettingsClient
from .gtk4_linker import GTK4ThemeLinker
from .icon_fallback import (
    BUNDLED_ICONS_DIR,
    ICON_FALLBACK_CHAINS,
    STANDARD_SYSTEM_ICON_DIRS,
    IconFallbackResolver,
    IconResolutionResult,
    get_fallback_icon_name,
    resolve_icon,
)
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
from .os_detector import (
    DEPENDENCY_PACKAGE_MAP,
    PACKAGE_MANAGER_INSTALL_TEMPLATES,
    OSInfo,
    detect_os,
    get_extension_manager_install_options,
    get_install_command,
    get_missing_dependency_hint,
    get_os_install_commands,
)
from .presets import PresetManager
from .sandbox_bridge import SandboxBridge
from .scanner import ThemeScanner
from .shell_editor import (
    ShellColorExtractor,
    ShellExtractedColors,
    ShellThemeFork,
    ShellThemeForkManager,
    extract_shell_colors,
    generate_shell_css_override,
)
from .store_client import (
    StoreCategory,
    StoreClient,
    StoreDownloadFile,
    StoreItem,
    theme_type_to_store_category,
)
from .terminal_detector import (
    TerminalInfo,
    detect_default_terminal,
    detect_terminal,
)
from .terminal_palette import (
    TerminalPalette,
    TerminalProfileSummary,
    apply_palette_to_gnome_terminal,
    create_gnome_terminal_profile,
    delete_gnome_terminal_profile,
    derive_terminal_palette_from_colors,
    export_palette_to_json,
    import_palette_from_json,
    list_gnome_terminal_profiles,
    set_default_gnome_terminal_profile,
)
from .terminal_profile import (
    TerminalProfile,
    get_terminal_profile,
)
from .theme_editor import ThemeComposition, ThemeMixer
from .theme_forks import (
    ThemeFork,
    ThemeForkManager,
    create_theme_fork,
    revert_theme_fork,
)
from .theme_validator import ThemeValidationResult, ThemeValidator
from .wallpaper_color import (
    WallpaperColorExtractor,
    extract_dominant_colors_from_image,
    extract_wallpaper_palette,
)

__all__ = [
    "BUNDLED_ICONS_DIR",
    "DEPENDENCY_PACKAGE_MAP",
    "FALLBACKS_FILE",
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
    "ICON_FALLBACK_CHAINS",
    "PACKAGE_MANAGER_INSTALL_TEMPLATES",
    "PRESETS_DIR",
    "STANDARD_SYSTEM_ICON_DIRS",
    "STATE_DIR",
    "SYSTEM_ICONS_DIRS",
    "SYSTEM_THEMES_DIRS",
    "USER_ICONS_DIRS",
    "USER_THEMES_DIRS",
    "ApplyResult",
    "ArchiveExtractionError",
    "EditorDraft",
    "EditorDraftManager",
    "ExtensionsManager",
    "ExtractedColors",
    "FallbackConfig",
    "FallbackManager",
    "GSettingsClient",
    "GSettingsUnavailableError",
    "GTK4ThemeLinker",
    "GlobalTheme",
    "GlobalThemeManager",
    "GnomeExtension",
    "GnomeThemeManagerError",
    "IconFallbackResolver",
    "IconResolutionResult",
    "OSInfo",
    "PresetManager",
    "PropagationResult",
    "SandboxBridge",
    "SandboxStatus",
    "ShellColorExtractor",
    "ShellExtractedColors",
    "ShellThemeFork",
    "ShellThemeForkManager",
    "StoreCategory",
    "StoreClient",
    "StoreDownloadError",
    "StoreDownloadFile",
    "StoreError",
    "StoreItem",
    "StoreItemNotFoundError",
    "StoreNetworkError",
    "SystemStatus",
    "TerminalInfo",
    "TerminalPalette",
    "TerminalProfile",
    "TerminalProfileSummary",
    "Theme",
    "ThemeAvailabilityChecker",
    "ThemeComposition",
    "ThemeFork",
    "ThemeForkManager",
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
    "UIPrefs",
    "WallpaperColorExtractor",
    "apply_palette_to_gnome_terminal",
    "create_gnome_terminal_profile",
    "create_theme_fork",
    "delete_gnome_terminal_profile",
    "derive_terminal_palette_from_colors",
    "detect_default_terminal",
    "detect_os",
    "detect_terminal",
    "detect_theme_types",
    "export_palette_to_json",
    "extract_dominant_colors_from_image",
    "extract_shell_colors",
    "extract_theme_colors",
    "extract_wallpaper_palette",
    "generate_shell_css_override",
    "get_extension_manager_install_options",
    "get_fallback_icon_name",
    "get_install_command",
    "get_missing_dependency_hint",
    "get_os_install_commands",
    "get_terminal_profile",
    "import_palette_from_json",
    "inspect_extracted_tree",
    "integrate_desktop",
    "list_gnome_terminal_profiles",
    "parse_css_define_colors",
    "resolve_icon",
    "revert_theme_fork",
    "safe_extract",
    "set_default_gnome_terminal_profile",
    "theme_type_to_store_category",
]
