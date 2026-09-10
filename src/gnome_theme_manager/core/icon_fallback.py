# SPDX-License-Identifier: GPL-3.0-or-later

"""Multi-OS Cascading Icon Fallback System.

Ensures that user interface icons render reliably across diverse Linux distributions
(Ubuntu, Fedora, Arch, openSUSE, etc.) and GTK icon themes (Adwaita, Yaru, Breeze, Papirus).

Implements a 3-level cascading fallback resolution:
1. Theme-specific icon (active or specified theme)
2. System default icon (freedesktop / Adwaita / hicolor fallback chains)
3. Bundled application icon (data/icons/ embedded assets)
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def find_bundled_icon_dirs() -> list[Path]:
    """Discover all existing bundled icon directories across development, flatpak, and system installs."""
    candidates: list[Path | None] = []

    # 1. Source tree / Git checkout
    try:
        candidates.append(Path(__file__).resolve().parents[3] / "data" / "icons")
    except IndexError:
        pass

    # 2. AppImage runtime
    appdir = os.environ.get("APPDIR")
    if appdir:
        candidates.extend(
            [
                Path(appdir) / "usr" / "share" / "icons",
                Path(appdir) / "data" / "icons",
                Path(appdir) / "data" / "icons" / "hicolor",
            ]
        )

    # 3. Flatpak runtime
    candidates.extend(
        [
            Path("/app/share/gnome-theme-manager/data/icons"),
            Path("/app/share/icons"),
            Path("/app/share/icons/hicolor"),
        ]
    )

    # 4. sys.prefix (pip, pipx, virtualenvs, local prefix)
    candidates.extend(
        [
            Path(sys.prefix) / "share" / "gnome-theme-manager" / "data" / "icons",
            Path(sys.prefix) / "share" / "icons",
            Path(sys.prefix) / "share" / "icons" / "hicolor",
        ]
    )

    # 5. System directories (/usr, /usr/local)
    candidates.extend(
        [
            Path("/usr/share/gnome-theme-manager/data/icons"),
            Path("/usr/local/share/gnome-theme-manager/data/icons"),
        ]
    )

    found: list[Path] = []
    for c in candidates:
        if c is not None and c.is_dir() and c not in found:
            found.append(c)
    return found


def _get_default_bundled_icons_dir() -> Path:
    dirs = find_bundled_icon_dirs()
    if dirs:
        return dirs[0]
    try:
        return Path(__file__).resolve().parents[3] / "data" / "icons"
    except IndexError:
        return Path("/usr/share/icons")


# Base path to application bundled icons
BUNDLED_ICONS_DIR: Path = _get_default_bundled_icons_dir()

# Standard icon directories checked for system themes
STANDARD_SYSTEM_ICON_DIRS: tuple[Path, ...] = (
    Path.home() / ".local" / "share" / "icons",
    Path.home() / ".icons",
    Path("/run/host/share/icons"),
    Path("/run/host/usr/share/icons"),
    Path("/usr/local/share/icons"),
    Path("/usr/share/icons"),
    Path("/app/share/icons"),
)

# Known icon names that frequently fail or vary across Linux distributions,
# mapped to prioritized alternative freedesktop / system candidates.
ICON_FALLBACK_CHAINS: dict[str, tuple[str, ...]] = {
    # App brand / global presets icon: absent in Adwaita vanilla, Breeze, Papirus
    "app-logo-symbolic": (
        "preferences-desktop-appearance-symbolic",
        "applications-graphics-symbolic",
        "emblem-favorite-symbolic",
        "system-run-symbolic",
    ),
    # Cursors page: absent in Adwaita vanilla, present in Yaru
    "face-slightly-smiling-plus-symbolic": (
        "face-smile-symbolic",
        "face-plain-symbolic",
        "input-mouse-symbolic",
        "face-smile",
    ),
    # Store page: named differently on Fedora/openSUSE Adwaita
    "software-store-symbolic": (
        "system-software-install-symbolic",
        "org.gnome.Software-symbolic",
        "package-x-generic-symbolic",
        "system-software-install",
    ),
    # Sandbox / permissions page: variable across minimalist themes
    "changes-allow-symbolic": (
        "security-high-symbolic",
        "system-run-symbolic",
        "preferences-system-symbolic",
        "dialog-password-symbolic",
    ),
    # Header bar synchronizing: absent in Breeze and light icon themes
    "emblem-synchronizing-symbolic": (
        "view-refresh-symbolic",
        "emblem-synchronizing",
        "view-refresh",
    ),
    # Themes view: alternate freedesktop appearance name
    "preferences-desktop-theme-symbolic": (
        "preferences-desktop-appearance-symbolic",
        "style-symbolic",
        "applications-graphics-symbolic",
        "preferences-desktop-theme",
    ),
    # Fonts view: desktop fonts icon
    "preferences-desktop-font-symbolic": (
        "font-x-generic-symbolic",
        "preferences-desktop-font",
        "font-select-symbolic",
    ),
    # Terminal view: terminal emulator symbolic
    "utilities-terminal-symbolic": (
        "terminal-symbolic",
        "org.gnome.Terminal-symbolic",
        "utilities-terminal",
        "terminal",
    ),
    # GNOME Shell view: desktop place icon
    "user-desktop-symbolic": (
        "desktop-symbolic",
        "user-home-symbolic",
        "user-desktop",
    ),
    # Extensions view: addon / plugin symbolic
    "application-x-addon-symbolic": (
        "emblem-system-symbolic",
        "application-x-addon",
        "emblem-generic-symbolic",
    ),
    # Flatpak package / badge: absent on minimal installations without flatpak icons
    "flatpak-symbolic": (
        "application-x-executable-symbolic",
        "package-x-generic-symbolic",
        "application-x-executable",
    ),
    # Offline store / network error:
    "network-error-symbolic": (
        "dialog-error-symbolic",
        "network-offline-symbolic",
        "network-error",
    ),
    # Search symbolic:
    "system-search-symbolic": (
        "edit-find-symbolic",
        "system-search",
        "edit-find",
    ),
    # Starred / favorites symbolic (absent in vanilla Adwaita 46)
    "starred-symbolic": (
        "emblem-favorite-symbolic",
        "bookmark-new-symbolic",
        "starred",
    ),
    # Dark mode weather icon
    "weather-clear-night-symbolic": (
        "night-light-symbolic",
        "display-brightness-symbolic",
        "weather-clear-symbolic",
        "weather-clear",
    ),
    # Photos / Wallpaper emblem
    "emblem-photos-symbolic": (
        "image-x-generic-symbolic",
        "folder-pictures-symbolic",
        "applications-graphics-symbolic",
        "image-x-generic",
    ),
    # System monitor
    "utilities-system-monitor-symbolic": (
        "org.gnome.SystemMonitor-symbolic",
        "system-run-symbolic",
        "utilities-system-monitor",
    ),
    # System users
    "system-users-symbolic": (
        "avatar-default-symbolic",
        "user-info-symbolic",
        "user-home-symbolic",
        "contact-new-symbolic",
        "system-users",
    ),
    # Mouse / Cursors
    "input-mouse-symbolic": (
        "preferences-desktop-peripherals-symbolic",
        "input-touchpad-symbolic",
        "input-mouse",
    ),
    # Remote folder
    "folder-remote-symbolic": (
        "folder-symbolic",
        "network-server-symbolic",
        "folder",
    ),
    # Security
    "security-high-symbolic": (
        "changes-allow-symbolic",
        "dialog-password-symbolic",
        "dialog-information-symbolic",
        "security-high",
    ),
    # Dialogs & feedback
    "dialog-error-symbolic": (
        "dialog-error",
        "error-symbolic",
    ),
    "dialog-warning-symbolic": (
        "dialog-warning",
        "emblem-important-symbolic",
    ),
    "dialog-information-symbolic": (
        "dialog-information",
        "dialog-info-symbolic",
        "dialog-info",
    ),
    "emblem-ok-symbolic": (
        "object-select-symbolic",
        "emblem-default-symbolic",
        "emblem-ok",
    ),
    "edit-delete-symbolic": (
        "user-trash-symbolic",
        "edit-delete",
    ),
    "preferences-color-symbolic": (
        "applications-graphics-symbolic",
        "style-symbolic",
        "preferences-desktop-theme-symbolic",
    ),
    "view-refresh-symbolic": (
        "emblem-synchronizing-symbolic",
        "view-refresh",
    ),
    "edit-copy-symbolic": (
        "edit-copy",
        "edit-paste-symbolic",
    ),
    "web-browser-symbolic": (
        "applications-internet-symbolic",
        "web-browser",
        "applications-internet",
    ),
}


@dataclass(frozen=True)
class IconResolutionResult:
    """Represents the outcome of a cascading icon resolution."""

    requested_name: str
    resolved_name: str
    level: str  # "theme", "system", "bundled", or "generic"
    file_path: Path | None = None
    is_fallback: bool = False


class IconFallbackResolver:
    """Resolves icons using a 3-level cascade with diagnostic logging.

    Cascade order:
    1. Level 1 (Theme): Icon directly found in active or specified icon theme.
    2. Level 2 (System): Standard freedesktop / system default icon from fallback chain.
    3. Level 3 (Bundled): Guaranteed embedded asset from application data/icons.
    """

    def __init__(
        self,
        bundled_icons_dir: Path | None = None,
        system_icon_dirs: tuple[Path, ...] | None = None,
    ) -> None:
        """Initialize IconFallbackResolver.

        Args:
            bundled_icons_dir: Optional custom path to bundled icons directory.
            system_icon_dirs: Optional custom sequence of system icon search paths.
        """
        self.bundled_icons_dir: Path = bundled_icons_dir or BUNDLED_ICONS_DIR
        self.system_icon_dirs: tuple[Path, ...] = system_icon_dirs or STANDARD_SYSTEM_ICON_DIRS
        self._bundled_cache: dict[str, Path] | None = None

    def _get_bundled_icons_index(self) -> dict[str, Path]:
        """Index all available bundled SVG and PNG icons by icon name without extension."""
        if self._bundled_cache is not None:
            return self._bundled_cache

        index: dict[str, Path] = {}
        search_dirs: list[Path] = []
        if self.bundled_icons_dir.is_dir():
            search_dirs.append(self.bundled_icons_dir)
        for extra_dir in find_bundled_icon_dirs():
            if extra_dir not in search_dirs:
                search_dirs.append(extra_dir)

        for b_dir in search_dirs:
            if b_dir.is_dir():
                for file_path in b_dir.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in (".svg", ".png"):
                        stem = file_path.stem
                        if stem not in index:
                            index[stem] = file_path

        self._bundled_cache = index
        return index

    def _theme_has_icon_filesystem(self, theme_name: str, icon_name: str) -> bool:
        """Check if an icon exists in a theme directory on the filesystem."""
        for base_dir in self.system_icon_dirs:
            theme_dir = base_dir / theme_name
            if not theme_dir.is_dir():
                continue
            for ext in (".svg", ".png"):
                if any(theme_dir.rglob(f"{icon_name}{ext}")):
                    return True
        return False

    def _system_has_icon_filesystem(self, icon_name: str) -> bool:
        """Check if an icon exists in system default themes (Adwaita, hicolor, etc.)."""
        for default_theme in ("Adwaita", "hicolor", "gnome", "default"):
            if self._theme_has_icon_filesystem(default_theme, icon_name):
                return True
        for base_dir in self.system_icon_dirs:
            if not base_dir.is_dir():
                continue
            for ext in (".svg", ".png"):
                if any(base_dir.rglob(f"{icon_name}{ext}")):
                    return True
        return False

    def _check_icon_theme_gtk(self, icon_theme: Any, icon_name: str) -> bool:
        """Query Gtk.IconTheme instance safely for an icon."""
        try:
            if hasattr(icon_theme, "has_icon"):
                return bool(icon_theme.has_icon(icon_name))
        except Exception as exc:
            logger.debug("Error querying Gtk.IconTheme.has_icon(%s): %s", icon_name, exc)
        return False

    def resolve(
        self,
        icon_name: str,
        icon_theme: Any | None = None,
        theme_name: str | None = None,
    ) -> IconResolutionResult:
        """Resolve an icon using the 3-level cascading fallback strategy.

        Args:
            icon_name: The requested icon identifier (e.g. 'app-logo-symbolic').
            icon_theme: Optional Gtk.IconTheme instance.
            theme_name: Optional icon theme name (e.g. 'Nordzy', 'Yaru', 'Adwaita').

        Returns:
            IconResolutionResult containing resolved icon name, resolution level,
            optional file path, and whether a fallback was triggered.
        """
        clean_name = icon_name.strip()
        if not clean_name:
            return IconResolutionResult(
                requested_name="",
                resolved_name="image-missing",
                level="generic",
                is_fallback=True,
            )

        # ------------------------------------------------------------------
        # Level 1: Theme-specific icon (active theme or provided Gtk.IconTheme)
        # ------------------------------------------------------------------
        level_1_found = False
        if icon_theme is not None:
            level_1_found = self._check_icon_theme_gtk(icon_theme, clean_name)
        elif theme_name:
            level_1_found = self._theme_has_icon_filesystem(theme_name, clean_name)

        if level_1_found:
            return IconResolutionResult(
                requested_name=clean_name,
                resolved_name=clean_name,
                level="theme",
                is_fallback=False,
            )

        # ------------------------------------------------------------------
        # Level 2: System default icon (Adwaita / hicolor / standard freedesktop)
        # ------------------------------------------------------------------
        # First try the requested name in default system themes if theme wasn't default
        if icon_theme is None and self._system_has_icon_filesystem(clean_name):
            logger.debug(
                "Icon fallback activated (Level 2 - System): '%s' found in system default theme",
                clean_name,
            )
            return IconResolutionResult(
                requested_name=clean_name,
                resolved_name=clean_name,
                level="system",
                is_fallback=True,
            )

        # Try alternative candidates from fallback chain
        fallback_candidates = ICON_FALLBACK_CHAINS.get(clean_name, ())
        for cand in fallback_candidates:
            cand_found = False
            if icon_theme is not None:
                cand_found = self._check_icon_theme_gtk(icon_theme, cand)
            else:
                cand_found = self._system_has_icon_filesystem(cand)

            if cand_found:
                logger.debug(
                    "Icon fallback activated (Level 2 - System): '%s' resolved to '%s'",
                    clean_name,
                    cand,
                )
                return IconResolutionResult(
                    requested_name=clean_name,
                    resolved_name=cand,
                    level="system",
                    is_fallback=True,
                )

        # ------------------------------------------------------------------
        # Level 3: Bundled application icon (data/icons/ embedded assets)
        # ------------------------------------------------------------------
        bundled_index = self._get_bundled_icons_index()

        # Check if requested name exists directly in bundled assets
        if clean_name in bundled_index:
            bundled_path = bundled_index[clean_name]
            logger.debug(
                "Icon fallback activated (Level 3 - Bundled): '%s' resolved to bundled asset %s",
                clean_name,
                bundled_path,
            )
            return IconResolutionResult(
                requested_name=clean_name,
                resolved_name=clean_name,
                level="bundled",
                file_path=bundled_path,
                is_fallback=True,
            )

        # Check candidate names in bundled assets
        for cand in fallback_candidates:
            if cand in bundled_index:
                bundled_path = bundled_index[cand]
                logger.debug(
                    "Icon fallback activated (Level 3 - Bundled): '%s' resolved to candidate '%s' (%s)",
                    clean_name,
                    cand,
                    bundled_path,
                )
                return IconResolutionResult(
                    requested_name=clean_name,
                    resolved_name=cand,
                    level="bundled",
                    file_path=bundled_path,
                    is_fallback=True,
                )

        # ------------------------------------------------------------------
        # Level 4: Generic universal fallback (guaranteed to render)
        # ------------------------------------------------------------------
        emergency_candidates = (
            "io.github.granafilo.ThemeManager-symbolic",
            "dialog-information-symbolic",
            "image-missing",
        )
        for em_cand in emergency_candidates:
            if em_cand in bundled_index:
                bundled_path = bundled_index[em_cand]
                logger.debug(
                    "Icon fallback activated (Level 4 - Generic): '%s' resolved to emergency '%s' (%s)",
                    clean_name,
                    em_cand,
                    bundled_path,
                )
                return IconResolutionResult(
                    requested_name=clean_name,
                    resolved_name=em_cand,
                    level="generic",
                    file_path=bundled_path,
                    is_fallback=True,
                )

        logger.debug(
            "Icon fallback activated (Level 4 - Generic): '%s' defaulted to 'image-missing'",
            clean_name,
        )
        return IconResolutionResult(
            requested_name=clean_name,
            resolved_name="image-missing",
            level="generic",
            is_fallback=True,
        )


# Global singleton instance for convenient project-wide use
_DEFAULT_RESOLVER = IconFallbackResolver()


def resolve_icon(
    icon_name: str,
    icon_theme: Any | None = None,
    theme_name: str | None = None,
) -> IconResolutionResult:
    """Resolve an icon using the cascading fallback strategy with the default resolver.

    Args:
        icon_name: Name of the icon to resolve.
        icon_theme: Optional Gtk.IconTheme instance.
        theme_name: Optional theme name to check against.

    Returns:
        IconResolutionResult with resolved details and debug diagnostics.
    """
    return _DEFAULT_RESOLVER.resolve(icon_name, icon_theme=icon_theme, theme_name=theme_name)


def get_fallback_icon_name(
    icon_name: str,
    icon_theme: Any | None = None,
    theme_name: str | None = None,
) -> str:
    """Convenience helper returning directly the resolved icon string identifier.

    Args:
        icon_name: Name of the icon to resolve.
        icon_theme: Optional Gtk.IconTheme instance.
        theme_name: Optional theme name to check against.

    Returns:
        String identifier of the resolved icon.
    """
    return resolve_icon(icon_name, icon_theme=icon_theme, theme_name=theme_name).resolved_name


__all__ = [
    "BUNDLED_ICONS_DIR",
    "ICON_FALLBACK_CHAINS",
    "STANDARD_SYSTEM_ICON_DIRS",
    "IconFallbackResolver",
    "IconResolutionResult",
    "find_bundled_icon_dirs",
    "get_fallback_icon_name",
    "resolve_icon",
]
