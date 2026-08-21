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
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .css_extractor import ExtractedColors

logger = logging.getLogger("gnome_theme_manager.core.terminal_palette")

# Try importing Gio safely (consistent with core/gsettings.py)
try:
    import gi  # type: ignore[import-untyped]

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio  # type: ignore[import-untyped]

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


def list_gnome_terminal_profiles() -> list[TerminalProfileSummary]:
    """List all available GNOME Terminal profiles and default status.

    Returns:
        List of TerminalProfileSummary items.
    """
    if not _GIO_AVAILABLE or Gio is None:
        return []

    try:
        profiles_settings = Gio.Settings(schema_id="org.gnome.Terminal.ProfilesList")
        default_id = profiles_settings.get_string("default")
        profile_ids = list(profiles_settings.get_strv("list"))

        summaries: list[TerminalProfileSummary] = []
        for pid in profile_ids:
            path = f"/org/gnome/terminal/legacy/profiles:/:{pid}/"
            try:
                prof_settings = Gio.Settings.new_with_path(
                    "org.gnome.Terminal.Legacy.Profile", path
                )
                visible_name = prof_settings.get_string("visible-name") or "Unnamed Profile"
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
    if not _GIO_AVAILABLE or Gio is None:
        return None

    try:
        new_id = str(uuid.uuid4())
        profiles_settings = Gio.Settings(schema_id="org.gnome.Terminal.ProfilesList")
        current_list = list(profiles_settings.get_strv("list"))

        if new_id not in current_list:
            current_list.append(new_id)
            profiles_settings.set_strv("list", current_list)

        path = f"/org/gnome/terminal/legacy/profiles:/:{new_id}/"
        prof_settings = Gio.Settings.new_with_path(
            "org.gnome.Terminal.Legacy.Profile", path
        )
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
    if not _GIO_AVAILABLE or Gio is None:
        return False

    try:
        profiles_settings = Gio.Settings(schema_id="org.gnome.Terminal.ProfilesList")
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
    if not _GIO_AVAILABLE or Gio is None:
        return False

    try:
        profiles_settings = Gio.Settings(schema_id="org.gnome.Terminal.ProfilesList")
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
    if not _GIO_AVAILABLE or Gio is None:
        return None

    try:
        if profile_id is None:
            profiles_settings = Gio.Settings(schema_id="org.gnome.Terminal.ProfilesList")
            profile_id = profiles_settings.get_string("default")

        if not profile_id:
            return None

        path = f"/org/gnome/terminal/legacy/profiles:/:{profile_id}/"
        profile = Gio.Settings.new_with_path(
            "org.gnome.Terminal.Legacy.Profile",
            path,
        )

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
    if not _GIO_AVAILABLE or Gio is None:
        logger.warning("Gio is unavailable; cannot apply GNOME Terminal palette")
        return False

    try:
        if profile_id is None:
            # Query default profile UUID from legacy settings
            profiles_settings = Gio.Settings(schema_id="org.gnome.Terminal.ProfilesList")
            profile_id = profiles_settings.get_string("default")

        if not profile_id:
            logger.warning("No GNOME Terminal profile ID found")
            return False

        path = f"/org/gnome/terminal/legacy/profiles:/:{profile_id}/"
        profile = Gio.Settings.new_with_path(
            "org.gnome.Terminal.Legacy.Profile",
            path,
        )

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
