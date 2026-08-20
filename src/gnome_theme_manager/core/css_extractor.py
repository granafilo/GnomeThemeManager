# SPDX-License-Identifier: GPL-3.0-or-later

"""CSS Color Extractor for GTK3 / GTK4 themes.

Parses CSS stylesheets (`gtk-4.0/gtk.css`, `gtk-3.0/gtk-main.css`, `gtk-3.0/gtk.css`),
resolves `@import` rules safely, and extracts `@define-color` definitions
(such as theme_fg_color, theme_bg_color, theme_selected_bg_color, accent colors, wm_*).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("gnome_theme_manager.core.css_extractor")

# Regex to strip CSS comments: /* ... */
COMMENT_REGEX = re.compile(r"/\*.*?\*/", re.DOTALL)

# Regex to match @define-color <name> <value>;
DEFINE_COLOR_REGEX = re.compile(
    r"@define-color\s+([a-zA-Z0-9_\-]+)\s+([^;]+);",
    re.MULTILINE,
)

# Regex to match @import url("...") or @import "..."
IMPORT_REGEX = re.compile(
    r"""@import\s+(?:url\(['"]?([^'")]+)['"]?\)|['"]([^'"]+)['"]);""",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ExtractedColors:
    """Standardized representation of extracted theme colors."""

    theme_fg_color: str | None = None
    theme_bg_color: str | None = None
    theme_selected_bg_color: str | None = None
    theme_selected_fg_color: str | None = None
    accent_color: str | None = None
    accent_bg_color: str | None = None
    accent_fg_color: str | None = None
    wm_title: str | None = None
    wm_bg_a: str | None = None
    wm_bg_b: str | None = None
    raw_colors: dict[str, str] = field(default_factory=dict)
    source_file: Path | None = None

    def is_empty(self) -> bool:
        """Return True if no colors were extracted."""
        return not bool(self.raw_colors)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "theme_fg_color": self.theme_fg_color,
            "theme_bg_color": self.theme_bg_color,
            "theme_selected_bg_color": self.theme_selected_bg_color,
            "theme_selected_fg_color": self.theme_selected_fg_color,
            "accent_color": self.accent_color,
            "accent_bg_color": self.accent_bg_color,
            "accent_fg_color": self.accent_fg_color,
            "wm_title": self.wm_title,
            "wm_bg_a": self.wm_bg_a,
            "wm_bg_b": self.wm_bg_b,
            "raw_colors": dict(self.raw_colors),
            "source_file": str(self.source_file) if self.source_file else None,
        }


def parse_css_define_colors(css_text: str) -> dict[str, str]:
    """Extract all `@define-color` name-value pairs from raw CSS content.

    Args:
        css_text: Raw CSS text.

    Returns:
        Dictionary mapping color variable names to their definitions.
    """
    clean_css = COMMENT_REGEX.sub("", css_text)
    colors: dict[str, str] = {}

    for match in DEFINE_COLOR_REGEX.finditer(clean_css):
        name = match.group(1).strip()
        value = match.group(2).strip()
        colors[name] = value

    return colors


def _parse_css_file_recursive(
    file_path: Path,
    visited: set[Path] | None = None,
) -> dict[str, str]:
    """Parse CSS file and its imports recursively.

    Args:
        file_path: Path to the root CSS file.
        visited: Set of already parsed files to prevent import cycles.

    Returns:
        Merged dictionary of color definitions.
    """
    if visited is None:
        visited = set()

    real_path = file_path.resolve()
    if real_path in visited or not file_path.is_file():
        return {}

    visited.add(real_path)

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as err:
        logger.warning("Could not read CSS file %s: %s", file_path, err)
        return {}

    clean_content = COMMENT_REGEX.sub("", content)

    # First collect colors from imported files
    colors: dict[str, str] = {}
    for match in IMPORT_REGEX.finditer(clean_content):
        import_target = match.group(1) or match.group(2)
        if not import_target:
            continue
        target_path = file_path.parent / import_target
        imported_colors = _parse_css_file_recursive(target_path, visited)
        colors.update(imported_colors)

    # Direct define-colors in current file take precedence
    direct_colors = parse_css_define_colors(clean_content)
    colors.update(direct_colors)

    return colors


def extract_theme_colors(theme_dir_or_file: Path) -> ExtractedColors:
    """Inspect a theme directory or CSS file and extract color definitions.

    Search priority:
    1. Direct file if given a file
    2. `gtk-4.0/gtk.css`
    3. `gtk-3.0/gtk.css`
    4. `gtk-3.0/gtk-main.css`

    Args:
        theme_dir_or_file: Path to theme directory or direct CSS file.

    Returns:
        ExtractedColors instance populated with found colors.
    """
    path = Path(theme_dir_or_file).expanduser()

    candidate_files: list[Path] = []
    if path.is_file():
        candidate_files.append(path)
    elif path.is_dir():
        candidate_files.extend(
            [
                path / "gtk-4.0" / "gtk.css",
                path / "gtk-3.0" / "gtk.css",
                path / "gtk-3.0" / "gtk-main.css",
            ]
        )

    for candidate in candidate_files:
        if candidate.is_file():
            raw_colors = _parse_css_file_recursive(candidate)
            if raw_colors:
                return ExtractedColors(
                    theme_fg_color=raw_colors.get("theme_fg_color"),
                    theme_bg_color=raw_colors.get("theme_bg_color"),
                    theme_selected_bg_color=raw_colors.get("theme_selected_bg_color"),
                    theme_selected_fg_color=raw_colors.get("theme_selected_fg_color"),
                    accent_color=raw_colors.get("accent_color")
                    or raw_colors.get("theme_selected_bg_color"),
                    accent_bg_color=raw_colors.get("accent_bg_color")
                    or raw_colors.get("accent_color")
                    or raw_colors.get("theme_selected_bg_color"),
                    accent_fg_color=raw_colors.get("accent_fg_color")
                    or raw_colors.get("theme_selected_fg_color"),
                    wm_title=raw_colors.get("wm_title"),
                    wm_bg_a=raw_colors.get("wm_bg_a"),
                    wm_bg_b=raw_colors.get("wm_bg_b"),
                    raw_colors=raw_colors,
                    source_file=candidate,
                )

    return ExtractedColors()
