# SPDX-License-Identifier: GPL-3.0-or-later

"""Terminal Color Palette Model and GNOME Terminal Integration (FASE 4 Task 4.4).

Provides functionality to:
1. Represent a 16-color ANSI terminal palette plus foreground and background colors (`TerminalPalette`).
2. Derive a balanced terminal palette directly from active GTK/CSS extracted colors (`derive_terminal_palette_from_colors`).
3. Export and import terminal palettes to/from JSON files for manual or automated integration.
4. Apply the palette to GNOME Terminal using relocatable GSettings schemas (`org.gnome.Terminal.Legacy.Profile`).
"""

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


def detect_installed_terminal() -> DetectedTerminal | None:
    """Detect available terminal emulator and its GSettings capabilities (Fix 1).

    Checks for supported terminals in order of preference:
    1. GNOME Terminal (gnome-terminal) -> org.gnome.Terminal.Legacy.Profile
    2. GNOME Console (kgx) -> org.gnome.Console
    3. Konsole (konsole) -> file-based configuration (no GSettings)
    4. XFCE Terminal (xfce4-terminal) -> org.xfce.terminal

    Returns:
        DetectedTerminal instance, or None if no supported terminal is installed.
    """
    # 1. GNOME Terminal
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

        name = profile.get_string("visible-name") or "GNOME Terminal"
        fg = profile.get_string("foreground-color") or "#d0d0d0"
        bg = profile.get_string("background-color") or "#241f31"
        raw_pal = profile.get_strv("palette")
        pal = list(raw_pal) if raw_pal and len(raw_pal) == 16 else list(DEFAULT_ANSI_PALETTE)

        use_sys_font = profile.get_boolean("use-system-font")
        font = profile.get_string("font") or "Monospace 11"
        c_shape = profile.get_string("cursor-shape") or "block"
        c_blink = profile.get_string("cursor-blink-mode") or "system"
        aud_bell = profile.get_boolean("audible-bell")
        use_trans = profile.get_boolean("use-transparent-background")
        trans_pct = profile.get_int("background-transparency-percent")

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

        profile.set_boolean("use-theme-colors", False)
        profile.set_string("foreground-color", palette.foreground_color)
        profile.set_string("background-color", palette.background_color)
        profile.set_strv("palette", palette.palette)
        if palette.bold_color:
            profile.set_string("bold-color", palette.bold_color)

        # Profile preferences
        profile.set_boolean("use-system-font", palette.use_system_font)
        if palette.font:
            profile.set_string("font", palette.font)
        profile.set_string("cursor-shape", palette.cursor_shape)
        profile.set_string("cursor-blink-mode", palette.cursor_blink_mode)
        profile.set_boolean("audible-bell", palette.audible_bell)
        profile.set_boolean("use-transparent-background", palette.use_transparent_background)
        profile.set_int("background-transparency-percent", palette.background_transparency_percent)

        return True
    except Exception as err:
        logger.warning("Failed to apply palette to GNOME Terminal: %s", err)
        return False
