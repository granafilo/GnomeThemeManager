# SPDX-License-Identifier: GPL-3.0-or-later

"""Terminal Color Palette Model and GNOME Terminal Integration (FASE 4 Task 4.4).

Provides functionality to:
1. Represent a 16-color ANSI terminal palette plus foreground and background colors (`TerminalPalette`).
2. Derive a balanced terminal palette directly from active GTK/CSS extracted colors (`derive_terminal_palette_from_colors`).
3. Export and import terminal palettes to/from JSON files for manual or automated integration.
4. Apply the palette to GNOME Terminal using relocatable GSettings schemas (`org.gnome.Terminal.Legacy.Profile`).
"""

import ast
import configparser
import json
import logging
import os
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .css_extractor import ExtractedColors

logger = logging.getLogger("gnome_theme_manager.core.terminal_palette")

# Try importing Gio safely (consistent with core/gsettings.py)
try:
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    _GIO_AVAILABLE = True
except (ImportError, ValueError, AttributeError):  # pragma: no cover
    Gio = None
    _GIO_AVAILABLE = False


DEFAULT_ANSI_PALETTE = [
    # Normal ANSI colors (0-7)
    "#241f31",  # Black
    "#c01c28",  # Red
    "#26a269",  # Green
    "#a2734c",  # Yellow
    "#12488b",  # Blue
    "#a347ba",  # Magenta
    "#2aa1b3",  # Cyan
    "#d0d0d0",  # White
    # Bright ANSI colors (8-15)
    "#5e5c64",  # Bright Black
    "#f66151",  # Bright Red
    "#33d17a",  # Bright Green
    "#e9ad0c",  # Bright Yellow
    "#2a7bde",  # Bright Blue
    "#c061cb",  # Bright Magenta
    "#33c7de",  # Bright Cyan
    "#ffffff",  # Bright White
]


@dataclass(frozen=True)
class DetectedTerminal:
    """Represents a detected system terminal emulator."""

    terminal_type: str  # "gnome-terminal", "kgx", "konsole", "xfce4-terminal"
    display_name: str  # "GNOME Terminal", "GNOME Console", "Konsole", "XFCE Terminal"
    binary_path: Path | None
    schema_id: str | None
    supports_gsettings: bool
    schema_accessible: bool


@dataclass(frozen=True)
class TerminalProfileSummary:
    """Represents an overview of a GNOME Terminal profile."""

    id: str
    name: str
    is_default: bool


@dataclass(frozen=True)
class TerminalPalette:
    """Represents a 16-color ANSI terminal color scheme and profile preferences."""

    name: str = "Default"
    foreground_color: str = "#d0d0d0"
    background_color: str = "#241f31"
    palette: list[str] = field(default_factory=lambda: list(DEFAULT_ANSI_PALETTE))
    bold_color: str | None = None
    cursor_background_color: str | None = None
    cursor_foreground_color: str | None = None
    # Profile preferences
    use_system_font: bool = True
    font: str = "Monospace 11"
    cursor_shape: str = "block"  # 'block', 'ibeam', 'underline'
    cursor_blink_mode: str = "system"  # 'system', 'on', 'off'
    audible_bell: bool = False
    use_transparent_background: bool = False
    background_transparency_percent: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize palette to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TerminalPalette":
        """Deserialize palette from dictionary."""
        if not data or not isinstance(data, dict):
            return cls()
        palette_list = data.get("palette")
        if not isinstance(palette_list, list) or len(palette_list) != 16:
            palette_list = list(DEFAULT_ANSI_PALETTE)

        return cls(
            name=str(data.get("name", "Custom")),
            foreground_color=str(data.get("foreground_color", "#d0d0d0")),
            background_color=str(data.get("background_color", "#241f31")),
            palette=[str(c) for c in palette_list],
            bold_color=str(data["bold_color"]) if data.get("bold_color") else None,
            cursor_background_color=(
                str(data["cursor_background_color"])
                if data.get("cursor_background_color")
                else None
            ),
            cursor_foreground_color=(
                str(data["cursor_foreground_color"])
                if data.get("cursor_foreground_color")
                else None
            ),
            use_system_font=bool(data.get("use_system_font", True)),
            font=str(data.get("font", "Monospace 11")),
            cursor_shape=str(data.get("cursor_shape", "block")),
            cursor_blink_mode=str(data.get("cursor_blink_mode", "system")),
            audible_bell=bool(data.get("audible_bell", False)),
            use_transparent_background=bool(data.get("use_transparent_background", False)),
            background_transparency_percent=int(data.get("background_transparency_percent", 0)),
        )


def derive_terminal_palette_from_colors(
    colors: ExtractedColors | None,
    name: str = "Theme Derived",
) -> TerminalPalette:
    """Derive a customized 16-color terminal palette from GTK/CSS extracted colors.

    Args:
        colors: Extracted theme colors.
        name: Name for the generated palette.

    Returns:
        TerminalPalette instance with tuned foreground, background, and accent colors.
    """
    if colors is None:
        return TerminalPalette(name=name)

    bg = colors.theme_bg_color or "#241f31"
    fg = colors.theme_fg_color or "#d0d0d0"
    accent = colors.accent_color or colors.theme_selected_bg_color or "#3584e4"

    palette = list(DEFAULT_ANSI_PALETTE)
    # Adjust normal & bright background/black
    palette[0] = bg
    # Adjust blue (index 4 & 12) with accent
    palette[4] = accent
    palette[12] = accent
    # Adjust bright white with foreground
    palette[15] = fg

    return TerminalPalette(
        name=name,
        foreground_color=fg,
        background_color=bg,
        palette=palette,
    )


def export_palette_to_json(palette: TerminalPalette, file_path: Path) -> None:
    """Export a TerminalPalette to a formatted JSON file.

    Args:
        palette: TerminalPalette to save.
        file_path: Destination file path.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(palette.to_dict(), f, indent=2)


def import_palette_from_json(file_path: Path) -> TerminalPalette:
    """Load a TerminalPalette from a JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Loaded TerminalPalette instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If JSON formatting is invalid.
    """
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return TerminalPalette.from_dict(data)


def schema_exists(schema_name: str) -> bool:
    """Safely check if a GSettings schema is installed and accessible (Fix 2)."""
    if _GIO_AVAILABLE and Gio is not None:
        try:
            source = Gio.SettingsSchemaSource.get_default()
            if source is not None and source.lookup(schema_name, True) is not None:
                return True
        except Exception:
            pass

        for host_schema_dir in [
            Path("/run/host/usr/share/glib-2.0/schemas"),
            Path("/run/host/usr/local/share/glib-2.0/schemas"),
            Path("/run/host/share/glib-2.0/schemas"),
        ]:
            if (host_schema_dir / "gschemas.compiled").is_file():
                try:
                    src = Gio.SettingsSchemaSource.new_from_directory(
                        str(host_schema_dir),
                        Gio.SettingsSchemaSource.get_default(),
                        False,
                    )
                    if src.lookup(schema_name, True) is not None:
                        return True
                except Exception:
                    pass

    try:
        res = subprocess.run(
            ["gsettings", "list-keys", schema_name],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    return False


def _is_schema_available(schema_id: str) -> bool:
    """Backward-compatible alias for schema_exists."""
    return schema_exists(schema_id)


def _find_terminal_binary(name: str) -> Path | None:
    """Search for a terminal binary within container or mounted host directories."""
    bin_path = shutil.which(name)
    if bin_path:
        return Path(bin_path)

    for prefix in [
        Path("/run/host/usr/bin"),
        Path("/run/host/bin"),
        Path("/run/host/usr/local/bin"),
        Path("/var/lib/flatpak/exports/bin"),
        Path.home() / ".local/share/flatpak/exports/bin",
    ]:
        cand = prefix / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def _get_settings_instance(schema_id: str, path: str | None = None) -> Any | None:
    """Instantiate Gio.Settings safely using default or host schema sources."""
    if not _GIO_AVAILABLE or Gio is None:
        return None

    source = Gio.SettingsSchemaSource.get_default()
    schema_obj = None
    if source is not None:
        schema_obj = source.lookup(schema_id, True)

    if schema_obj is None:
        for host_schema_dir in [
            Path("/run/host/usr/share/glib-2.0/schemas"),
            Path("/run/host/usr/local/share/glib-2.0/schemas"),
            Path("/run/host/share/glib-2.0/schemas"),
        ]:
            if (host_schema_dir / "gschemas.compiled").is_file():
                try:
                    src = Gio.SettingsSchemaSource.new_from_directory(
                        str(host_schema_dir),
                        source,
                        False,
                    )
                    schema_obj = src.lookup(schema_id, True)
                    if schema_obj is not None:
                        break
                except Exception:
                    pass

    if schema_obj is None:
        return None

    is_default_source = source is not None and schema_obj == source.lookup(schema_id, True)

    try:
        if path:
            if is_default_source and hasattr(Gio.Settings, "new_with_path"):
                return Gio.Settings.new_with_path(schema_id, path)
            return Gio.Settings.new_full(schema_obj, None, path)
        if is_default_source and callable(Gio.Settings):
            try:
                return Gio.Settings(schema_id)
            except (TypeError, Exception):
                pass
        return Gio.Settings.new_full(schema_obj, None, None)
    except Exception as err:
        logger.debug("Failed to instantiate Gio.Settings for %s: %s", schema_id, err)
        return None


def _settings_has_key(settings: Any, key: str) -> bool:
    """Check safely whether a Gio.Settings instance contains a given key without crashing."""
    if settings is None:
        return False
    try:
        # Check list_keys() if available and returns a container
        if hasattr(settings, "list_keys"):
            res = settings.list_keys()
            if isinstance(res, (list, tuple, set)):
                return key in res

        # Check schema.has_key() on real Gio.SettingsSchema
        schema = getattr(settings, "settings_schema", None)
        if schema is None and hasattr(settings, "get_property"):
            try:
                schema = settings.get_property("settings-schema")
            except Exception:
                schema = None
        if schema is not None and hasattr(schema, "has_key"):
            val = schema.has_key(key)
            if isinstance(val, bool):
                return val

        return True
    except Exception:
        return False


def _safe_get_string(settings: Any, key: str, default: str = "") -> str:
    """Get a string value from Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            val = settings.get_string(key)
            return str(val) if val is not None else default
        except Exception:
            pass
    return default


def _safe_get_boolean(settings: Any, key: str, default: bool = False) -> bool:
    """Get a boolean value from Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            val = settings.get_boolean(key)
            return bool(val) if val is not None else default
        except Exception:
            pass
    return default


def _safe_get_double(settings: Any, key: str, default: float = 1.0) -> float:
    """Get a double value from Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            val = settings.get_double(key)
            return float(val) if val is not None else default
        except Exception:
            pass
    return default


def _safe_set_string(settings: Any, key: str, val: str) -> bool:
    """Set a string value in Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            settings.set_string(key, val)
            return True
        except Exception:
            pass
    return False


def _safe_set_boolean(settings: Any, key: str, val: bool) -> bool:
    """Set a boolean value in Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            settings.set_boolean(key, val)
            return True
        except Exception:
            pass
    return False


def _safe_set_double(settings: Any, key: str, val: float) -> bool:
    """Set a double value in Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            settings.set_double(key, val)
            return True
        except Exception:
            pass
    return False


def _safe_get_int(settings: Any, key: str, default: int = 0) -> int:
    """Get an int value from Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            val = settings.get_int(key)
            return int(val) if val is not None else default
        except Exception:
            pass
    return default


def _safe_set_int(settings: Any, key: str, val: int) -> bool:
    """Set an int value in Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            settings.set_int(key, val)
            return True
        except Exception:
            pass
    return False


def _safe_get_strv(settings: Any, key: str, default: list[str] | None = None) -> list[str]:
    """Get a string array from Gio.Settings safely without crashing on missing keys."""
    default_list = default if default is not None else []
    if settings is not None and _settings_has_key(settings, key):
        try:
            val = settings.get_strv(key)
            return list(val) if val is not None else default_list
        except Exception:
            pass
    return default_list


def _safe_set_strv(settings: Any, key: str, val: list[str]) -> bool:
    """Set a string array in Gio.Settings safely without crashing on missing keys."""
    if settings is not None and _settings_has_key(settings, key):
        try:
            settings.set_strv(key, val)
            return True
        except Exception:
            pass
    return False


def gnome_terminal_supports_transparency(profile_id: str | None = None) -> bool:
    """Check if GNOME Terminal schema and profile support transparency keys.

    Vanilla upstream GNOME Terminal (Debian, Arch, etc.) lacks transparency keys,
    whereas Ubuntu and Fedora carry downstream patches adding them.
    """
    if not schema_exists("org.gnome.Terminal.Legacy.Profile"):
        return False

    try:
        if profile_id is None and schema_exists("org.gnome.Terminal.ProfilesList"):
            profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
            if profiles_settings is not None:
                profile_id = profiles_settings.get_string("default")

        if profile_id:
            path = f"/org/gnome/terminal/legacy/profiles:/:{profile_id}/"
            profile = _get_settings_instance("org.gnome.Terminal.Legacy.Profile", path)
            if profile is not None:
                return _settings_has_key(profile, "use-transparent-background")
    except Exception:
        pass

    try:
        from gi.repository import Gio

        source = Gio.SettingsSchemaSource.get_default()
        if source is not None:
            schema = source.lookup("org.gnome.Terminal.Legacy.Profile", True)
            if schema is not None:
                return bool(schema.has_key("use-transparent-background"))
    except Exception:
        pass

    return False


def detect_installed_terminal() -> DetectedTerminal | None:
    """Detect available terminal emulator and its GSettings capabilities (Fix 1).

    Checks for supported terminals in order of preference:
    1. Ptyxis (ptyxis) -> org.gnome.Ptyxis
    2. GNOME Terminal (gnome-terminal) -> org.gnome.Terminal.Legacy.Profile
    3. GNOME Console (kgx) -> org.gnome.Console
    4. Konsole (konsole) -> file-based configuration (no GSettings)
    5. XFCE Terminal (xfce4-terminal) -> org.xfce.terminal

    Returns:
        DetectedTerminal instance, or None if no supported terminal is installed.
    """
    # 1. Ptyxis
    ptyxis_bin = _find_terminal_binary("ptyxis") or _find_terminal_binary("org.gnome.Ptyxis")
    if ptyxis_bin is not None:
        has_schema = schema_exists("org.gnome.Ptyxis")
        return DetectedTerminal(
            terminal_type="ptyxis",
            display_name="Ptyxis",
            binary_path=ptyxis_bin,
            schema_id="org.gnome.Ptyxis" if has_schema else None,
            supports_gsettings=has_schema,
            schema_accessible=has_schema,
        )

    # 2. GNOME Terminal
    gt_bin = _find_terminal_binary("gnome-terminal")
    if gt_bin is not None:
        has_schema = schema_exists("org.gnome.Terminal.Legacy.Profile") and schema_exists(
            "org.gnome.Terminal.ProfilesList"
        )
        return DetectedTerminal(
            terminal_type="gnome-terminal",
            display_name="GNOME Terminal",
            binary_path=gt_bin,
            schema_id="org.gnome.Terminal.Legacy.Profile",
            supports_gsettings=True,
            schema_accessible=has_schema,
        )

    # 2. GNOME Console (kgx)
    kgx_bin = _find_terminal_binary("kgx") or _find_terminal_binary("gnome-console")
    if kgx_bin is not None:
        has_schema = schema_exists("org.gnome.Console")
        return DetectedTerminal(
            terminal_type="kgx",
            display_name="GNOME Console",
            binary_path=kgx_bin,
            schema_id="org.gnome.Console",
            supports_gsettings=True,
            schema_accessible=has_schema,
        )

    # 3. Konsole
    konsole_bin = _find_terminal_binary("konsole")
    if konsole_bin is not None:
        return DetectedTerminal(
            terminal_type="konsole",
            display_name="Konsole",
            binary_path=konsole_bin,
            schema_id=None,
            supports_gsettings=False,
            schema_accessible=False,
        )

    # 4. XFCE Terminal
    xfce_bin = _find_terminal_binary("xfce4-terminal")
    if xfce_bin is not None:
        has_schema = schema_exists("org.xfce.terminal")
        return DetectedTerminal(
            terminal_type="xfce4-terminal",
            display_name="XFCE Terminal",
            binary_path=xfce_bin,
            schema_id="org.xfce.terminal" if has_schema else None,
            supports_gsettings=has_schema,
            schema_accessible=has_schema,
        )

    return None


def apply_palette_to_gnome_console(palette: TerminalPalette) -> bool:
    """Apply compatible preferences to GNOME Console (Fix 5).

    Schema: `org.gnome.Console`

    Args:
        palette: TerminalPalette containing font, bell, and color preferences.

    Returns:
        True if applied successfully, False if schema is unavailable.
    """
    if not schema_exists("org.gnome.Console"):
        logger.warning("GNOME Console schema is unavailable")
        return False

    settings = _get_settings_instance("org.gnome.Console")
    if settings is None:
        return False

    try:
        schema_obj = settings.get_property("settings-schema")
        keys = schema_obj.list_keys() if schema_obj else []

        if "use-system-font" in keys:
            settings.set_boolean("use-system-font", palette.use_system_font)
        if "custom-font" in keys and palette.font:
            settings.set_string("custom-font", palette.font)
        if "audible-bell" in keys:
            settings.set_boolean("audible-bell", palette.audible_bell)
        if "theme" in keys:
            from .css_extractor import _is_color_dark

            is_dark = _is_color_dark(palette.background_color)
            settings.set_string("theme", "dark" if is_dark else "light")

        return True
    except Exception as err:
        logger.warning("Failed to apply settings to GNOME Console: %s", err)
        return False


def list_gnome_terminal_profiles() -> list[TerminalProfileSummary]:
    """List all available GNOME Terminal profiles and default status.

    Returns:
        List of TerminalProfileSummary items.
    """
    if not schema_exists("org.gnome.Terminal.ProfilesList") or not schema_exists(
        "org.gnome.Terminal.Legacy.Profile"
    ):
        return []

    try:
        profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
        if profiles_settings is None:
            return []
        default_id = profiles_settings.get_string("default")
        profile_ids = list(profiles_settings.get_strv("list"))

        summaries: list[TerminalProfileSummary] = []
        for pid in profile_ids:
            path = f"/org/gnome/terminal/legacy/profiles:/:{pid}/"
            try:
                prof_settings = _get_settings_instance("org.gnome.Terminal.Legacy.Profile", path)
                visible_name = (
                    prof_settings.get_string("visible-name")
                    if prof_settings is not None
                    else "Unnamed Profile"
                ) or "Unnamed Profile"
            except Exception:
                visible_name = pid

            summaries.append(
                TerminalProfileSummary(
                    id=pid,
                    name=visible_name,
                    is_default=(pid == default_id),
                )
            )
        return summaries
    except Exception as err:
        logger.debug("Failed to list GNOME Terminal profiles: %s", err)
        return []


def create_gnome_terminal_profile(
    name: str,
    palette: TerminalPalette | None = None,
) -> str | None:
    """Create a new GNOME Terminal profile.

    Args:
        name: Visible name for the new profile.
        palette: Optional initial palette and preferences (uses defaults if None).

    Returns:
        UUID of the newly created profile, or None on failure.
    """
    if not schema_exists("org.gnome.Terminal.ProfilesList") or not schema_exists(
        "org.gnome.Terminal.Legacy.Profile"
    ):
        return None

    try:
        new_id = str(uuid.uuid4())
        profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
        if profiles_settings is None:
            return None
        current_list = list(profiles_settings.get_strv("list"))

        if new_id not in current_list:
            current_list.append(new_id)
            profiles_settings.set_strv("list", current_list)

        path = f"/org/gnome/terminal/legacy/profiles:/:{new_id}/"
        prof_settings = _get_settings_instance("org.gnome.Terminal.Legacy.Profile", path)
        if prof_settings is not None:
            prof_settings.set_string("visible-name", name)

        if palette:
            apply_palette_to_gnome_terminal(palette, profile_id=new_id)

        return new_id
    except Exception as err:
        logger.warning("Failed to create GNOME Terminal profile: %s", err)
        return None


def delete_gnome_terminal_profile(profile_id: str) -> bool:
    """Delete an inactive (non-default) GNOME Terminal profile.

    Args:
        profile_id: UUID of the profile to delete.

    Returns:
        True if deleted, False if profile is default or deletion failed.
    """
    if not schema_exists("org.gnome.Terminal.ProfilesList"):
        return False

    try:
        profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
        if profiles_settings is None:
            return False
        default_id = profiles_settings.get_string("default")

        # Guard: Never delete the active/default profile
        if profile_id == default_id:
            logger.warning("Refusing to delete the active default profile '%s'", profile_id)
            return False

        current_list = list(profiles_settings.get_strv("list"))
        if profile_id in current_list:
            current_list.remove(profile_id)
            profiles_settings.set_strv("list", current_list)
            return True
        return False
    except Exception as err:
        logger.warning("Failed to delete GNOME Terminal profile: %s", err)
        return False


def set_default_gnome_terminal_profile(profile_id: str) -> bool:
    """Set a GNOME Terminal profile as the default.

    Args:
        profile_id: UUID of the profile to set as default.

    Returns:
        True if successful, False otherwise.
    """
    if not schema_exists("org.gnome.Terminal.ProfilesList"):
        return False

    try:
        profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
        if profiles_settings is None:
            return False
        profiles_settings.set_string("default", profile_id)
        return True
    except Exception as err:
        logger.warning("Failed to set default GNOME Terminal profile: %s", err)
        return False


def read_current_gnome_terminal_palette(
    profile_id: str | None = None,
) -> TerminalPalette | None:
    """Read currently configured palette and preferences from GNOME Terminal profile.

    Args:
        profile_id: Optional profile UUID; if None, queries default profile.

    Returns:
        TerminalPalette if found and readable, None otherwise.
    """
    if not schema_exists("org.gnome.Terminal.ProfilesList") or not schema_exists(
        "org.gnome.Terminal.Legacy.Profile"
    ):
        return None

    try:
        if profile_id is None:
            profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
            if profiles_settings is None:
                return None
            profile_id = profiles_settings.get_string("default")

        if not profile_id:
            return None

        path = f"/org/gnome/terminal/legacy/profiles:/:{profile_id}/"
        profile = _get_settings_instance("org.gnome.Terminal.Legacy.Profile", path)
        if profile is None:
            return None

        name = _safe_get_string(profile, "visible-name", "GNOME Terminal") or "GNOME Terminal"
        fg = _safe_get_string(profile, "foreground-color", "#d0d0d0") or "#d0d0d0"
        bg = _safe_get_string(profile, "background-color", "#241f31") or "#241f31"
        raw_pal = _safe_get_strv(profile, "palette")
        pal = list(raw_pal) if raw_pal and len(raw_pal) == 16 else list(DEFAULT_ANSI_PALETTE)

        use_sys_font = _safe_get_boolean(profile, "use-system-font", True)
        font = _safe_get_string(profile, "font", "Monospace 11") or "Monospace 11"
        c_shape = _safe_get_string(profile, "cursor-shape", "block") or "block"
        c_blink = _safe_get_string(profile, "cursor-blink-mode", "system") or "system"
        aud_bell = _safe_get_boolean(profile, "audible-bell", False)
        use_trans = _safe_get_boolean(profile, "use-transparent-background", False)
        trans_pct = _safe_get_int(profile, "background-transparency-percent", 0)

        return TerminalPalette(
            name=name,
            foreground_color=fg,
            background_color=bg,
            palette=pal,
            use_system_font=use_sys_font,
            font=font,
            cursor_shape=c_shape,
            cursor_blink_mode=c_blink,
            audible_bell=aud_bell,
            use_transparent_background=use_trans,
            background_transparency_percent=trans_pct,
        )
    except Exception as err:
        logger.debug("Could not read current GNOME Terminal settings: %s", err)
        return None


def apply_palette_to_gnome_terminal(
    palette: TerminalPalette,
    profile_id: str | None = None,
) -> bool:
    """Apply a terminal palette and profile preferences to GNOME Terminal.

    Schema: `org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<profile_id>/`

    Args:
        palette: Palette to apply.
        profile_id: Optional profile UUID; if None, queries default profile.

    Returns:
        True if applied successfully, False if GNOME Terminal schema is unavailable.
    """
    if not schema_exists("org.gnome.Terminal.ProfilesList") or not schema_exists(
        "org.gnome.Terminal.Legacy.Profile"
    ):
        logger.warning("GNOME Terminal schemas are unavailable; cannot apply palette")
        return False

    try:
        if profile_id is None:
            # Query default profile UUID from legacy settings
            profiles_settings = _get_settings_instance("org.gnome.Terminal.ProfilesList")
            if profiles_settings is None:
                return False
            profile_id = profiles_settings.get_string("default")

        if not profile_id:
            logger.warning("No GNOME Terminal profile ID found")
            return False

        path = f"/org/gnome/terminal/legacy/profiles:/:{profile_id}/"
        profile = _get_settings_instance("org.gnome.Terminal.Legacy.Profile", path)
        if profile is None:
            return False

        _safe_set_boolean(profile, "use-theme-colors", False)
        _safe_set_string(profile, "foreground-color", palette.foreground_color)
        _safe_set_string(profile, "background-color", palette.background_color)
        _safe_set_strv(profile, "palette", palette.palette)
        if palette.bold_color:
            _safe_set_string(profile, "bold-color", palette.bold_color)

        # Profile preferences
        _safe_set_boolean(profile, "use-system-font", palette.use_system_font)
        if palette.font:
            _safe_set_string(profile, "font", palette.font)
        _safe_set_string(profile, "cursor-shape", palette.cursor_shape)
        _safe_set_string(profile, "cursor-blink-mode", palette.cursor_blink_mode)
        _safe_set_boolean(profile, "audible-bell", palette.audible_bell)
        _safe_set_boolean(profile, "use-transparent-background", palette.use_transparent_background)
        _safe_set_int(
            profile, "background-transparency-percent", palette.background_transparency_percent
        )

        return True
    except Exception as err:
        logger.warning("Failed to apply palette to GNOME Terminal: %s", err)
        return False


# -----------------------------------------------------------------------------
# dconf Direct CLI Helpers
# -----------------------------------------------------------------------------


def _safe_write_file_with_host_fallback(file_path: Path, content: str) -> bool:
    """Safely write a text file locally, falling back to flatpak-spawn if sandboxed."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return True
    except (PermissionError, OSError) as err:
        logger.debug(
            "Local write to %s failed: %s. Attempting flatpak-spawn fallback...", file_path, err
        )
        if shutil.which("flatpak-spawn"):
            try:
                py_code = (
                    "import pathlib, sys\n"
                    f"p = pathlib.Path({str(file_path)!r})\n"
                    "p.parent.mkdir(parents=True, exist_ok=True)\n"
                    "p.write_text(sys.stdin.read(), encoding='utf-8')\n"
                )
                proc = subprocess.run(
                    ["flatpak-spawn", "--host", "python3", "-c", py_code],
                    input=content,
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if proc.returncode == 0:
                    return True
                logger.warning("flatpak-spawn file write failed: %s", proc.stderr)
            except Exception as host_err:
                logger.warning("flatpak-spawn write error: %s", host_err)
    return False


def _safe_read_file_with_host_fallback(file_path: Path) -> str | None:
    """Safely read a text file locally, falling back to flatpak-spawn if sandboxed."""
    try:
        if file_path.is_file():
            return file_path.read_text(encoding="utf-8")
    except (PermissionError, OSError):
        pass
    if shutil.which("flatpak-spawn"):
        try:
            res = subprocess.run(
                ["flatpak-spawn", "--host", "cat", str(file_path)],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass
    return None


def _dconf_read(path: str) -> str | None:
    """Safely read a key directly from dconf CLI with host fallback.

    Args:
        path: Path to the dconf key.

    Returns:
        Stripped string output if returncode is 0, None otherwise.
    """
    try:
        res = subprocess.run(
            ["dconf", "read", path],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            val = res.stdout.strip()
            return val if val else None
    except Exception as err:
        logger.debug("Failed dconf read for %s: %s", path, err)

    if shutil.which("flatpak-spawn"):
        try:
            res = subprocess.run(
                ["flatpak-spawn", "--host", "dconf", "read", path],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if res.returncode == 0:
                val = res.stdout.strip()
                return val if val else None
        except Exception:
            pass

    return None


def _dconf_write(path: str, value: str) -> bool:
    """Safely write a key directly to dconf CLI with host fallback.

    Args:
        path: Path to the dconf key.
        value: Exact serialized value to write.

    Returns:
        True if returncode is 0, False otherwise.
    """
    try:
        res = subprocess.run(
            ["dconf", "write", path, value],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            return True
    except Exception as err:
        logger.debug("Failed dconf write for %s: %s", path, err)

    if shutil.which("flatpak-spawn"):
        try:
            res = subprocess.run(
                ["flatpak-spawn", "--host", "dconf", "write", path, value],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            pass

    return False


# -----------------------------------------------------------------------------
# Ptyxis Palette and Profile Management (GNOME 47+, CachyOS, Fedora 41+)
# -----------------------------------------------------------------------------


def export_ptyxis_palette(
    palette: TerminalPalette,
    name: str = "Gnome-Theme-Manager",
    target_dir: Path | None = None,
) -> Path:
    """Export a TerminalPalette to a Ptyxis INI .palette file.

    Ptyxis loads custom palettes from ~/.local/share/org.gnome.Ptyxis/palettes/
    or Flatpak data directories.

    Args:
        palette: TerminalPalette instance to serialize.
        name: Name for the palette inside Ptyxis.
        target_dir: Optional custom destination folder (used for testing/overrides).

    Returns:
        Path to the saved .palette file.
    """
    if target_dir is None:
        target_dir = Path.home() / ".local/share/org.gnome.Ptyxis/palettes"

    safe_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_")
    if not safe_filename:
        safe_filename = "custom"
    file_path = target_dir / f"{safe_filename}.palette"

    lines = [
        "[Palette]",
        f"Name={name}",
        "Primary=true",
        "",
        "[Dark]",
        f"Foreground={palette.foreground_color}",
        f"Background={palette.background_color}",
    ]
    for idx, color in enumerate(palette.palette[:16]):
        lines.append(f"Color{idx}={color}")
    if palette.bold_color:
        lines.append(f"Bold={palette.bold_color}")
    if palette.cursor_background_color:
        lines.append(f"Cursor={palette.cursor_background_color}")

    lines.extend(
        [
            "",
            "[Light]",
            f"Foreground={palette.foreground_color}",
            f"Background={palette.background_color}",
        ]
    )
    for idx, color in enumerate(palette.palette[:16]):
        lines.append(f"Color{idx}={color}")
    if palette.bold_color:
        lines.append(f"Bold={palette.bold_color}")
    if palette.cursor_background_color:
        lines.append(f"Cursor={palette.cursor_background_color}")

    lines.append("")
    content = "\n".join(lines)
    if not _safe_write_file_with_host_fallback(file_path, content):
        file_path.write_text(content, encoding="utf-8")

    # If Flatpak user dir exists, synchronize there as well
    for flatpak_base in [
        Path.home() / ".var/app/org.gnome.Ptyxis/data/ptyxis/palettes",
        Path.home() / ".var/app/org.gnome.Ptyxis/data/org.gnome.Ptyxis/palettes",
        Path.home() / ".var/app/app.devsuite.Ptyxis/data/ptyxis/palettes",
        Path.home() / ".var/app/app.devsuite.Ptyxis/data/org.gnome.Ptyxis/palettes",
    ]:
        if flatpak_base.parent.is_dir():
            _safe_write_file_with_host_fallback(flatpak_base / f"{safe_filename}.palette", content)

    return file_path


def list_ptyxis_profiles() -> list[TerminalProfileSummary]:
    """List configured Ptyxis profiles with fallback to default profile.

    Returns:
        List of TerminalProfileSummary instances.
    """
    profile_uuids: list[str] = []
    default_uuid: str | None = None

    settings = _get_settings_instance("org.gnome.Ptyxis")
    if settings is not None:
        try:
            profile_uuids = list(settings.get_strv("profile-uuids"))
            default_uuid = settings.get_string("default-profile-uuid")
        except Exception as err:
            logger.debug("Failed reading Ptyxis profiles from Gio.Settings: %s", err)

    if not profile_uuids:
        raw_list = _dconf_read("/org/gnome/Ptyxis/profile-uuids")
        if raw_list:
            try:
                parsed = ast.literal_eval(raw_list)
                if isinstance(parsed, list):
                    profile_uuids = [str(item) for item in parsed]
            except Exception:
                pass

    if not default_uuid:
        raw_default = _dconf_read("/org/gnome/Ptyxis/default-profile-uuid")
        if raw_default:
            default_uuid = raw_default.strip("'\"")

    if not profile_uuids:
        if default_uuid:
            profile_uuids = [default_uuid]
        else:
            return [TerminalProfileSummary(id="default", name="Default", is_default=True)]

    if not default_uuid and profile_uuids:
        default_uuid = profile_uuids[0]

    summaries: list[TerminalProfileSummary] = []
    for pid in profile_uuids:
        name = ""
        prof_settings = _get_settings_instance(
            "org.gnome.Ptyxis.Profile", path=f"/org/gnome/Ptyxis/Profiles/{pid}/"
        )
        if prof_settings is not None:
            try:
                name = prof_settings.get_string("label")
            except Exception:
                pass

        if not name:
            raw_label = _dconf_read(f"/org/gnome/Ptyxis/Profiles/{pid}/label")
            if raw_label:
                name = raw_label.strip("'\"")

        if not name:
            name = "Default" if pid == default_uuid else f"Profile ({pid[:8]})"

        summaries.append(
            TerminalProfileSummary(
                id=pid,
                name=name,
                is_default=(pid == default_uuid),
            )
        )

    return summaries


def set_default_ptyxis_profile(profile_id: str) -> bool:
    """Set a Ptyxis profile UUID as the default profile.

    Args:
        profile_id: UUID of the profile.

    Returns:
        True if updated successfully, False otherwise.
    """
    settings = _get_settings_instance("org.gnome.Ptyxis")
    if settings is not None:
        try:
            settings.set_string("default-profile-uuid", profile_id)
            return True
        except Exception as err:
            logger.debug("Failed setting default Ptyxis profile via Gio: %s", err)

    return _dconf_write("/org/gnome/Ptyxis/default-profile-uuid", f"'{profile_id}'")


def create_ptyxis_profile(name: str, palette: TerminalPalette | None = None) -> str | None:
    """Create a new profile in Ptyxis.

    Args:
        name: Visible label for the new profile.
        palette: Optional palette to immediately apply.

    Returns:
        UUID of the created profile, or None on failure.
    """
    new_uuid = str(uuid.uuid4())
    profiles = list_ptyxis_profiles()
    existing_uuids = [p.id for p in profiles if p.id != "default"]
    if new_uuid not in existing_uuids:
        existing_uuids.append(new_uuid)

    success = False
    settings = _get_settings_instance("org.gnome.Ptyxis")
    if settings is not None:
        try:
            settings.set_strv("profile-uuids", existing_uuids)
            success = True
        except Exception as err:
            logger.debug("Failed updating profile-uuids via Gio: %s", err)

    if not success:
        formatted = "[" + ", ".join(f"'{u}'" for u in existing_uuids) + "]"
        success = _dconf_write("/org/gnome/Ptyxis/profile-uuids", formatted)

    # Set label
    prof_settings = _get_settings_instance(
        "org.gnome.Ptyxis.Profile", path=f"/org/gnome/Ptyxis/Profiles/{new_uuid}/"
    )
    if prof_settings is not None:
        try:
            prof_settings.set_string("label", name)
        except Exception:
            pass
    _dconf_write(f"/org/gnome/Ptyxis/Profiles/{new_uuid}/label", f"'{name}'")

    if palette is not None:
        apply_palette_to_ptyxis(palette, profile_id=new_uuid)

    return new_uuid if success else None


def delete_ptyxis_profile(profile_id: str) -> bool:
    """Delete a Ptyxis profile by UUID. Cannot delete the active default profile."""
    profiles = list_ptyxis_profiles()
    target = next((p for p in profiles if p.id == profile_id), None)
    if target is None or target.is_default:
        logger.warning("Cannot delete default or nonexistent Ptyxis profile: %s", profile_id)
        return False

    remaining_uuids = [p.id for p in profiles if p.id != profile_id and p.id != "default"]
    success = False
    settings = _get_settings_instance("org.gnome.Ptyxis")
    if settings is not None:
        try:
            settings.set_strv("profile-uuids", remaining_uuids)
            success = True
        except Exception:
            pass

    if not success:
        formatted = "[" + ", ".join(f"'{u}'" for u in remaining_uuids) + "]"
        success = _dconf_write("/org/gnome/Ptyxis/profile-uuids", formatted)

    try:
        subprocess.run(
            ["dconf", "reset", "-f", f"/org/gnome/Ptyxis/Profiles/{profile_id}/"],
            capture_output=True,
            timeout=2,
            check=False,
        )
    except Exception:
        pass

    return success


def read_current_ptyxis_palette(
    profile_id: str | None = None,
) -> TerminalPalette | None:
    """Read active preferences and color scheme for a Ptyxis profile."""
    if profile_id is None or profile_id == "default":
        settings = _get_settings_instance("org.gnome.Ptyxis")
        if settings is not None:
            try:
                profile_id = settings.get_string("default-profile-uuid")
            except Exception:
                pass
        if not profile_id or profile_id == "default":
            raw_default = _dconf_read("/org/gnome/Ptyxis/default-profile-uuid")
            if raw_default:
                profile_id = raw_default.strip("'\"")

    label = "Ptyxis"
    palette_name = "Default"
    use_custom_font = False
    font_name = "Monospace 11"
    opacity = 1.0
    c_shape = "block"
    c_blink = "system"
    aud_bell = False

    # 1. Read app-level font and cursor settings from org.gnome.Ptyxis
    app_settings = _get_settings_instance("org.gnome.Ptyxis")
    if app_settings is not None:
        use_custom_font = not _safe_get_boolean(app_settings, "use-system-font", True)
        font_name = _safe_get_string(app_settings, "font-name", font_name) or font_name
        c_shape = _safe_get_string(app_settings, "cursor-shape", c_shape) or c_shape
        c_blink = _safe_get_string(app_settings, "cursor-blink-mode", c_blink) or c_blink
        aud_bell = _safe_get_boolean(app_settings, "audible-bell", aud_bell)
    else:
        raw_cust_font = _dconf_read("/org/gnome/Ptyxis/use-system-font")
        if raw_cust_font:
            use_custom_font = raw_cust_font.lower() != "true"
        raw_font = _dconf_read("/org/gnome/Ptyxis/font-name")
        if raw_font:
            font_name = raw_font.strip("'\"")
        raw_shape = _dconf_read("/org/gnome/Ptyxis/cursor-shape")
        if raw_shape:
            c_shape = raw_shape.strip("'\"")
        raw_blink = _dconf_read("/org/gnome/Ptyxis/cursor-blink-mode")
        if raw_blink:
            c_blink = raw_blink.strip("'\"")
        raw_bell = _dconf_read("/org/gnome/Ptyxis/audible-bell")
        if raw_bell:
            aud_bell = raw_bell.lower() == "true"

    # 2. Read profile-level settings from org.gnome.Ptyxis.Profile
    if profile_id and profile_id != "default":
        prof_settings = _get_settings_instance(
            "org.gnome.Ptyxis.Profile", path=f"/org/gnome/Ptyxis/Profiles/{profile_id}/"
        )
        if prof_settings is not None:
            label = _safe_get_string(prof_settings, "label", label) or label
            palette_name = _safe_get_string(prof_settings, "palette", palette_name) or palette_name
            opacity = _safe_get_double(prof_settings, "opacity", opacity)
        else:
            raw_pal = _dconf_read(f"/org/gnome/Ptyxis/Profiles/{profile_id}/palette")
            if raw_pal:
                palette_name = raw_pal.strip("'\"")
            raw_label = _dconf_read(f"/org/gnome/Ptyxis/Profiles/{profile_id}/label")
            if raw_label:
                label = raw_label.strip("'\"")
            raw_opac = _dconf_read(f"/org/gnome/Ptyxis/Profiles/{profile_id}/opacity")
            if raw_opac:
                try:
                    opacity = float(raw_opac)
                except ValueError:
                    pass

    # Locate the .palette file for palette_name
    colors = list(DEFAULT_ANSI_PALETTE)
    fg = "#d0d0d0"
    bg = "#241f31"

    search_dirs = [
        Path.home() / ".local/share/org.gnome.Ptyxis/palettes",
        Path.home() / ".var/app/org.gnome.Ptyxis/data/ptyxis/palettes",
        Path.home() / ".var/app/org.gnome.Ptyxis/data/org.gnome.Ptyxis/palettes",
        Path.home() / ".var/app/app.devsuite.Ptyxis/data/ptyxis/palettes",
        Path.home() / ".var/app/app.devsuite.Ptyxis/data/org.gnome.Ptyxis/palettes",
        Path("/usr/share/org.gnome.Ptyxis/palettes"),
    ]

    for sdir in search_dirs:
        cand = sdir / f"{palette_name}.palette"
        if not cand.is_file() and sdir.is_dir():
            for pfile in sdir.glob("*.palette"):
                try:
                    cfg = configparser.ConfigParser()
                    cfg.read(str(pfile), encoding="utf-8")
                    if (
                        cfg.has_section("Palette")
                        and cfg.get("Palette", "Name", fallback="") == palette_name
                    ):
                        cand = pfile
                        break
                except Exception:
                    pass
        if cand.is_file():
            try:
                cfg = configparser.ConfigParser()
                cfg.read(str(cand), encoding="utf-8")
                sect = (
                    "Dark"
                    if cfg.has_section("Dark")
                    else ("Palette" if cfg.has_section("Palette") else None)
                )
                if sect:
                    fg = cfg.get(sect, "Foreground", fallback=fg)
                    bg = cfg.get(sect, "Background", fallback=bg)
                    for i in range(16):
                        col = cfg.get(sect, f"Color{i}", fallback=None)
                        if col:
                            colors[i] = col
                break
            except Exception as err:
                logger.debug("Error reading palette file %s: %s", cand, err)

    use_trans = opacity < 0.999
    trans_pct = round((1.0 - opacity) * 100) if use_trans else 0

    return TerminalPalette(
        name=label,
        foreground_color=fg,
        background_color=bg,
        palette=colors,
        use_system_font=not use_custom_font,
        font=font_name,
        cursor_shape=c_shape,
        cursor_blink_mode=c_blink,
        audible_bell=aud_bell,
        use_transparent_background=use_trans,
        background_transparency_percent=trans_pct,
    )


def apply_palette_to_ptyxis(
    palette: TerminalPalette,
    profile_id: str | None = None,
    palette_name: str = "Gnome-Theme-Manager",
    target_dir: Path | None = None,
) -> bool:
    """Apply a TerminalPalette to Ptyxis terminal emulator.

    Generates the .palette file and assigns the palette and preferences to the target profile.

    Args:
        palette: TerminalPalette containing ANSI colors, fonts, opacity.
        profile_id: Optional UUID of the profile. If None, targets default profile.
        palette_name: Name of the palette to install and assign.
        target_dir: Optional custom directory to write .palette file to.

    Returns:
        True if applied successfully, False on failure.
    """
    try:
        export_ptyxis_palette(palette, name=palette_name, target_dir=target_dir)
    except Exception as err:
        logger.warning("Failed to write Ptyxis palette file: %s", err)
        return False

    # Resolve target profile UUID
    target_uuid = profile_id
    if not target_uuid or target_uuid == "default":
        settings = _get_settings_instance("org.gnome.Ptyxis")
        if settings is not None:
            try:
                target_uuid = settings.get_string("default-profile-uuid")
            except Exception:
                pass
        if not target_uuid:
            raw_default = _dconf_read("/org/gnome/Ptyxis/default-profile-uuid")
            if raw_default:
                target_uuid = raw_default.strip("'\"")

    if not target_uuid:
        target_uuid = str(uuid.uuid4())
        settings = _get_settings_instance("org.gnome.Ptyxis")
        if settings is not None:
            try:
                settings.set_string("default-profile-uuid", target_uuid)
                settings.set_strv("profile-uuids", [target_uuid])
            except Exception:
                pass
        _dconf_write("/org/gnome/Ptyxis/default-profile-uuid", f"'{target_uuid}'")
        _dconf_write("/org/gnome/Ptyxis/profile-uuids", f"['{target_uuid}']")

    # Apply preferences
    opacity = (
        max(0.0, min(1.0, 1.0 - (palette.background_transparency_percent / 100.0)))
        if palette.use_transparent_background
        else 1.0
    )

    path = f"/org/gnome/Ptyxis/Profiles/{target_uuid}/"
    prof_settings = _get_settings_instance("org.gnome.Ptyxis.Profile", path=path)

    applied_profile = False
    if prof_settings is not None:
        _safe_set_string(prof_settings, "palette", palette_name)
        _safe_set_double(prof_settings, "opacity", opacity)
        applied_profile = True
    else:
        _dconf_write(f"{path}palette", f"'{palette_name}'")
        _dconf_write(f"{path}opacity", f"{opacity:.4f}")
        applied_profile = True

    # App-level font & cursor settings
    app_settings = _get_settings_instance("org.gnome.Ptyxis")
    if app_settings is not None:
        _safe_set_boolean(app_settings, "use-system-font", palette.use_system_font)
        if palette.font:
            _safe_set_string(app_settings, "font-name", palette.font)
        _safe_set_string(app_settings, "cursor-shape", palette.cursor_shape)
        _safe_set_string(app_settings, "cursor-blink-mode", palette.cursor_blink_mode)
        _safe_set_boolean(app_settings, "audible-bell", palette.audible_bell)
    else:
        _dconf_write(
            "/org/gnome/Ptyxis/use-system-font",
            "true" if palette.use_system_font else "false",
        )
        if palette.font:
            _dconf_write("/org/gnome/Ptyxis/font-name", f"'{palette.font}'")
        _dconf_write("/org/gnome/Ptyxis/cursor-shape", f"'{palette.cursor_shape}'")
        _dconf_write("/org/gnome/Ptyxis/cursor-blink-mode", f"'{palette.cursor_blink_mode}'")
        _dconf_write(
            "/org/gnome/Ptyxis/audible-bell",
            "true" if palette.audible_bell else "false",
        )

    return applied_profile


# -----------------------------------------------------------------------------
# Alacritty and Kitty File-Based Palette Management (CachyOS, Arch, etc.)
# -----------------------------------------------------------------------------


def _parse_pango_font(font_str: str) -> tuple[str, float]:
    """Split Pango font description into family name and size.

    Args:
        font_str: Pango font string (e.g. 'FiraCode Nerd Font 11' or 'Monospace 10.5').

    Returns:
        Tuple of (font_family, font_size_float).
    """
    parts = font_str.strip().rsplit(" ", 1)
    if len(parts) == 2:
        try:
            size = float(parts[1])
            return parts[0].strip(), size
        except ValueError:
            pass
    return font_str.strip(), 11.0


def apply_palette_to_alacritty(
    palette: TerminalPalette,
    config_path: Path | None = None,
) -> bool:
    """Apply a TerminalPalette to Alacritty configuration (alacritty.toml).

    Preserves existing user configurations outside of color/font/window/cursor sections.

    Args:
        palette: TerminalPalette containing ANSI colors, fonts, opacity.
        config_path: Optional custom Path to alacritty.toml.

    Returns:
        True if applied and written successfully, False otherwise.
    """
    if config_path is None:
        config_path = Path.home() / ".config/alacritty/alacritty.toml"

    opacity = (
        max(0.0, min(1.0, 1.0 - (palette.background_transparency_percent / 100.0)))
        if palette.use_transparent_background
        else 1.0
    )

    alacritty_colors_norm = [
        ("black", palette.palette[0] if len(palette.palette) > 0 else "#241f31"),
        ("red", palette.palette[1] if len(palette.palette) > 1 else "#c01c28"),
        ("green", palette.palette[2] if len(palette.palette) > 2 else "#26a269"),
        ("yellow", palette.palette[3] if len(palette.palette) > 3 else "#a2734c"),
        ("blue", palette.palette[4] if len(palette.palette) > 4 else "#12488b"),
        ("magenta", palette.palette[5] if len(palette.palette) > 5 else "#a347ba"),
        ("cyan", palette.palette[6] if len(palette.palette) > 6 else "#2aa1b3"),
        ("white", palette.palette[7] if len(palette.palette) > 7 else "#d0d0d0"),
    ]

    alacritty_colors_bright = [
        ("black", palette.palette[8] if len(palette.palette) > 8 else "#5e5c64"),
        ("red", palette.palette[9] if len(palette.palette) > 9 else "#f66151"),
        ("green", palette.palette[10] if len(palette.palette) > 10 else "#33d17a"),
        ("yellow", palette.palette[11] if len(palette.palette) > 11 else "#e9ad0c"),
        ("blue", palette.palette[12] if len(palette.palette) > 12 else "#2a7bde"),
        ("magenta", palette.palette[13] if len(palette.palette) > 13 else "#c061cb"),
        ("cyan", palette.palette[14] if len(palette.palette) > 14 else "#33c7de"),
        ("white", palette.palette[15] if len(palette.palette) > 15 else "#ffffff"),
    ]

    c_shape = "Block"
    if palette.cursor_shape == "ibeam":
        c_shape = "Beam"
    elif palette.cursor_shape == "underline":
        c_shape = "Underline"

    c_blink = "Always"
    if palette.cursor_blink_mode == "on":
        c_blink = "On"
    elif palette.cursor_blink_mode == "off":
        c_blink = "Off"

    managed_prefixes: tuple[str, ...] = (
        "colors",
        "cursor",
    )
    if not palette.use_system_font and palette.font:
        managed_prefixes = managed_prefixes + ("font",)

    # Read existing content if available
    existing_content = _safe_read_file_with_host_fallback(config_path) or ""
    kept_sections: list[tuple[str, list[str]]] = []
    current_sec = ""
    current_lines: list[str] = []

    for line in existing_content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("[") and trimmed.endswith("]") and not trimmed.startswith("[["):
            sec_name = trimmed[1:-1].strip()
            if current_sec or current_lines:
                kept_sections.append((current_sec, current_lines))
            current_sec = sec_name
            current_lines = []
        else:
            current_lines.append(line)
    if current_sec or current_lines:
        kept_sections.append((current_sec, current_lines))

    # Filter out managed sections and update window opacity
    new_output_lines: list[str] = []
    window_handled = False

    for sec_name, lines in kept_sections:
        is_managed = any(
            sec_name == pfx or sec_name.startswith(f"{pfx}.") for pfx in managed_prefixes
        )
        if is_managed:
            continue

        if sec_name == "window":
            window_handled = True
            new_output_lines.append("[window]")
            op_set = False
            for l in lines:
                if l.strip().startswith("opacity") and "=" in l:
                    new_output_lines.append(f"opacity = {opacity:.2f}")
                    op_set = True
                else:
                    new_output_lines.append(l)
            if not op_set:
                new_output_lines.append(f"opacity = {opacity:.2f}")
            new_output_lines.append("")
        elif sec_name:
            new_output_lines.append(f"[{sec_name}]")
            new_output_lines.extend(lines)
            new_output_lines.append("")
        else:
            new_output_lines.extend(lines)
            if lines:
                new_output_lines.append("")

    if not window_handled:
        new_output_lines.append("[window]")
        new_output_lines.append(f"opacity = {opacity:.2f}")
        new_output_lines.append("")

    # Add Colors
    new_output_lines.append("[colors.primary]")
    new_output_lines.append(f'background = "{palette.background_color}"')
    new_output_lines.append(f'foreground = "{palette.foreground_color}"')
    if palette.bold_color:
        new_output_lines.append(f'bold = "{palette.bold_color}"')
    new_output_lines.append("")

    if palette.cursor_background_color or palette.cursor_foreground_color:
        new_output_lines.append("[colors.cursor]")
        if palette.cursor_foreground_color:
            new_output_lines.append(f'text = "{palette.cursor_foreground_color}"')
        if palette.cursor_background_color:
            new_output_lines.append(f'cursor = "{palette.cursor_background_color}"')
        new_output_lines.append("")

    new_output_lines.append("[colors.normal]")
    for k, v in alacritty_colors_norm:
        new_output_lines.append(f'{k} = "{v}"')
    new_output_lines.append("")

    new_output_lines.append("[colors.bright]")
    for k, v in alacritty_colors_bright:
        new_output_lines.append(f'{k} = "{v}"')
    new_output_lines.append("")

    # Add Cursor
    new_output_lines.append("[cursor]")
    new_output_lines.append(f'style = {{ shape = "{c_shape}", blinking = "{c_blink}" }}')
    new_output_lines.append("")

    # Add Font if custom
    if not palette.use_system_font and palette.font:
        fam, size = _parse_pango_font(palette.font)
        new_output_lines.append("[font]")
        new_output_lines.append(f"size = {size}")
        new_output_lines.append("")
        new_output_lines.append("[font.normal]")
        new_output_lines.append(f'family = "{fam}"')
        new_output_lines.append("")

    final_toml = "\n".join(new_output_lines).strip() + "\n"
    success = _safe_write_file_with_host_fallback(config_path, final_toml)
    if not success:
        logger.warning("Failed writing Alacritty config to %s", config_path)
    return success


def read_current_alacritty_palette(
    config_path: Path | None = None,
) -> TerminalPalette | None:
    """Read active palette and preferences from Alacritty config file (alacritty.toml).

    Args:
        config_path: Optional custom Path to alacritty.toml.

    Returns:
        TerminalPalette if config exists and contains styling, None otherwise.
    """
    if config_path is None:
        config_path = Path.home() / ".config/alacritty/alacritty.toml"

    content = _safe_read_file_with_host_fallback(config_path)
    if not content or not content.strip():
        return None

    current_sec = ""
    kv_by_sec: dict[str, dict[str, str]] = {}
    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("#"):
            continue
        if trimmed.startswith("[") and trimmed.endswith("]") and not trimmed.startswith("[["):
            current_sec = trimmed[1:-1].strip()
        elif "=" in trimmed:
            k, _, v = trimmed.partition("=")
            key = k.strip()
            val = v.strip().strip("'\"")
            kv_by_sec.setdefault(current_sec, {})[key] = val

    prim = kv_by_sec.get("colors.primary", {})
    bg = prim.get("background", "#1e1e2e")
    fg = prim.get("foreground", "#cdd6f4")

    norm = kv_by_sec.get("colors.normal", {})
    bright = kv_by_sec.get("colors.bright", {})
    color_keys = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]

    pal = list(DEFAULT_ANSI_PALETTE)
    for idx, name in enumerate(color_keys):
        if name in norm:
            pal[idx] = norm[name]
        if name in bright:
            pal[idx + 8] = bright[name]

    opacity_val = kv_by_sec.get("window", {}).get("opacity")
    use_trans = False
    trans_pct = 0
    if opacity_val:
        try:
            op = float(opacity_val)
            if op < 0.999:
                use_trans = True
                trans_pct = round((1.0 - op) * 100)
        except ValueError:
            pass

    font_fam = kv_by_sec.get("font.normal", {}).get("family", "")
    font_sz = kv_by_sec.get("font", {}).get("size", "")
    font_str = f"{font_fam} {font_sz}".strip() if font_fam else "Monospace 11"
    use_sys_font = not bool(font_fam)

    cursor_style = kv_by_sec.get("cursor", {}).get("style", "")
    c_shape = "block"
    c_blink = "system"
    if "Beam" in cursor_style:
        c_shape = "ibeam"
    elif "Underline" in cursor_style:
        c_shape = "underline"

    if "On" in cursor_style:
        c_blink = "on"
    elif "Off" in cursor_style:
        c_blink = "off"

    return TerminalPalette(
        name="Alacritty",
        foreground_color=fg,
        background_color=bg,
        palette=pal,
        use_system_font=use_sys_font,
        font=font_str,
        cursor_shape=c_shape,
        cursor_blink_mode=c_blink,
        use_transparent_background=use_trans,
        background_transparency_percent=trans_pct,
    )


def apply_palette_to_kitty(
    palette: TerminalPalette,
    config_path: Path | None = None,
) -> bool:
    """Apply a TerminalPalette to Kitty configuration (kitty.conf).

    Args:
        palette: TerminalPalette containing ANSI colors, fonts, opacity.
        config_path: Optional custom Path to kitty.conf.

    Returns:
        True if applied successfully, False otherwise.
    """
    if config_path is None:
        config_path = Path.home() / ".config/kitty/kitty.conf"

    opacity = (
        max(0.0, min(1.0, 1.0 - (palette.background_transparency_percent / 100.0)))
        if palette.use_transparent_background
        else 1.0
    )

    c_shape = "block"
    if palette.cursor_shape == "ibeam":
        c_shape = "beam"
    elif palette.cursor_shape == "underline":
        c_shape = "underline"

    c_blink = "-1"
    if palette.cursor_blink_mode == "off":
        c_blink = "0"
    elif palette.cursor_blink_mode == "on":
        c_blink = "0.5"

    existing_content = _safe_read_file_with_host_fallback(config_path) or ""
    managed_keys = {
        "foreground",
        "background",
        "background_opacity",
        "cursor",
        "cursor_text_color",
        "cursor_shape",
        "cursor_blink_interval",
    }
    for i in range(16):
        managed_keys.add(f"color{i}")
    if not palette.use_system_font and palette.font:
        managed_keys.add("font_family")
        managed_keys.add("font_size")

    kept_lines: list[str] = []
    for line in existing_content.splitlines():
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#"):
            first_word = trimmed.split()[0]
            if first_word in managed_keys:
                continue
        kept_lines.append(line)

    new_lines: list[str] = [
        "# Gnome Theme Manager Managed Colors",
        f"foreground {palette.foreground_color}",
        f"background {palette.background_color}",
        f"background_opacity {opacity:.2f}",
        f"cursor {palette.cursor_background_color or palette.foreground_color}",
        f"cursor_text_color {palette.cursor_foreground_color or palette.background_color}",
        f"cursor_shape {c_shape}",
        f"cursor_blink_interval {c_blink}",
    ]
    for idx, col in enumerate(palette.palette[:16]):
        new_lines.append(f"color{idx} {col}")

    if not palette.use_system_font and palette.font:
        fam, size = _parse_pango_font(palette.font)
        new_lines.append(f"font_family {fam}")
        new_lines.append(f"font_size {size}")

    combined = "\n".join(kept_lines).rstrip() + "\n\n" + "\n".join(new_lines) + "\n"
    success = _safe_write_file_with_host_fallback(config_path, combined)

    # Hot reload running kitty instances via SIGUSR1
    try:
        subprocess.run(
            ["pkill", "-SIGUSR1", "-x", "kitty"],
            capture_output=True,
            timeout=2,
            check=False,
        )
    except Exception:
        pass
    if shutil.which("flatpak-spawn"):
        try:
            subprocess.run(
                ["flatpak-spawn", "--host", "pkill", "-SIGUSR1", "-x", "kitty"],
                capture_output=True,
                timeout=2,
                check=False,
            )
        except Exception:
            pass

    return success


def read_current_kitty_palette(
    config_path: Path | None = None,
) -> TerminalPalette | None:
    """Read active palette and preferences from Kitty config file (kitty.conf).

    Args:
        config_path: Optional custom Path to kitty.conf.

    Returns:
        TerminalPalette if config exists and contains styling, None otherwise.
    """
    if config_path is None:
        config_path = Path.home() / ".config/kitty/kitty.conf"

    content = _safe_read_file_with_host_fallback(config_path)
    if not content or not content.strip():
        return None

    kv: dict[str, str] = {}
    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#"):
            parts = trimmed.split(None, 1)
            if len(parts) == 2:
                kv[parts[0]] = parts[1].strip()

    if not any(k in kv for k in ("foreground", "background", "color0")):
        return None

    fg = kv.get("foreground", "#cdd6f4")
    bg = kv.get("background", "#1e1e2e")
    pal = list(DEFAULT_ANSI_PALETTE)
    for i in range(16):
        ck = f"color{i}"
        if ck in kv:
            pal[i] = kv[ck]

    opacity_val = kv.get("background_opacity")
    use_trans = False
    trans_pct = 0
    if opacity_val:
        try:
            op = float(opacity_val)
            if op < 0.999:
                use_trans = True
                trans_pct = round((1.0 - op) * 100)
        except ValueError:
            pass

    font_fam = kv.get("font_family", "")
    font_sz = kv.get("font_size", "")
    font_str = f"{font_fam} {font_sz}".strip() if font_fam else "Monospace 11"
    use_sys_font = not bool(font_fam)

    c_shape_raw = kv.get("cursor_shape", "block")
    c_shape = "block"
    if c_shape_raw == "beam":
        c_shape = "ibeam"
    elif c_shape_raw == "underline":
        c_shape = "underline"

    c_blink_raw = kv.get("cursor_blink_interval", "-1")
    c_blink = "system"
    if c_blink_raw == "0":
        c_blink = "off"
    elif c_blink_raw not in ("-1", "0"):
        c_blink = "on"

    return TerminalPalette(
        name="Kitty",
        foreground_color=fg,
        background_color=bg,
        palette=pal,
        use_system_font=use_sys_font,
        font=font_str,
        cursor_shape=c_shape,
        cursor_blink_mode=c_blink,
        use_transparent_background=use_trans,
        background_transparency_percent=trans_pct,
    )
