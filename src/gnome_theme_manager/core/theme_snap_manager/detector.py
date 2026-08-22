# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme detector for verifying compatibility with the Snap ecosystem."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("gnome_theme_manager.core.theme_snap_manager.detector")


class ThemeDetector:
    """Detects whether a theme is already available natively in gtk-common-themes."""

    DEFAULT_THEMES_PATH = Path("/snap/gtk-common-themes/current/share/themes")
    DEFAULT_ICONS_PATH = Path("/snap/gtk-common-themes/current/share/icons")
    DEFAULT_SOUNDS_PATH = Path("/snap/gtk-common-themes/current/share/sounds")

    def __init__(
        self,
        themes_path: Path | None = None,
        icons_path: Path | None = None,
        sounds_path: Path | None = None,
    ) -> None:
        """Initialize ThemeDetector with custom or default gtk-common-themes paths.

        Args:
            themes_path: Path to share/themes directory in gtk-common-themes.
            icons_path: Path to share/icons directory in gtk-common-themes.
            sounds_path: Path to share/sounds directory in gtk-common-themes.
        """
        self.themes_path = themes_path or self.DEFAULT_THEMES_PATH
        self.icons_path = icons_path or self.DEFAULT_ICONS_PATH
        self.sounds_path = sounds_path or self.DEFAULT_SOUNDS_PATH

    def check_theme_compatibility(self, theme_name: str) -> tuple[bool, list[str]]:
        """Check if a theme exists in gtk-common-themes and determine available slots.

        Args:
            theme_name: Name of the theme to inspect.

        Returns:
            Tuple of (is_compatible, available_slots).
        """
        if not theme_name or not theme_name.strip():
            return False, []

        clean_name = theme_name.strip()
        available_slots: list[str] = []

        # Check theme in share/themes
        theme_dir = self.themes_path / clean_name
        if theme_dir.is_dir():
            available_slots.append("gtk-3-themes")

        # Check icons in share/icons
        icon_dir = self.icons_path / clean_name
        if icon_dir.is_dir():
            available_slots.append("icon-themes")

        # Check sounds in share/sounds
        sound_dir = self.sounds_path / clean_name
        if sound_dir.is_dir():
            available_slots.append("sound-themes")

        is_compatible = len(available_slots) > 0
        logger.debug(
            "Theme '%s' compatibility check: compatible=%s, slots=%s",
            clean_name,
            is_compatible,
            available_slots,
        )
        return is_compatible, available_slots
