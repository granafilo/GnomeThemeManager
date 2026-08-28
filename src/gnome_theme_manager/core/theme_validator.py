# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme validator module.

Validates the structure and integrity of themes:
- Checks index.theme desktop entry, metadata and metatheme sections.
- Validates GTK 3 / GTK 4 style files (gtk.css).
- Validates cursor theme folders and cursor entries.
- Validates icon theme indexes and icon availability.
- Validates GNOME Shell theme CSS stylesheets.
"""

import configparser
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .models import ThemeType

logger = logging.getLogger("gnome_theme_manager.core.theme_validator")

# Standard icon basenames to look for when verifying icon packs
STANDARD_ICON_BASENAMES: set[str] = {
    "folder",
    "folder-open",
    "user-home",
    "user-desktop",
    "user-trash",
    "system-file-manager",
    "preferences-system",
    "document-open",
    "document-save",
    "edit-copy",
    "edit-cut",
    "edit-paste",
    "dialog-information",
    "dialog-warning",
    "dialog-error",
}


@dataclass(frozen=True)
class ThemeValidationResult:
    """Outcome of validating a theme on the filesystem."""

    valid: bool
    warnings: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)


class ThemeValidator:
    """Validates structural integrity and compliance of installed or imported themes."""

    def validate(self, theme_path: Path, theme_type: ThemeType) -> ThemeValidationResult:
        """Validate a theme directory based on its expected ThemeType.

        Args:
            theme_path: Directory path of the theme to inspect.
            theme_type: Expected ThemeType (GTK, ICON, CURSOR, or SHELL).

        Returns:
            ThemeValidationResult containing validity boolean, warnings, and missing files list.
        """
        path = Path(theme_path)
        warnings: list[str] = []
        missing_files: list[str] = []

        if not path.exists():
            return ThemeValidationResult(
                valid=False,
                warnings=[f"Path does not exist: {path}"],
                missing_files=[str(path)],
            )

        if not path.is_dir():
            return ThemeValidationResult(
                valid=False,
                warnings=[f"Path is not a directory: {path}"],
                missing_files=[str(path)],
            )

        if theme_type == ThemeType.GTK:
            return self._validate_gtk(path)
        elif theme_type == ThemeType.CURSOR:
            return self._validate_cursor(path)
        elif theme_type == ThemeType.ICON:
            return self._validate_icon(path)
        elif theme_type == ThemeType.SHELL:
            return self._validate_shell(path)

        return ThemeValidationResult(valid=True, warnings=warnings, missing_files=missing_files)

    def _validate_index_theme(
        self,
        index_path: Path,
        expected_sections: list[str],
    ) -> tuple[bool, list[str], configparser.ConfigParser]:
        """Parse index.theme with configparser and verify expected sections."""
        warnings: list[str] = []
        config = configparser.ConfigParser(interpolation=None)

        if not index_path.is_file():
            warnings.append("Missing index.theme configuration file.")
            return False, warnings, config

        try:
            config.read(str(index_path), encoding="utf-8")
        except Exception as err:
            warnings.append(f"Failed to parse index.theme: {err}")
            return False, warnings, config

        has_section = any(config.has_section(sec) for sec in expected_sections)
        if not has_section:
            warnings.append(
                f"index.theme is missing required sections (expected one of: {expected_sections})."
            )
            return False, warnings, config

        return True, warnings, config

    def _validate_gtk(self, path: Path) -> ThemeValidationResult:
        """Validate GTK theme directory."""
        warnings: list[str] = []
        missing_files: list[str] = []

        has_gtk3 = (path / "gtk-3.0" / "gtk.css").is_file() or (
            path / "gtk-3.0" / "gtk-dark.css"
        ).is_file()
        has_gtk4 = (path / "gtk-4.0" / "gtk.css").is_file() or (
            path / "gtk-4.0" / "gtk-dark.css"
        ).is_file()
        has_gtk2 = (path / "gtk-2.0" / "gtkrc").is_file()

        index_path = path / "index.theme"
        if index_path.is_file():
            _, idx_warns, _ = self._validate_index_theme(
                index_path, ["Desktop Entry", "X-GNOME-Metatheme", "Theme"]
            )
            warnings.extend(idx_warns)
        else:
            warnings.append("Missing index.theme metadata file.")

        if not (has_gtk3 or has_gtk4):
            missing_files.append("gtk-3.0/gtk.css or gtk-4.0/gtk.css")
            if has_gtk2:
                warnings.append(
                    "Legacy GTK 2 theme only (gtk-2.0). Missing modern GTK 3.0 or GTK 4.0 stylesheets."
                )
            else:
                warnings.append("No modern GTK stylesheet (gtk-3.0 or gtk-4.0) detected.")
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=missing_files
            )

        is_valid = len(missing_files) == 0 and not any(
            "failed to parse" in w.lower() for w in warnings
        )
        return ThemeValidationResult(valid=is_valid, warnings=warnings, missing_files=missing_files)

    def _validate_cursor(self, path: Path) -> ThemeValidationResult:
        """Validate mouse cursor theme directory."""
        warnings: list[str] = []
        missing_files: list[str] = []

        cursors_dir = path / "cursors"
        if not cursors_dir.is_dir():
            missing_files.append("cursors")
            warnings.append("Missing 'cursors' directory.")
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=missing_files
            )

        cursor_files = [f for f in cursors_dir.iterdir() if f.is_file()]
        if not cursor_files:
            warnings.append("Cursor directory contains no cursor files.")
            missing_files.append("cursors/*")
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=missing_files
            )

        index_path = path / "index.theme"
        if index_path.is_file():
            _, idx_warns, _ = self._validate_index_theme(
                index_path, ["Icon Theme", "Desktop Entry", "Cursor Theme"]
            )
            warnings.extend(idx_warns)

        return ThemeValidationResult(valid=True, warnings=warnings, missing_files=missing_files)

    def _validate_icon(self, path: Path) -> ThemeValidationResult:
        """Validate icon theme pack directory."""
        warnings: list[str] = []
        missing_files: list[str] = []

        index_path = path / "index.theme"
        if not index_path.is_file():
            missing_files.append("index.theme")
            warnings.append("Missing index.theme file for icon pack.")
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=missing_files
            )

        idx_ok, idx_warns, _ = self._validate_index_theme(
            index_path, ["Icon Theme", "Desktop Entry"]
        )
        warnings.extend(idx_warns)
        if not idx_ok:
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=missing_files
            )

        # Check if theme inherits from parent icon packs (e.g. Yaru, Humanity, Adwaita, hicolor)
        inherits_parents = False
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(index_path, encoding="utf-8")
            for sec in ("Icon Theme", "Desktop Entry"):
                if config.has_section(sec) and config.get(sec, "Inherits", fallback="").strip():
                    inherits_parents = True
                    break
        except Exception:
            pass

        # Validate that declared directories in index.theme are well-formed (each declared directory must have a section with 'Size')
        try:
            config = configparser.ConfigParser(interpolation=None)
            config.read(index_path, encoding="utf-8")
            main_sec = "Icon Theme" if config.has_section("Icon Theme") else "Desktop Entry"
            dirs_str = config.get(main_sec, "Directories", fallback="")
            if dirs_str:
                for d in [item.strip() for item in dirs_str.split(",") if item.strip()]:
                    if not config.has_section(d):
                        warnings.append(
                            f"Directory '{d}' declared in Directories list is missing its section in index.theme."
                        )
                        return ThemeValidationResult(
                            valid=False, warnings=warnings, missing_files=[f"index.theme [{d}]"]
                        )
                    elif not config.has_option(d, "Size"):
                        warnings.append(
                            f"Directory '{d}' in index.theme is missing the required 'Size' field."
                        )
                        return ThemeValidationResult(
                            valid=False,
                            warnings=warnings,
                            missing_files=[f"index.theme [{d}] Size"],
                        )
        except Exception as err:
            warnings.append(f"Error parsing index.theme directories: {err}")
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=["index.theme"]
            )

        # Count detected standard icons across all subdirectories
        found_standard_icons: set[str] = set()
        for p in path.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".svg", ".png", ".xpm"):
                stem = p.stem.lower()
                if stem in STANDARD_ICON_BASENAMES:
                    found_standard_icons.add(stem)

        # Only warn for standalone icon packs that do NOT inherit from parent themes and have < 5 icons
        if len(found_standard_icons) < 5 and not inherits_parents:
            warnings.append(
                f"Icon pack has only {len(found_standard_icons)} standard icons detected "
                "(recommended minimum: 5)."
            )

        return ThemeValidationResult(
            valid=True,
            warnings=warnings,
            missing_files=missing_files,
        )

    def _validate_shell(self, path: Path) -> ThemeValidationResult:
        """Validate GNOME Shell theme directory."""
        warnings: list[str] = []
        missing_files: list[str] = []

        has_shell_dir = (path / "gnome-shell" / "gnome-shell.css").is_file()
        has_direct_css = (path / "gnome-shell.css").is_file()

        if not (has_shell_dir or has_direct_css):
            missing_files.append("gnome-shell/gnome-shell.css")
            warnings.append("Missing gnome-shell/gnome-shell.css stylesheet.")
            return ThemeValidationResult(
                valid=False, warnings=warnings, missing_files=missing_files
            )

        return ThemeValidationResult(valid=True, warnings=warnings, missing_files=missing_files)
