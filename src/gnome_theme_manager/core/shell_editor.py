# SPDX-License-Identifier: GPL-3.0-or-later

"""Shell Theme Editor & Fork Management (Task 2.7).

Provides color extraction from `gnome-shell.css`, custom fork creation in `~/.themes/{name}-shell/`,
idempotent CSS overrides with `/* GTM-OVERRIDE-START */` markers, and shell theme management.
"""

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import THEME_FORKS_FILE, get_user_themes_dirs

logger = logging.getLogger("gnome_theme_manager.core.shell_editor")

GTM_MARKER_START = "/* GTM-OVERRIDE-START */"
GTM_MARKER_END = "/* GTM-OVERRIDE-END */"


@dataclass(frozen=True)
class ShellExtractedColors:
    """Standardized representation of extracted GNOME Shell colors."""

    accent_color: str | None = None
    panel_bg: str | None = None
    panel_fg: str | None = None
    overview_bg: str | None = None
    raw_colors: dict[str, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Return True if no colors were found."""
        return not bool(self.accent_color or self.panel_bg or self.panel_fg or self.overview_bg)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "accent_color": self.accent_color,
            "panel_bg": self.panel_bg,
            "panel_fg": self.panel_fg,
            "overview_bg": self.overview_bg,
            "raw_colors": dict(self.raw_colors),
        }


@dataclass(frozen=True)
class ShellThemeFork:
    """Metadata tracking a user-forked GNOME Shell theme."""

    fork_name: str
    base_theme_name: str
    fork_path: Path
    colors: dict[str, str]
    created_at: str | None = None
    component: str = "shell"

    def to_dict(self) -> dict[str, Any]:
        """Serialize ShellThemeFork to dictionary."""
        return {
            "fork_name": self.fork_name,
            "base_theme_name": self.base_theme_name,
            "fork_path": str(self.fork_path),
            "colors": dict(self.colors),
            "created_at": self.created_at,
            "component": self.component,
        }


class ShellColorExtractor:
    """Extracts key colors from GNOME Shell theme stylesheets."""

    @staticmethod
    def find_shell_css(theme_path: Path) -> Path | None:
        """Locate gnome-shell.css within a theme directory."""
        candidates = [
            theme_path / "gnome-shell" / "gnome-shell.css",
            theme_path / "gnome-shell.css",
        ]
        for c in candidates:
            if c.is_file():
                return c
        return None

    def extract_colors(self, theme_path: Path) -> ShellExtractedColors:
        """Extract dominant shell colors from theme path."""
        css_file = self.find_shell_css(theme_path)
        if not css_file:
            return ShellExtractedColors()

        try:
            content = css_file.read_text(encoding="utf-8", errors="replace")
        except Exception as err:
            logger.warning("Failed to read shell css %s: %s", css_file, err)
            return ShellExtractedColors()

        raw_colors: dict[str, str] = {}

        # 1. Parse @define-color definitions
        define_matches = re.findall(
            r"@define-color\s+([a-zA-Z0-9_\-]+)\s+([^;]+);", content, re.MULTILINE
        )
        for name, val in define_matches:
            raw_colors[name.strip()] = val.strip()

        accent = (
            raw_colors.get("selected_bg_color")
            or raw_colors.get("theme_selected_bg_color")
            or raw_colors.get("accent_bg_color")
            or raw_colors.get("accent_color")
        )
        panel_bg = raw_colors.get("panel_bg") or raw_colors.get("panel_bg_color")
        panel_fg = raw_colors.get("panel_fg") or raw_colors.get("panel_fg_color")
        overview_bg = raw_colors.get("overview_bg") or raw_colors.get("overview_bg_color")

        # 2. Heuristics on standard GNOME Shell CSS selectors if unset
        if not panel_bg:
            panel_match = re.search(
                r"#panel\s*\{[^}]*?background(?:-color)?\s*:\s*([^;\}]+)", content
            )
            if panel_match:
                panel_bg = panel_match.group(1).strip()

        if not panel_fg:
            panel_fg_match = re.search(
                r"(?:\.panel-button|#panel)\s*\{[^}]*?(?<!background-)color\s*:\s*([^;\}]+)",
                content,
            )
            if panel_fg_match:
                panel_fg = panel_fg_match.group(1).strip()

        if not overview_bg:
            overview_match = re.search(
                r"\.overview(?:-controls)?\s*\{[^}]*?background(?:-color)?\s*:\s*([^;\}]+)",
                content,
            )
            if overview_match:
                overview_bg = overview_match.group(1).strip()

        if not accent:
            selected_match = re.search(
                r"(?:\.selected|\.active|button:active)\s*\{[^}]*?background(?:-color)?\s*:\s*([^;\}]+)",
                content,
            )
            if selected_match:
                accent = selected_match.group(1).strip()

        return ShellExtractedColors(
            accent_color=accent,
            panel_bg=panel_bg,
            panel_fg=panel_fg,
            overview_bg=overview_bg,
            raw_colors=raw_colors,
        )


def extract_shell_colors(theme_path: Path) -> ShellExtractedColors:
    """Convenience helper to extract shell colors."""
    extractor = ShellColorExtractor()
    return extractor.extract_colors(theme_path)


def generate_shell_css_override(original_css: str, colors: dict[str, str]) -> str:
    """Generate or update GTM override block in gnome-shell.css idempotently.

    Args:
        original_css: Existing CSS text.
        colors: Color mapping (accent_color, panel_bg, panel_fg, overview_bg).

    Returns:
        Updated CSS text with custom override block.
    """
    # Remove existing GTM block if present
    marker_pattern = re.compile(
        re.escape(GTM_MARKER_START) + r".*?" + re.escape(GTM_MARKER_END) + r"\n?",
        re.DOTALL,
    )
    cleaned_css = marker_pattern.sub("", original_css).rstrip()

    accent = colors.get("accent_color")
    panel_bg = colors.get("panel_bg")
    panel_fg = colors.get("panel_fg")
    overview_bg = colors.get("overview_bg")

    override_rules: list[str] = [GTM_MARKER_START]

    # @define-color definitions for modern GNOME shell
    if accent:
        override_rules.append(f"@define-color selected_bg_color {accent};")
        override_rules.append(f"@define-color theme_selected_bg_color {accent};")
    if panel_bg:
        override_rules.append(f"@define-color panel_bg_color {panel_bg};")
    if panel_fg:
        override_rules.append(f"@define-color panel_fg_color {panel_fg};")

    # CSS Rule overrides
    if panel_bg:
        override_rules.append(f"#panel {{ background-color: {panel_bg} !important; }}")
    if panel_fg:
        override_rules.append(
            f"#panel, .panel-button, #panel .clock, #panel .aggregate-menu {{ color: {panel_fg} !important; }}"
        )
    if overview_bg:
        override_rules.append(
            f".overview, #overview, .overview-controls {{ background-color: {overview_bg} !important; }}"
        )
    if accent:
        override_rules.append(
            f".popup-menu-item:active, .popup-menu-item:selected, .panel-button:active, .calendar-day-selected, "
            f".quick-settings-toggle:checked, .quick-toggle:checked, "
            f".quick-toggle-menu:checked, .quick-slider .slider, "
            f".slider-bin .slider {{ background-color: {accent} !important; color: #ffffff !important; }}"
        )
        override_rules.append(
            f".quick-settings-toggle:checked, .quick-toggle:checked {{ "
            f"background-color: {accent} !important; "
            f"border-color: {accent} !important; "
            f"color: #ffffff !important; }}"
        )

    override_rules.append(GTM_MARKER_END)
    override_block = "\n".join(override_rules)

    return f"{cleaned_css}\n\n{override_block}\n"


class ShellThemeForkManager:
    """Manager for creating and reverting user forks for GNOME Shell themes."""

    def __init__(
        self,
        user_themes_dir: Path | None = None,
        state_file: Path | None = None,
    ) -> None:
        """Initialize ShellThemeForkManager.

        Args:
            user_themes_dir: Target directory for storing user theme forks (default: ~/.themes).
            state_file: Path to theme_forks.json metadata file.
        """
        if user_themes_dir is not None:
            self._user_themes_dir = Path(user_themes_dir).expanduser()
        else:
            user_dirs = get_user_themes_dirs()
            legacy_themes = Path.home() / ".themes"
            self._user_themes_dir = legacy_themes if legacy_themes in user_dirs else user_dirs[0]

        self._state_file = (
            Path(state_file).expanduser()
            if state_file is not None
            else THEME_FORKS_FILE.expanduser()
        )

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name to valid directory identifier."""
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Shell theme fork name cannot be empty.")
        if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
            raise ValueError(f"Invalid characters in shell fork name: '{name}'")
        return cleaned

    def _read_forks(self) -> list[ShellThemeFork]:
        """Read all shell theme forks from state file."""
        if not self._state_file.is_file():
            return []
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return []
            items = data.get("forks", [])
            shell_forks: list[ShellThemeFork] = []
            for it in items:
                if isinstance(it, dict) and it.get("component") == "shell":
                    shell_forks.append(
                        ShellThemeFork(
                            fork_name=str(it.get("fork_name", "")),
                            base_theme_name=str(it.get("base_theme_name", "")),
                            fork_path=Path(str(it.get("fork_path", ""))),
                            colors=dict(it.get("colors", {})),
                            created_at=it.get("created_at"),
                            component="shell",
                        )
                    )
            return shell_forks
        except Exception as err:
            logger.warning("Failed to read shell forks from %s: %s", self._state_file, err)
            return []

    def _write_fork(self, new_fork: ShellThemeFork) -> None:
        """Save a new shell fork to the shared theme_forks.json state file."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        raw_items: list[dict[str, Any]] = []
        if self._state_file.is_file():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    raw_items = [
                        it
                        for it in data.get("forks", [])
                        if isinstance(it, dict) and it.get("fork_name") != new_fork.fork_name
                    ]
            except Exception:
                raw_items = []

        raw_items.append(new_fork.to_dict())
        self._state_file.write_text(
            json.dumps({"forks": raw_items}, indent=2, sort_keys=True), encoding="utf-8"
        )

    def create_shell_fork(
        self,
        base_theme_name: str,
        base_theme_path: Path,
        custom_name: str,
        colors: dict[str, str],
        overwrite: bool = True,
    ) -> ShellThemeFork:
        """Create a customized fork for GNOME Shell theme."""
        clean_name = self._sanitize_name(custom_name)
        fork_name = clean_name
        dest_dir = self._user_themes_dir / fork_name

        if dest_dir.exists() and not overwrite:
            raise FileExistsError(f"Shell fork directory already exists: {dest_dir}")

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_shell_dir = dest_dir / "gnome-shell"
        if dest_shell_dir.exists() and overwrite:
            shutil.rmtree(dest_shell_dir)
        dest_shell_dir.mkdir(parents=True, exist_ok=True)

        # Copy original gnome-shell contents if present
        orig_shell = base_theme_path / "gnome-shell"
        if orig_shell.is_dir():
            for item in orig_shell.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest_shell_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(
                        item, dest_shell_dir / item.name, symlinks=True, dirs_exist_ok=True
                    )
        elif (base_theme_path / "gnome-shell.css").is_file():
            shutil.copy2(base_theme_path / "gnome-shell.css", dest_shell_dir / "gnome-shell.css")

        # Generate CSS override
        css_file = dest_shell_dir / "gnome-shell.css"
        initial_css = (
            css_file.read_text(encoding="utf-8", errors="replace") if css_file.is_file() else ""
        )
        updated_css = generate_shell_css_override(initial_css, colors)
        css_file.write_text(updated_css, encoding="utf-8")

        # Write or update index.theme metadata
        index_file = dest_dir / "index.theme"
        if index_file.is_file():
            try:
                lines = index_file.read_text(encoding="utf-8", errors="replace").splitlines()
                has_metatheme_sec = False
                has_shell_theme = False
                updated_lines = []
                for line in lines:
                    if line.strip() == "[X-GNOME-Metatheme]":
                        has_metatheme_sec = True
                        updated_lines.append(line)
                    elif line.strip().startswith("GnomeShellTheme="):
                        has_shell_theme = True
                        updated_lines.append(f"GnomeShellTheme={fork_name}")
                    else:
                        updated_lines.append(line)
                if not has_metatheme_sec:
                    updated_lines.extend(
                        ["", "[X-GNOME-Metatheme]", f"GnomeShellTheme={fork_name}"]
                    )
                elif not has_shell_theme:
                    updated_lines.append(f"GnomeShellTheme={fork_name}")
                index_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
            except Exception as err:
                logger.warning("Failed updating index.theme for shell fork: %s", err)
        else:
            index_content = (
                f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={fork_name} (edited)\n"
                f"Comment=Custom Theme created with GnomeThemeManager\n"
                f"Encoding=UTF-8\n\n[X-GNOME-Metatheme]\nGtkTheme={fork_name}\nGnomeShellTheme={fork_name}\n"
            )
            index_file.write_text(index_content, encoding="utf-8")

        fork = ShellThemeFork(
            fork_name=fork_name,
            base_theme_name=base_theme_name,
            fork_path=dest_dir,
            colors=colors,
            created_at=datetime.now(timezone.utc).isoformat(),
            component="shell",
        )
        self._write_fork(fork)
        return fork

    def revert_shell_fork(self, fork_name_or_path: str | Path) -> bool:
        """Revert and delete a shell theme fork."""
        clean_input = str(fork_name_or_path).strip()
        clean_shell = clean_input if clean_input.endswith("-shell") else f"{clean_input}-shell"

        dest_dir = self._user_themes_dir / clean_shell
        if not dest_dir.is_dir() and (self._user_themes_dir / clean_input).is_dir():
            dest_dir = self._user_themes_dir / clean_input

        if dest_dir.is_dir():
            shutil.rmtree(dest_dir)

        if self._state_file.is_file():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    kept = [
                        it
                        for it in data.get("forks", [])
                        if isinstance(it, dict)
                        and it.get("fork_name") not in (clean_input, clean_shell)
                        and it.get("fork_path") != str(dest_dir)
                    ]
                    self._state_file.write_text(
                        json.dumps({"forks": kept}, indent=2, sort_keys=True), encoding="utf-8"
                    )
            except Exception as err:
                logger.warning("Failed to update forks state file: %s", err)

        return True
