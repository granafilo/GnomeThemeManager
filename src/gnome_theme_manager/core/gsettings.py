# SPDX-License-Identifier: GPL-3.0-or-later

"""Safe wrapper for GSettings interaction via PyGObject (Gio).

In GNOME desktop environments, GSettings is the central storage system
for desktop preferences and settings (backed primarily by dconf).
This module encapsulates all read and write calls to:
- `org.gnome.desktop.interface` (GTK, Icon, Cursor themes, and Color Scheme)
- `org.gnome.shell.extensions.user-theme` (GNOME Shell theme)
"""

from enum import Enum
from pathlib import Path
from typing import Any

from .constants import (
    GSETTINGS_KEY_COLOR_SCHEME,
    GSETTINGS_KEY_CURSOR_THEME,
    GSETTINGS_KEY_DOCUMENT_FONT_NAME,
    GSETTINGS_KEY_FONT_NAME,
    GSETTINGS_KEY_GTK_THEME,
    GSETTINGS_KEY_ICON_THEME,
    GSETTINGS_KEY_MONOSPACE_FONT_NAME,
    GSETTINGS_KEY_SHELL_THEME,
    GSETTINGS_KEY_TEXT_SCALING_FACTOR,
    GSETTINGS_SCHEMA_INTERFACE,
    GSETTINGS_SCHEMA_USER_THEME,
    GTK4_CONFIG_DIR,
)
from .errors import GSettingsUnavailableError
from .fonts import FontConfig
from .models import ThemeSet

# Protected PyGObject import
try:
    import gi  # type: ignore[import-untyped]

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio  # type: ignore[import-untyped]

    _GIO_AVAILABLE = True
except (ImportError, ValueError, AttributeError):
    Gio = None
    _GIO_AVAILABLE = False


class Gtk4OverrideStatus(Enum):
    """GTK4 / Libadwaita override status."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class GSettingsClient:
    """Wrapper client for reading and updating GNOME theme preferences."""

    def __init__(
        self,
        schema_name: str = GSETTINGS_SCHEMA_INTERFACE,
        shell_schema_name: str = GSETTINGS_SCHEMA_USER_THEME,
        custom_schema_dirs: list[Path] | None = None,
    ) -> None:
        """Initialize GSettings client and verify schema availability.

        Args:
            schema_name: Primary schema for desktop themes (default: org.gnome.desktop.interface).
            shell_schema_name: Schema for GNOME Shell theme (default: org.gnome.shell.extensions.user-theme).
            custom_schema_dirs: Additional directories to search for schema files (optional).

        Raises:
            GSettingsUnavailableError: If PyGObject or the primary interface schema is unavailable.
        """
        self.schema_name = schema_name
        self.shell_schema_name = shell_schema_name
        self.custom_schema_dirs = custom_schema_dirs or []

        # 1. Verify PyGObject availability
        if not _GIO_AVAILABLE or Gio is None:
            raise GSettingsUnavailableError(
                "PyGObject (gi.repository.Gio) is not available on this system. "
                "Ensure you are running on a GNOME-compatible Linux environment "
                "with python3-gi and libglib2.0 packages installed."
            )

        # 2. Initialize primary interface schema (mandatory)
        self._settings: Any = self._get_settings_for_schema(schema_name)
        if self._settings is None:
            raise GSettingsUnavailableError(
                f"GSettings schema '{schema_name}' is not installed on this system. "
                "This tool requires a GNOME-based desktop environment."
            )

        # 3. Initialize Shell User-Theme schema (searches system and user extension paths)
        self._shell_settings: Any = self._get_settings_for_schema(shell_schema_name)

        # 4. Initialize Desktop Background schema (optional fallback for wallpaper)
        self._bg_settings: Any = self._get_settings_for_schema("org.gnome.desktop.background")

    @property
    def is_shell_theme_supported(self) -> bool:
        """Indicate whether the User Themes extension is available and Shell theme can be configured."""
        return self._shell_settings is not None

    def get_wallpaper_path(self) -> Path | None:
        """Get the filesystem path to the currently configured wallpaper image.

        Returns:
            Path to wallpaper image or None if unset or unavailable.
        """
        if self._bg_settings is None:
            return None

        # Check dark mode wallpaper first if prefer-dark is active
        color_scheme = (
            self._settings.get_string(GSETTINGS_KEY_COLOR_SCHEME)
            if self._has_key(self._settings, GSETTINGS_KEY_COLOR_SCHEME)
            else None
        )
        uri = None
        if color_scheme == "prefer-dark" and self._has_key(self._bg_settings, "picture-uri-dark"):
            uri = self._bg_settings.get_string("picture-uri-dark")

        if not uri and self._has_key(self._bg_settings, "picture-uri"):
            uri = self._bg_settings.get_string("picture-uri")

        if not uri:
            return None

        clean_uri = uri.strip().strip("'\"")
        if clean_uri.startswith("file://"):
            from urllib.parse import unquote, urlparse

            parsed = urlparse(clean_uri)
            file_path = Path(unquote(parsed.path))
            return file_path if file_path.is_file() else None
        elif clean_uri.startswith("/"):
            file_path = Path(clean_uri)
            return file_path if file_path.is_file() else None

        return None

    # -------------------------------------------------------------------------
    # Dynamic Schema Resolution (Including User Extensions)
    # -------------------------------------------------------------------------

    def _get_settings_for_schema(self, target_schema: str) -> Any:
        """Find and instantiate a Gio.Settings object for a schema.

        Checks global system locations first ($XDG_DATA_DIRS/glib-2.0/schemas).
        If not found (as is common for user-installed extensions in ~/.local),
        scans extension directories.
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

        # GNOME extension paths (both user and system)
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
                # Scan extension subdirectories for 'schemas' folder
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
    # Read Methods
    # -------------------------------------------------------------------------

    def get_current(self) -> ThemeSet:
        """Read and return current active desktop themes.

        Returns:
            A ThemeSet object containing active GTK, Icon, Cursor,
            color scheme, and Shell theme (if supported).
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
    # Write Methods
    # -------------------------------------------------------------------------

    def apply(self, theme_set: ThemeSet) -> None:
        """Apply all populated theme settings from a ThemeSet.

        Args:
            theme_set: ThemeSet instance with settings to apply.
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
        """Set GTK theme."""
        self._settings.set_string(GSETTINGS_KEY_GTK_THEME, name)

    def set_icon_theme(self, name: str) -> None:
        """Set icon pack."""
        self._settings.set_string(GSETTINGS_KEY_ICON_THEME, name)

    def set_cursor_theme(self, name: str) -> None:
        """Set cursor theme."""
        self._settings.set_string(GSETTINGS_KEY_CURSOR_THEME, name)

    def set_color_scheme(self, scheme: str) -> None:
        """Set color scheme preference (light/dark, GNOME 42+)."""
        valid_schemes = ["default", "prefer-dark", "prefer-light"]
        if scheme not in valid_schemes:
            raise ValueError(f"Invalid color scheme '{scheme}'. Allowed choices: {valid_schemes}")

        if self._has_key(self._settings, GSETTINGS_KEY_COLOR_SCHEME):
            self._settings.set_string(GSETTINGS_KEY_COLOR_SCHEME, scheme)

    def set_shell_theme(self, name: str) -> None:
        """Set GNOME Shell theme.

        Args:
            name: Shell theme name (or empty string for system default).

        Raises:
            GSettingsUnavailableError: If the 'User Themes' GNOME extension is not installed.
        """
        if self._shell_settings is None:
            raise GSettingsUnavailableError(
                "Cannot set GNOME Shell theme: the 'User Themes' extension "
                "(schema org.gnome.shell.extensions.user-theme) is not installed or enabled. "
                "You can install it on Ubuntu with: sudo apt install gnome-shell-extension-user-theme"
            )

        self._shell_settings.set_string(GSETTINGS_KEY_SHELL_THEME, name)

    # -------------------------------------------------------------------------
    # Font Methods (FASE 4 Task 4.3)
    # -------------------------------------------------------------------------

    def get_fonts(self) -> "FontConfig":
        """Read and return current active font configuration.

        Returns:
            A FontConfig dataclass containing the interface, document,
            monospace font names and text scaling factor.
        """
        from .fonts import FontConfig

        interface = self._read_font_string(GSETTINGS_KEY_FONT_NAME, "Cantarell 11")
        document = self._read_font_string(GSETTINGS_KEY_DOCUMENT_FONT_NAME, "Sans 11")
        monospace = self._read_font_string(GSETTINGS_KEY_MONOSPACE_FONT_NAME, "Monospace 11")
        scaling = self._read_scaling_factor()
        return FontConfig(
            interface_font=interface,
            document_font=document,
            monospace_font=monospace,
            text_scaling_factor=scaling,
        )

    def set_fonts(self, fonts: "FontConfig") -> None:
        """Apply a FontConfig to the desktop interface.

        Args:
            fonts: FontConfig instance with font values to apply.
        """
        if fonts.interface_font is not None:
            self.set_interface_font(fonts.interface_font)
        if fonts.document_font is not None:
            self.set_document_font(fonts.document_font)
        if fonts.monospace_font is not None:
            self.set_monospace_font(fonts.monospace_font)
        if fonts.text_scaling_factor is not None:
            self.set_text_scaling_factor(fonts.text_scaling_factor)
        self._sync()

    def apply_fonts(self, fonts: "FontConfig") -> bool:
        """Apply a FontConfig to the desktop interface.

        Args:
            fonts: FontConfig instance with font values to apply.

        Returns:
            True if applied successfully.
        """
        self.set_fonts(fonts)
        return True

    def _read_font_string(self, key: str, default: str) -> str:
        """Read a font-name style string key with a safe fallback."""
        if self._has_key(self._settings, key):
            try:
                val = self._settings.get_string(key)
                return str(val) if val is not None else default
            except Exception:
                return default
        return default

    def _read_scaling_factor(self) -> float:
        """Read text scaling factor with a safe default of 1.0."""
        if self._has_key(self._settings, GSETTINGS_KEY_TEXT_SCALING_FACTOR):
            try:
                return float(self._settings.get_double(GSETTINGS_KEY_TEXT_SCALING_FACTOR))
            except Exception:
                return 1.0
        return 1.0

    def set_interface_font(self, font_spec: str) -> None:
        """Set interface (UI) font name and size, e.g. 'Cantarell 11'."""
        self._settings.set_string(GSETTINGS_KEY_FONT_NAME, font_spec)

    def set_document_font(self, font_spec: str) -> None:
        """Set document font name and size, e.g. 'Sans 11'."""
        self._settings.set_string(GSETTINGS_KEY_DOCUMENT_FONT_NAME, font_spec)

    def set_monospace_font(self, font_spec: str) -> None:
        """Set monospace font name and size, e.g. 'Monospace 11'."""
        self._settings.set_string(GSETTINGS_KEY_MONOSPACE_FONT_NAME, font_spec)

    def set_text_scaling_factor(self, factor: float) -> None:
        """Set text scaling factor (1.0 = default, >1 larger, <1 smaller)."""
        if self._has_key(self._settings, GSETTINGS_KEY_TEXT_SCALING_FACTOR):
            self._settings.set_double(GSETTINGS_KEY_TEXT_SCALING_FACTOR, float(factor))

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _has_key(settings_obj: Any | None, key: str) -> bool:
        """Safely check if a key is supported by the current schema."""
        if settings_obj is None:
            return False
        try:
            if hasattr(settings_obj, "list_keys"):
                return bool(key in settings_obj.list_keys())
            if hasattr(settings_obj, "keys"):
                return bool(key in settings_obj)
        except Exception:
            pass
        return False

    def _sync(self) -> None:
        """Sync changes with the dconf backend."""
        try:
            Gio.Settings.sync()
        except Exception:
            pass

    def detect_gtk4_override(self) -> Gtk4OverrideStatus:
        """Check whether GTK4 override is active or inactive.

        Returns:
            Gtk4OverrideStatus corresponding to gtk.css presence.
        """
        css_file = GTK4_CONFIG_DIR / "gtk.css"
        if css_file.is_file():
            return Gtk4OverrideStatus.ACTIVE
        return Gtk4OverrideStatus.INACTIVE
