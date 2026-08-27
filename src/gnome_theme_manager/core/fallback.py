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
        and if that is also unavailable, dynamically discovers an available system theme.
        """
        if self.check(theme_name, theme_type, target=target):
            return theme_name

        # Try stripping suffixes like '-Custom', '-gtk4', '-shell', ' (Fork)'
        cleaned = theme_name
        for suffix in (
            "-Custom",
            "-custom",
            "-gtk4",
            "-shell",
            " (Fork)",
            "-dark",
            "-Dark",
            "-light",
            "-Light",
        ):
            if cleaned.endswith(suffix):
                candidate = cleaned[: -len(suffix)]
                if candidate and self.check(candidate, theme_type, target=target):
                    return candidate

        # Check explicitly provided fallback theme
        if fallback_theme and self.check(fallback_theme, theme_type, target=target):
            return fallback_theme

        # Dynamically discover an available theme on target from scanned system themes
        is_dark_requested = "dark" in theme_name.lower()
        scanned = self._scanner.scan_all()
        matching_variant: str | None = None
        first_valid: str | None = None

        for t in scanned:
            if (
                t.theme_type == theme_type
                and not t.invalid
                and self.check(t.name, theme_type, target=target)
            ):
                if ("dark" in t.name.lower()) == is_dark_requested and matching_variant is None:
                    matching_variant = t.name
                if first_valid is None:
                    first_valid = t.name

        if matching_variant:
            return matching_variant
        if first_valid:
            return first_valid

        # Known common system fallback candidates dynamically checked
        for candidate in ("Yaru-dark", "Yaru", "Adwaita-dark", "Adwaita"):
            if self.check(candidate, theme_type, target=target):
                return candidate

        return fallback_theme or theme_name


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
        """Detect initial fallback values from active system settings or dynamically discovered themes."""
        detected: dict[str, str] = {
            "gtk3": "",
            "gtk4": "",
            "shell": "",
            "icons": "",
            "cursors": "",
        }

        if self._gsettings is not None:
            try:
                current = self._gsettings.get_current()
                if current.gtk_theme:
                    detected["gtk3"] = current.gtk_theme
                    detected["gtk4"] = current.gtk_theme
                if current.icon_theme:
                    detected["icons"] = current.icon_theme
                if current.cursor_theme:
                    detected["cursors"] = current.cursor_theme
                if current.shell_theme:
                    detected["shell"] = current.shell_theme
            except Exception as err:
                logger.debug("Could not read GSettings for default fallbacks: %s", err)

        # For any missing or unverified component, dynamically find first valid system theme
        mapping = {
            "gtk3": ThemeType.GTK,
            "gtk4": ThemeType.GTK,
            "shell": ThemeType.SHELL,
            "icons": ThemeType.ICON,
            "cursors": ThemeType.CURSOR,
        }
        for key, theme_type in mapping.items():
            val = detected[key]
            if not val or not self._scanner.find_theme(val, theme_type):
                available = self.get_available_fallback_themes(theme_type)
                if available:
                    detected[key] = available[0]
                else:
                    for t in self._scanner._scan_themes_by_type(theme_type, user_only=False):
                        if not t.invalid:
                            detected[key] = t.name
                            break
                    if not detected[key]:
                        detected[key] = "Adwaita"

        return FallbackConfig(
            gtk3=detected["gtk3"],
            gtk4=detected["gtk4"],
            shell=detected["shell"],
            icons=detected["icons"],
            cursors=detected["cursors"],
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
            if t.invalid:
                continue
            if (
                self._availability_checker.check_all_targets(t.name, t.theme_type, theme_obj=t)
                and t.name not in available_names
            ):
                available_names.append(t.name)

        # If no universally available theme was found, dynamically include any valid system-level themes found
        if not available_names:
            for t in scanned:
                if not t.invalid and not t.is_user_level and t.name not in available_names:
                    available_names.append(t.name)

        return sorted(available_names, key=str.casefold)

    def resolve_fallback_for_component(self, theme_type: ThemeType) -> str:
        """Resolve configured fallback theme name for specific component.

        Args:
            theme_type: Component category.

        Returns:
            Theme name to use as fallback.
        """
        cfg = self.get_config()
        configured = ""
        if theme_type == ThemeType.GTK:
            configured = cfg.gtk3 or cfg.gtk4
        elif theme_type == ThemeType.ICON:
            configured = cfg.icons
        elif theme_type == ThemeType.CURSOR:
            configured = cfg.cursors
        elif theme_type == ThemeType.SHELL:
            configured = cfg.shell

        if configured:
            found = self._scanner.find_theme(configured, theme_type)
            if found and not found.invalid:
                return configured

        # If configured theme is missing on disk or invalid, find dynamic system fallback
        available = self.get_available_fallback_themes(theme_type)
        if available:
            return available[0]

        for t in self._scanner._scan_themes_by_type(theme_type, user_only=False):
            if not t.invalid:
                return t.name

        return configured or "Adwaita"
