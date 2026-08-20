# SPDX-License-Identifier: GPL-3.0-or-later

"""Save, load, and delete theme presets/profiles.

Presets store full snapshots of desktop preferences
(GTK theme, icons, cursors, GNOME Shell, and color scheme) in JSON format
within the user configuration directory (~/.config/gnome-theme-manager/presets/).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import PRESETS_DIR
from .models import ThemeSet

logger = logging.getLogger("gnome_theme_manager.core")


class PresetManager:
    """Lifecycle manager for theme presets in GnomeThemeManager."""

    def __init__(self, presets_dir: Path | None = None) -> None:
        """Initialize preset manager.

        Args:
            presets_dir: Storage directory (default: ~/.config/gnome-theme-manager/presets).
        """
        self.presets_dir = (
            Path(presets_dir).expanduser() if presets_dir is not None else PRESETS_DIR.expanduser()
        )
        self.presets_file = self.presets_dir / "presets.json"

    def _sanitize_name(self, name: str) -> str:
        """Validate and sanitize preset name preventing path traversal and illegal names.

        Allows normal names including spaces, hyphens, underscores, accents, and
        Unicode characters. Explicitly rejects:
        - empty or whitespace-only strings;
        - path separators '/' and '\\';
        - directory traversal sequences '..';
        - names that are exactly '.' or '..';
        - ASCII control characters (0-31 and 127);
        - names longer than 255 characters.

        Args:
            name: Preset name to validate.

        Returns:
            Cleaned valid name without leading/trailing whitespace.

        Raises:
            ValueError: If name is empty, contains invalid characters, or path separators.
        """
        cleaned = name.strip()

        # Empty or whitespace-only name
        if not cleaned:
            raise ValueError("Preset name cannot be empty.")

        # Excess length (filesystem limit)
        if len(cleaned) > 255:
            raise ValueError(f"Preset name is too long ({len(cleaned)} characters, maximum 255).")

        # Path separators (prevent Path Traversal)
        if "/" in cleaned or "\\" in cleaned:
            raise ValueError(f"Invalid preset name: '{name}'. Path characters are not allowed.")

        # Directory traversal sequence
        if ".." in cleaned:
            raise ValueError(f"Invalid preset name: '{name}'. Path characters are not allowed.")

        # Reserved names
        if cleaned in (".", ".."):
            raise ValueError(f"Invalid preset name: '{name}'. Path characters are not allowed.")

        # ASCII control characters (0-31 and 127)
        if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
            raise ValueError(f"Preset name '{name}' contains disallowed control characters.")

        return cleaned

    def _read_presets_file(self) -> dict[str, Any]:
        """Read presets.json file and return dictionary."""
        if not self.presets_file.is_file():
            return {"presets": []}
        try:
            content = self.presets_file.read_text(encoding="utf-8")
            data: Any = json.loads(content)
            if isinstance(data, dict):
                return data
            return {"presets": []}
        except json.JSONDecodeError as err:
            logger.error("Corrupted or unreadable presets.json file: %s", err)
            raise ValueError(f"Corrupted or unreadable presets.json file: {err}") from err
        except Exception as err:
            logger.error("Error reading presets.json: %s", err)
            return {"presets": []}

    def _write_presets_file(self, data: dict[str, Any]) -> None:
        """Write dictionary to presets.json."""
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self.presets_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def save_preset(self, name: str, theme_set: ThemeSet, overwrite: bool = False) -> Path:
        """Save a ThemeSet configuration as a preset in presets.json."""
        preset_name = self._sanitize_name(name)
        if theme_set.is_empty():
            raise ValueError("Cannot save an empty preset.")

        data = self._read_presets_file()
        presets = data.get("presets", [])

        # Check duplicates
        existing_index = -1
        for i, p in enumerate(presets):
            if p.get("name") == preset_name:
                existing_index = i
                break

        if existing_index != -1 and not overwrite:
            raise FileExistsError(f"Preset '{preset_name}' already exists.")

        new_preset = {
            "name": preset_name,
            "components": {
                "gtk3": theme_set.gtk_theme,
                "gtk4": theme_set.gtk_theme,
                "shell": theme_set.shell_theme,
                "icons": theme_set.icon_theme,
                "cursors": theme_set.cursor_theme,
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if existing_index != -1:
            presets[existing_index] = new_preset
        else:
            presets.append(new_preset)

        data["presets"] = presets
        self._write_presets_file(data)
        logger.info("Preset saved successfully: '%s'", preset_name)
        return self.presets_file

    def load_preset(self, name: str) -> ThemeSet:
        """Load a preset from presets.json."""
        preset_name = self._sanitize_name(name)
        data = self._read_presets_file()
        presets = data.get("presets", [])

        for p in presets:
            if p.get("name") == preset_name:
                comp = p.get("components", {})
                return ThemeSet(
                    gtk_theme=comp.get("gtk3") or comp.get("gtk4"),
                    shell_theme=comp.get("shell"),
                    icon_theme=comp.get("icons"),
                    cursor_theme=comp.get("cursors"),
                )

        raise FileNotFoundError(f"Preset '{preset_name}' not found.")

    def list_presets(self) -> list[str]:
        """List all available preset names."""
        data = self._read_presets_file()
        presets = data.get("presets", [])
        names = [p.get("name") for p in presets if p.get("name")]
        names.sort(key=str.lower)
        return names

    def delete_preset(self, name: str) -> bool:
        """Delete a preset from presets.json."""
        preset_name = self._sanitize_name(name)
        data = self._read_presets_file()
        presets = data.get("presets", [])

        initial_len = len(presets)
        presets = [p for p in presets if p.get("name") != preset_name]

        if len(presets) == initial_len:
            raise FileNotFoundError(f"Preset '{preset_name}' does not exist.")

        data["presets"] = presets
        self._write_presets_file(data)
        logger.info("Preset deleted successfully: '%s'", preset_name)
        return True
