# SPDX-License-Identifier: GPL-3.0-or-later

"""Filesystem scanner module for detecting installed themes.

This module implements `ThemeScanner`, responsible for discovering
themes in standard GNOME directories (both user and system levels):
- Window widget controls (GTK 2/3/4)
- Icon packs
- Mouse cursor themes
- GNOME Shell themes (top bar, dock, and system menus)

Business rules applied:
1. Precedence: user themes (~/.local/share/...) take priority over system ones (/usr/share/...).
2. Hybrid folders: directories in 'icons/' containing both icons and cursors are registered for both types.
3. Shell themes: directories in 'themes/' containing 'gnome-shell/' are registered for ThemeType.SHELL.
"""

from pathlib import Path

from .constants import (
    get_system_icons_dirs,
    get_system_themes_dirs,
    get_user_icons_dirs,
    get_user_themes_dirs,
)
from .models import Theme, ThemeType


class ThemeScanner:
    """Scanner for detecting GTK themes, icon packs, cursor themes, and Shell themes on the filesystem.

    Scans provided or default GNOME directories and identifies valid themes
    using heuristics based on subdirectories and files ('gtk-3.0', 'cursors', 'gnome-shell', 'index.theme').
    """

    def __init__(
        self,
        user_theme_dirs: list[Path] | None = None,
        user_icon_dirs: list[Path] | None = None,
        system_theme_dirs: list[Path] | None = None,
        system_icon_dirs: list[Path] | None = None,
    ) -> None:
        """Initialize scanner with target paths.

        If custom paths are not provided, default XDG and legacy paths are dynamically resolved.

        Args:
            user_theme_dirs: List of user theme directories.
            user_icon_dirs: List of user icon/cursor directories.
            system_theme_dirs: List of system theme directories.
            system_icon_dirs: List of system icon/cursor directories.
        """
        self.user_theme_dirs = (
            user_theme_dirs if user_theme_dirs is not None else get_user_themes_dirs()
        )
        self.user_icon_dirs = (
            user_icon_dirs if user_icon_dirs is not None else get_user_icons_dirs()
        )
        self.system_theme_dirs = (
            system_theme_dirs if system_theme_dirs is not None else get_system_themes_dirs()
        )
        self.system_icon_dirs = (
            system_icon_dirs if system_icon_dirs is not None else get_system_icons_dirs()
        )

    # -------------------------------------------------------------------------
    # Public Scan Methods
    # -------------------------------------------------------------------------

    def scan_gtk_themes(self, user_only: bool = False) -> list[Theme]:
        """Scan and return all available GTK themes.

        Args:
            user_only: If True, limit scan to user directories.

        Returns:
            List of GTK Theme objects without duplicates (User > System precedence).
        """
        return self._scan_themes_by_type(ThemeType.GTK, user_only=user_only)

    def scan_icon_themes(self, user_only: bool = False) -> list[Theme]:
        """Scan and return all available icon packs.

        Args:
            user_only: If True, limit scan to user directories.

        Returns:
            List of ICON Theme objects without duplicates.
        """
        return self._scan_themes_by_type(ThemeType.ICON, user_only=user_only)

    def scan_cursor_themes(self, user_only: bool = False) -> list[Theme]:
        """Scan and return all available cursor themes.

        Args:
            user_only: If True, limit scan to user directories.

        Returns:
            List of CURSOR Theme objects without duplicates.
        """
        return self._scan_themes_by_type(ThemeType.CURSOR, user_only=user_only)

    def scan_shell_themes(self, user_only: bool = False) -> list[Theme]:
        """Scan and return all available GNOME Shell themes.

        Args:
            user_only: If True, limit scan to user directories.

        Returns:
            List of SHELL Theme objects without duplicates.
        """
        return self._scan_themes_by_type(ThemeType.SHELL, user_only=user_only)

    def scan_all(self, user_only: bool = False) -> list[Theme]:
        """Scan and return all detected themes (GTK, icons, cursors, and Shell).

        Args:
            user_only: If True, limit scan to user directories.

        Returns:
            Full list of detected Theme objects.
        """
        all_themes: list[Theme] = []
        all_themes.extend(self.scan_gtk_themes(user_only=user_only))
        all_themes.extend(self.scan_icon_themes(user_only=user_only))
        all_themes.extend(self.scan_cursor_themes(user_only=user_only))
        all_themes.extend(self.scan_shell_themes(user_only=user_only))
        return all_themes

    def find_theme(self, name: str, theme_type: ThemeType) -> Theme | None:
        """Find a specific theme by name and type.

        Searches with precedence (user theme shadows system theme with the same name).

        Args:
            name: Exact directory name of the theme (e.g. 'Adwaita', 'Nordic').
            theme_type: Requested theme type (ThemeType.GTK, ICON, CURSOR, or SHELL).

        Returns:
            Matching Theme object, or None if not found.
        """
        available_themes = self._scan_themes_by_type(theme_type, user_only=False)

        for theme in available_themes:
            if theme.name == name:
                return theme

        # Case-insensitive fallback
        for theme in available_themes:
            if theme.name.lower() == name.lower():
                return theme

        return None

    # -------------------------------------------------------------------------
    # Internal Scan and Heuristic Methods
    # -------------------------------------------------------------------------

    def _scan_themes_by_type(self, target_type: ThemeType, user_only: bool = False) -> list[Theme]:
        """Scan for a specific theme type applying precedence rules.

        Args:
            target_type: Theme type to look for (GTK, ICON, CURSOR, SHELL).
            user_only: If True, skip system directories.

        Returns:
            List of unique Theme objects for the specified type.
        """
        themes: list[Theme] = []
        seen_names: set[str] = set()

        # Determine target directories
        if target_type in (ThemeType.GTK, ThemeType.SHELL):
            user_dirs = self.user_theme_dirs
            system_dirs = self.system_theme_dirs
        else:
            user_dirs = self.user_icon_dirs
            system_dirs = self.system_icon_dirs

        # 1. Scan user directories (high priority)
        for base_dir in user_dirs:
            for theme in self._scan_directory(base_dir, is_user_level=True):
                if theme.theme_type == target_type and theme.name not in seen_names:
                    seen_names.add(theme.name)
                    themes.append(theme)

        # 2. Scan system directories (secondary priority, if not user_only)
        if not user_only:
            for base_dir in system_dirs:
                for theme in self._scan_directory(base_dir, is_user_level=False):
                    if theme.theme_type == target_type and theme.name not in seen_names:
                        seen_names.add(theme.name)
                        themes.append(theme)

        return themes

    def _scan_directory(self, directory: Path, is_user_level: bool) -> list[Theme]:
        """Scan a single directory for valid themes.

        Args:
            directory: Directory path to scan (e.g. /usr/share/themes).
            is_user_level: Flag indicating if this is a user directory.

        Returns:
            List of Theme objects detected in the directory.
        """
        import configparser

        found_themes: list[Theme] = []

        if not directory.exists() or not directory.is_dir():
            return found_themes

        try:
            entries = list(directory.iterdir())
        except (PermissionError, OSError):
            return found_themes

        for entry in entries:
            if not entry.is_dir():
                continue

            index_file = entry / "index.theme"
            invalid = False
            inherits_str = ""

            # If index.theme exists, parse metadata and inheritance
            if index_file.is_file():
                config = configparser.ConfigParser(interpolation=None)
                try:
                    config.read(index_file, encoding="utf-8")
                    if config.has_section("Desktop Entry"):
                        inherits_str = config.get("Desktop Entry", "Inherits", fallback="")
                    elif config.has_section("Icon Theme"):
                        inherits_str = config.get("Icon Theme", "Inherits", fallback="")
                    elif config.has_section("X-GNOME-Metatheme"):
                        inherits_str = config.get("X-GNOME-Metatheme", "Inherits", fallback="")
                except Exception:
                    invalid = True

            # Recursive inheritance chain calculation (max depth 5)
            inheritance_chain: list[str] = []
            curr_inherits = inherits_str
            depth = 0

            while curr_inherits and depth < 4:
                # Split and strip comma-separated parent names
                parents = [p.strip() for p in curr_inherits.split(",") if p.strip()]
                if not parents:
                    break

                # Add parents found at this level
                for p in parents:
                    if p not in inheritance_chain:
                        inheritance_chain.append(p)

                # Search index.theme of first parent to continue chain
                next_parent = parents[0]
                parent_path = None

                # Search known directories for parent path
                for d in (
                    self.user_theme_dirs
                    + self.system_theme_dirs
                    + self.user_icon_dirs
                    + self.system_icon_dirs
                ):
                    candidate = d / next_parent
                    if candidate.is_dir():
                        parent_path = candidate
                        break

                if parent_path and (parent_path / "index.theme").is_file():
                    parent_config = configparser.ConfigParser(interpolation=None)
                    try:
                        parent_config.read(parent_path / "index.theme", encoding="utf-8")
                        next_inherits = ""
                        if parent_config.has_section("Desktop Entry"):
                            next_inherits = parent_config.get(
                                "Desktop Entry", "Inherits", fallback=""
                            )
                        elif parent_config.has_section("Icon Theme"):
                            next_inherits = parent_config.get("Icon Theme", "Inherits", fallback="")
                        elif parent_config.has_section("X-GNOME-Metatheme"):
                            next_inherits = parent_config.get(
                                "X-GNOME-Metatheme", "Inherits", fallback=""
                            )
                        curr_inherits = next_inherits
                    except Exception:
                        break
                else:
                    break
                depth += 1

            # Detect supported types
            is_gtk = self._is_gtk_theme(entry)
            is_cursor = self._is_cursor_theme(entry)
            is_icon = self._is_icon_theme(entry)
            is_shell = self._is_shell_theme(entry)

            # If index.theme is present but type heuristics fail, treat as GTK with invalid=True
            if not (is_gtk or is_cursor or is_icon or is_shell) and index_file.is_file():
                invalid = True
                is_gtk = True  # Fallback classification

            # Register found themes
            if is_gtk:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.GTK,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )
            if is_icon:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.ICON,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )
            if is_cursor:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.CURSOR,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )
            if is_shell:
                found_themes.append(
                    Theme(
                        name=entry.name,
                        theme_type=ThemeType.SHELL,
                        path=entry,
                        is_user_level=is_user_level,
                        invalid=invalid,
                        inheritance_chain=inheritance_chain,
                    )
                )

        return found_themes

    # -------------------------------------------------------------------------
    # Theme Recognition Heuristics
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_gtk_theme(path: Path) -> bool:
        """Check if directory contains a valid GTK theme."""
        gtk_subdirs = ["gtk-4.0", "gtk-3.0", "gtk-3.20", "gtk-2.0"]
        for subdir in gtk_subdirs:
            if (path / subdir).is_dir():
                return True

        index_file = path / "index.theme"
        if index_file.is_file():
            try:
                content = index_file.read_text(encoding="utf-8", errors="ignore")
                if (
                    "GtkTheme" in content
                    or "[Desktop Entry]" in content
                    or "[X-GNOME-Metatheme]" in content
                ):
                    return True
            except OSError:
                pass

        return False

    @staticmethod
    def _is_shell_theme(path: Path) -> bool:
        """Check if directory contains a GNOME Shell theme.

        Presence of 'gnome-shell' directory (typically containing 'gnome-shell.css')
        identifies a GNOME Shell theme.
        """
        shell_dir = path / "gnome-shell"
        if shell_dir.is_dir():
            return True

        index_file = path / "index.theme"
        if index_file.is_file():
            try:
                content = index_file.read_text(encoding="utf-8", errors="ignore")
                if "[Shell Theme]" in content or "ShellTheme" in content:
                    return True
            except OSError:
                pass

        return False

    @staticmethod
    def _is_cursor_theme(path: Path) -> bool:
        """Check if directory contains a valid cursor theme."""
        cursors_dir = path / "cursors"
        return cursors_dir.is_dir()

    @staticmethod
    def _is_icon_theme(path: Path) -> bool:
        """Check if directory contains a valid icon pack."""
        index_file = path / "index.theme"
        if index_file.is_file():
            try:
                content = index_file.read_text(encoding="utf-8", errors="ignore")
                if "[Icon Theme]" in content or "Directories=" in content:
                    return True
            except OSError:
                pass

        icon_subdirs = [
            "scalable",
            "symbolic",
            "16x16",
            "22x22",
            "24x24",
            "32x32",
            "48x48",
            "64x64",
            "128x128",
            "256x256",
            "512x512",
        ]
        for subdir in icon_subdirs:
            if (path / subdir).is_dir():
                return True

        return False
