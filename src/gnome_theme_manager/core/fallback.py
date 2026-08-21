# SPDX-License-Identifier: GPL-3.0-or-later

"""Fallback themes and cross-target availability checking module.

This module provides:
- `FallbackConfig`: Data structure representing chosen fallback themes for
  GTK3, GTK4, GNOME Shell, Icons, and Cursors.
- `ThemeAvailabilityChecker`: Utility to inspect availability across targets
  ('host', 'snap', 'flatpak').
- `FallbackManager`: Manager for reading, saving, and resolving default and user
  configured fallbacks in `~/.local/state/gnome-theme-manager/fallbacks.json`.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import FALLBACKS_FILE
from .gsettings import GSettingsClient
from .models import Theme, ThemeType
from .sandbox_bridge import KNOWN_SNAP_COMMON_THEMES
from .scanner import ThemeScanner

logger = logging.getLogger("gnome_theme_manager.core.fallback")


@dataclass
class FallbackConfig:
    """Configuration mapping theme components to their user-selected fallback themes."""

    gtk3: str = "Adwaita"
    gtk4: str = "Adwaita"
    shell: str = "Adwaita"
    icons: str = "Adwaita"
    cursors: str = "Adwaita"

    def to_dict(self) -> dict[str, str]:
        """Convert fallback config to dictionary."""
        return {
            "gtk3": self.gtk3,
            "gtk4": self.gtk4,
            "shell": self.shell,
            "icons": self.icons,
            "cursors": self.cursors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FallbackConfig":
        """Construct FallbackConfig from dictionary with sensible defaults."""
        return cls(
            gtk3=str(data.get("gtk3", "Adwaita")),
            gtk4=str(data.get("gtk4", "Adwaita")),
            shell=str(data.get("shell", "Adwaita")),
            icons=str(data.get("icons", "Adwaita")),
            cursors=str(data.get("cursors", "Adwaita")),
        )


class ThemeAvailabilityChecker:
    """Checks theme availability on Host, Snap, and Flatpak targets."""

    def __init__(self, scanner: ThemeScanner | None = None) -> None:
        """Initialize ThemeAvailabilityChecker.

        Args:
            scanner: Optional ThemeScanner instance.
        """
        self._scanner = scanner or ThemeScanner()

    def check(
        self,
        theme_name: str,
        theme_type: ThemeType,
        target: str = "host",
        theme_obj: Theme | None = None,
    ) -> bool:
        """Check if a theme is available for a specific target.

        Args:
            theme_name: Name of theme.
            theme_type: Component category.
            target: Target environment ('host', 'snap', 'flatpak').
            theme_obj: Optional pre-discovered Theme instance to avoid filesystem scans.

        Returns:
            True if available on target, False otherwise.
        """
        if not theme_name or not theme_name.strip():
            return False

        normalized_target = target.strip().lower()

        if normalized_target == "host":
            if theme_obj is not None:
                return theme_obj.exists
            found = self._scanner.find_theme(theme_name, theme_type)
            return found is not None and found.exists

        if normalized_target == "snap":
            # For Snap, check if theme is known in snap common themes or installed snap packages
            norm_name = theme_name.strip().lower()
            if norm_name in KNOWN_SNAP_COMMON_THEMES:
                return True
            # Inspect snap theme directories if available
            snap_dirs = [
                Path("/snap/gtk-common-themes/current/share/themes"),
                Path("/snap/gtk-common-themes/current/share/icons"),
                Path(f"/snap/gtk-theme-{norm_name}/current/usr/share/themes"),
                Path(f"/snap/icon-theme-{norm_name}/current/usr/share/icons"),
            ]
            for sdir in snap_dirs:
                if (sdir / theme_name).is_dir() or (sdir / norm_name).is_dir():
                    return True
            return False

        if normalized_target == "flatpak":
            # For Flatpak, user/system filesystem overrides expose host themes
            if theme_obj is not None:
                return theme_obj.exists
            found = self._scanner.find_theme(theme_name, theme_type)
            return found is not None and found.exists

        return False

    def check_all_targets(
        self, theme_name: str, theme_type: ThemeType, theme_obj: Theme | None = None
    ) -> bool:
        """Check if a theme is available across all supported targets (Host, Snap, Flatpak).

        Args:
            theme_name: Name of theme.
            theme_type: Component category.
            theme_obj: Optional pre-discovered Theme instance to avoid filesystem scans.

        Returns:
            True if available on Host, Snap, and Flatpak.
        """
        return (
            self.check(theme_name, theme_type, target="host", theme_obj=theme_obj)
            and self.check(theme_name, theme_type, target="snap", theme_obj=theme_obj)
            and self.check(theme_name, theme_type, target="flatpak", theme_obj=theme_obj)
        )

    def derive_available_theme(
        self,
        theme_name: str,
        theme_type: ThemeType,
        target: str = "snap",
        fallback_theme: str | None = None,
    ) -> str:
        """Derive an available theme name for the specified target.

        If `theme_name` is already available on the target, returns `theme_name`.
        Otherwise, attempts to derive a valid parent name (e.g. 'Colloid-Dark' for 'Colloid-Dark-Custom'),
        and if that is also unavailable, returns `fallback_theme` or 'Adwaita' / 'Yaru'.
        """
        if self.check(theme_name, theme_type, target=target):
            return theme_name

        # Try stripping suffixes like '-Custom', '-gtk4', '-shell', ' (Fork)'
        cleaned = theme_name
        for suffix in ("-Custom", "-custom", "-gtk4", "-shell", " (Fork)", "-dark", "-Dark", "-light", "-Light"):
            if cleaned.endswith(suffix):
                candidate = cleaned[: -len(suffix)]
                if candidate and self.check(candidate, theme_type, target=target):
                    return candidate

        # Try matching base prefix in available snap themes
        if target == "snap":
            norm = theme_name.lower()
            if "colloid" in norm:
                colloid_candidate = "Colloid-Dark" if "dark" in norm else "Colloid"
                if self.check(colloid_candidate, theme_type, target="snap"):
                    return colloid_candidate
            if "yaru" in norm:
                yaru_candidate = "Yaru-dark" if "dark" in norm else "Yaru"
                return yaru_candidate
            if "adwaita" in norm:
                return "Adwaita-dark" if "dark" in norm else "Adwaita"

        if fallback_theme and self.check(fallback_theme, theme_type, target=target):
            return fallback_theme

        return "Yaru-dark" if "dark" in theme_name.lower() else "Yaru"


class FallbackManager:
    """Manages universal fallback themes for host and sandboxed environments."""

    def __init__(
        self,
        config_file: Path | None = None,
        scanner: ThemeScanner | None = None,
        gsettings: GSettingsClient | None = None,
        gsettings_client: GSettingsClient | None = None,
    ) -> None:
        """Initialize FallbackManager.

        Args:
            config_file: Storage path for fallbacks.json (default: ~/.local/state/gnome-theme-manager/fallbacks.json).
            scanner: Optional ThemeScanner instance.
            gsettings: Optional GSettingsClient instance.
            gsettings_client: Compatibility alias for GSettingsClient.
        """
        self.config_file = config_file or FALLBACKS_FILE
        self._scanner = scanner or ThemeScanner()
        self._gsettings = gsettings if gsettings is not None else gsettings_client
        self._availability_checker = ThemeAvailabilityChecker(self._scanner)

    @property
    def availability_checker(self) -> ThemeAvailabilityChecker:
        """Return theme availability checker."""
        return self._availability_checker

    def get_config(self) -> FallbackConfig:
        """Load current fallback configuration or generate default if absent."""
        if not self.config_file.is_file():
            default_config = self._detect_default_fallbacks()
            self.save_config(default_config)
            return default_config

        try:
            content = self.config_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return FallbackConfig.from_dict(data)
        except Exception as err:
            logger.warning("Failed to parse fallbacks.json, recreating defaults: %s", err)
            default_config = self._detect_default_fallbacks()
            self.save_config(default_config)
            return default_config

    def save_config(self, config: FallbackConfig) -> None:
        """Persist fallback configuration to JSON file atomically."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.config_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2)
            temp_file.replace(self.config_file)
            logger.debug("Saved fallback configuration to %s", self.config_file)
        except Exception as err:
            logger.error("Failed to save fallbacks.json: %s", err)

    def _detect_default_fallbacks(self) -> FallbackConfig:
        """Detect initial fallback values from active system settings or standard defaults."""
        detected_gtk = "Adwaita"
        detected_icon = "Adwaita"
        detected_cursor = "Adwaita"
        detected_shell = "Adwaita"

        if self._gsettings is not None:
            try:
                current = self._gsettings.get_current()
                if current.gtk_theme:
                    detected_gtk = current.gtk_theme
                if current.icon_theme:
                    detected_icon = current.icon_theme
                if current.cursor_theme:
                    detected_cursor = current.cursor_theme
                if current.shell_theme:
                    detected_shell = current.shell_theme
            except Exception as err:
                logger.debug("Could not read GSettings for default fallbacks: %s", err)

        return FallbackConfig(
            gtk3=detected_gtk,
            gtk4=detected_gtk,
            shell=detected_shell,
            icons=detected_icon,
            cursors=detected_cursor,
        )

    def get_available_fallback_themes(self, theme_type: ThemeType) -> list[str]:
        """List themes of given type that are available across all targets (Host, Snap, Flatpak).

        Args:
            theme_type: Component category.

        Returns:
            Sorted list of theme names available universally.
        """
        if theme_type == ThemeType.GTK:
            scanned = self._scanner.scan_gtk_themes()
        elif theme_type == ThemeType.ICON:
            scanned = self._scanner.scan_icon_themes()
        elif theme_type == ThemeType.CURSOR:
            scanned = self._scanner.scan_cursor_themes()
        elif theme_type == ThemeType.SHELL:
            scanned = self._scanner.scan_shell_themes()
        else:
            scanned = self._scanner.scan_all()

        available_names: list[str] = []
        for t in scanned:
            if (
                self._availability_checker.check_all_targets(t.name, t.theme_type, theme_obj=t)
                and t.name not in available_names
            ):
                available_names.append(t.name)

        # Always ensure standard system fallbacks are represented if found
        if not available_names:
            for fallback_candidate in ("Adwaita", "Yaru"):
                if self._scanner.find_theme(fallback_candidate, theme_type):
                    available_names.append(fallback_candidate)

        return sorted(available_names, key=str.casefold)

    def resolve_fallback_for_component(self, theme_type: ThemeType) -> str:
        """Resolve configured fallback theme name for specific component.

        Args:
            theme_type: Component category.

        Returns:
            Theme name to use as fallback.
        """
        cfg = self.get_config()
        if theme_type == ThemeType.GTK:
            return cfg.gtk3 or "Adwaita"
        if theme_type == ThemeType.ICON:
            return cfg.icons or "Adwaita"
        if theme_type == ThemeType.CURSOR:
            return cfg.cursors or "Adwaita"
        if theme_type == ThemeType.SHELL:
            return cfg.shell or "Adwaita"
        return "Adwaita"
