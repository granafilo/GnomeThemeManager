# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme Fork and Color Override management (Task 2.4).

Copies a base GTK theme to `~/.themes/{custom_name}-gtk4/` (or `~/.local/share/themes`),
overrides `@define-color` definitions in its CSS stylesheets, adds an `(edited)`
label in `index.theme`, and tracks forks in `theme_forks.json` for full reversibility.
"""

import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import THEME_FORKS_FILE, get_user_themes_dirs

logger = logging.getLogger("gnome_theme_manager.core.theme_forks")


@dataclass(frozen=True)
class ThemeFork:
    """Metadata tracking a user-forked theme."""

    fork_name: str
    base_theme_name: str
    fork_path: Path
    colors: dict[str, str]
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize ThemeFork to dictionary."""
        return {
            "fork_name": self.fork_name,
            "base_theme_name": self.base_theme_name,
            "fork_path": str(self.fork_path),
            "colors": dict(self.colors),
            "created_at": self.created_at,
        }


def _inject_colors_in_css(css_content: str, colors: dict[str, str]) -> str:
    """Inject or replace @define-color definitions and CSS variable overrides.

    Args:
        css_content: Original CSS text.
        colors: Dictionary of color variables to override/define.

    Returns:
        Modified CSS content.
    """
    updated_css = css_content

    # Expand aliases for maximum compatibility across GTK3, GTK4 and Libadwaita
    fg = colors.get("theme_fg_color")
    bg = colors.get("theme_bg_color")
    accent_bg = colors.get("theme_selected_bg_color") or colors.get("accent_bg_color")
    accent_fg = colors.get("theme_selected_fg_color") or colors.get("accent_fg_color")

    color_map = dict(colors)
    if fg:
        color_map["theme_fg_color"] = fg
        color_map["theme_text_color"] = fg
        color_map["window_fg_color"] = fg
        color_map["view_fg_color"] = fg
        color_map["headerbar_fg_color"] = fg
        color_map["card_fg_color"] = fg
        color_map["popover_fg_color"] = fg
        color_map["dialog_fg_color"] = fg
        color_map["sidebar_fg_color"] = fg
    if bg:
        color_map["theme_bg_color"] = bg
        color_map["theme_base_color"] = bg
        color_map["window_bg_color"] = bg
        color_map["view_bg_color"] = bg
        color_map["headerbar_bg_color"] = bg
        color_map["card_bg_color"] = bg
        color_map["popover_bg_color"] = bg
        color_map["dialog_bg_color"] = bg
        color_map["sidebar_bg_color"] = bg
        color_map["secondary_sidebar_bg_color"] = bg
    if accent_bg:
        color_map["theme_selected_bg_color"] = accent_bg
        color_map["accent_bg_color"] = accent_bg
        color_map["accent_color"] = accent_bg
        color_map["standalone_color_ok"] = accent_bg
    if accent_fg:
        color_map["theme_selected_fg_color"] = accent_fg
        color_map["accent_fg_color"] = accent_fg

    # 1. Update existing @define-color definitions
    for name, value in color_map.items():
        pattern = re.compile(rf"@define-color\s+{re.escape(name)}\s+[^;]+;", re.MULTILINE)
        new_def = f"@define-color {name} {value};"

        if pattern.search(updated_css):
            updated_css = pattern.sub(new_def, updated_css)

    # 2. Append explicit @define-color overrides at the end of the stylesheet
    # so that CSS cascading and @import statements do not overwrite user custom colors
    override_lines: list[str] = [
        "",
        "/* GTM-GTK-OVERRIDE-START */",
    ]
    for name, value in color_map.items():
        override_lines.append(f"@define-color {name} {value};")
    override_lines.append("/* GTM-GTK-OVERRIDE-END */\n")

    marker_pattern = re.compile(
        r"/\* GTM-GTK-OVERRIDE-START \*/.*?/\* GTM-GTK-OVERRIDE-END \*/\n?",
        re.DOTALL,
    )
    cleaned_css = marker_pattern.sub("", updated_css).rstrip()

    return f"{cleaned_css}\n" + "\n".join(override_lines)


def _update_index_theme_label(index_path: Path, new_name: str) -> None:
    """Update or create index.theme setting Name={new_name} (edited) and GtkTheme={new_name}."""
    label = f"{new_name} (edited)"
    if not index_path.is_file():
        content = (
            f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={label}\nComment=Customized Theme Fork\n"
            f"Encoding=UTF-8\n\n[X-GNOME-Metatheme]\nGtkTheme={new_name}\n"
        )
        index_path.write_text(content, encoding="utf-8")
        return

    try:
        lines = index_path.read_text(encoding="utf-8", errors="replace").splitlines()
        updated_lines: list[str] = []
        name_found = False
        has_metatheme = False
        has_gtk_theme = False

        for line in lines:
            if line.strip() == "[X-GNOME-Metatheme]":
                has_metatheme = True
                updated_lines.append(line)
            elif line.strip().startswith("Name="):
                updated_lines.append(f"Name={label}")
                name_found = True
            elif line.strip().startswith("GtkTheme="):
                has_gtk_theme = True
                updated_lines.append(f"GtkTheme={new_name}")
            else:
                updated_lines.append(line)

        if not name_found:
            updated_lines.append(f"Name={label}")
        if not has_metatheme:
            updated_lines.extend(["", "[X-GNOME-Metatheme]", f"GtkTheme={new_name}"])
        elif not has_gtk_theme:
            updated_lines.append(f"GtkTheme={new_name}")

        index_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    except Exception as err:
        logger.warning("Could not update index.theme in %s: %s", index_path, err)


class ThemeForkManager:
    """Manager for creating, listing, and reverting custom theme forks."""

    def __init__(
        self,
        user_themes_dir: Path | None = None,
        state_file: Path | None = None,
    ) -> None:
        """Initialize ThemeForkManager.

        Args:
            user_themes_dir: Target directory for storing user forks (default: ~/.themes).
            state_file: Path to theme_forks.json metadata file.
        """
        if user_themes_dir is not None:
            self._user_themes_dir = Path(user_themes_dir).expanduser()
        else:
            user_dirs = get_user_themes_dirs()
            # Prefer ~/.themes for legacy compat or ~/.local/share/themes
            legacy_themes = Path.home() / ".themes"
            self._user_themes_dir = legacy_themes if legacy_themes in user_dirs else user_dirs[0]

        self._state_file = (
            Path(state_file).expanduser()
            if state_file is not None
            else THEME_FORKS_FILE.expanduser()
        )

    def _sanitize_fork_name(self, name: str) -> str:
        """Sanitize fork name preventing traversal and invalid chars."""
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Fork theme name cannot be empty.")
        if len(cleaned) > 255:
            raise ValueError("Fork theme name is too long.")
        if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
            raise ValueError(f"Invalid characters in fork name '{name}'.")
        return cleaned

    @staticmethod
    def fork_from_dict(data: dict[str, Any]) -> ThemeFork:
        """Deserialize a ThemeFork from dictionary."""
        return ThemeFork(
            fork_name=str(data.get("fork_name", "")),
            base_theme_name=str(data.get("base_theme_name", "")),
            fork_path=Path(str(data.get("fork_path", ""))),
            colors=dict(data.get("colors", {})),
            created_at=data.get("created_at"),
        )

    def _read_state_forks(self) -> list[ThemeFork]:
        """Read list of forks from state file."""
        if not self._state_file.is_file():
            return []
        try:
            content = self._state_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                return []
            items = data.get("forks", [])
            return [self.fork_from_dict(it) for it in items if isinstance(it, dict)]
        except Exception as err:
            logger.warning("Failed to read theme forks state from %s: %s", self._state_file, err)
            return []

    def _write_state_forks(self, forks: list[ThemeFork]) -> None:
        """Write list of forks to state file."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"forks": [f.to_dict() for f in forks]}
        self._state_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def list_forks(self) -> list[ThemeFork]:
        """List all active tracked theme forks."""
        return self._read_state_forks()

    def get_fork(self, fork_name: str) -> ThemeFork | None:
        """Get a ThemeFork by name."""
        for f in self.list_forks():
            if f.fork_name == fork_name:
                return f
        return None

    def create_fork(
        self,
        base_theme_name: str,
        base_theme_path: Path,
        custom_name: str,
        colors: dict[str, str],
        overwrite: bool = True,
    ) -> ThemeFork:
        """Create a new theme fork with customized @define-color values.

        Args:
            base_theme_name: Name of the original theme.
            base_theme_path: Path to the original base theme directory.
            custom_name: Name for the customized fork.
            colors: Dict of color names to hex/rgba values.
            overwrite: If True, overwrite existing fork folder.

        Returns:
            ThemeFork metadata object.

        Raises:
            FileNotFoundError: If base theme path doesn't exist.
            FileExistsError: If destination exists and overwrite=False.
        """
        clean_name = self._sanitize_fork_name(custom_name)
        base_path = Path(base_theme_path).expanduser()

        if not base_path.is_dir():
            raise FileNotFoundError(f"Base theme directory not found: {base_path}")

        # Destination directory: ~/.themes/{custom_name} or ~/.local/share/themes/{custom_name}
        dest_dir_name = clean_name
        dest_dir = self._user_themes_dir / dest_dir_name

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy base theme tree into dest_dir (merging if directory already exists)
        shutil.copytree(base_path, dest_dir, symlinks=True, dirs_exist_ok=True)

        # Search for and modify all CSS stylesheets
        css_targets = [
            dest_dir / "gtk-4.0" / "gtk.css",
            dest_dir / "gtk-4.0" / "gtk-dark.css",
            dest_dir / "gtk-3.0" / "gtk.css",
            dest_dir / "gtk-3.0" / "gtk-main.css",
            dest_dir / "gtk.css",
        ]

        modified_any_css = False
        for css_file in css_targets:
            if css_file.is_file():
                try:
                    orig_content = css_file.read_text(encoding="utf-8", errors="replace")
                    updated = _inject_colors_in_css(orig_content, colors)
                    css_file.write_text(updated, encoding="utf-8")
                    modified_any_css = True
                except Exception as err:
                    logger.warning("Failed injecting colors into %s: %s", css_file, err)

        # If no CSS existed (e.g. gresource only), create gtk-4.0/gtk.css with overrides
        if not modified_any_css:
            gtk4_dir = dest_dir / "gtk-4.0"
            gtk4_dir.mkdir(parents=True, exist_ok=True)
            fallback_css = dest_dir / "gtk-4.0" / "gtk.css"
            fallback_content = _inject_colors_in_css("", colors)
            fallback_css.write_text(fallback_content, encoding="utf-8")

        # Update index.theme Name=(edited)
        _update_index_theme_label(dest_dir / "index.theme", dest_dir_name)

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        fork = ThemeFork(
            fork_name=dest_dir_name,
            base_theme_name=base_theme_name,
            fork_path=dest_dir,
            colors=dict(colors),
            created_at=now_iso,
        )

        all_forks = [f for f in self.list_forks() if f.fork_name != dest_dir_name]
        all_forks.insert(0, fork)
        self._write_state_forks(all_forks)

        logger.info(
            "Created theme fork '%s' from '%s' at %s",
            dest_dir_name,
            base_theme_name,
            dest_dir,
        )
        return fork

    def revert_fork(self, fork_name_or_path: str) -> bool:
        """Revert and delete a theme fork, restoring filesystem state.

        Args:
            fork_name_or_path: Name or folder path of the fork to delete.

        Returns:
            True if fork was deleted.

        Raises:
            FileNotFoundError: If fork was not found.
        """
        all_forks = self.list_forks()
        clean_input = self._sanitize_fork_name(fork_name_or_path)
        clean_gtk4 = clean_input if clean_input.endswith("-gtk4") else f"{clean_input}-gtk4"

        target = next(
            (
                f
                for f in all_forks
                if f.fork_name in (clean_input, clean_gtk4)
                or str(f.fork_path) == str(fork_name_or_path)
                or f.fork_path.name in (clean_input, clean_gtk4)
            ),
            None,
        )

        if target is None:
            # Check if directory exists directly in user themes
            candidate = self._user_themes_dir / clean_gtk4
            if candidate.is_dir():
                shutil.rmtree(candidate)
                return True
            candidate_raw = self._user_themes_dir / clean_input
            if candidate_raw.is_dir():
                shutil.rmtree(candidate_raw)
                return True
            raise FileNotFoundError(f"Theme fork '{fork_name_or_path}' not found.")

        if target.fork_path.exists() and target.fork_path.is_dir():
            try:
                shutil.rmtree(target.fork_path)
                logger.info("Removed theme fork directory: %s", target.fork_path)
            except Exception as err:
                logger.error("Failed to delete fork directory %s: %s", target.fork_path, err)

        updated_forks = [f for f in all_forks if f.fork_name != target.fork_name]
        self._write_state_forks(updated_forks)
        return True


# Convenience standalone functions
def create_theme_fork(
    base_theme_name: str,
    base_theme_path: Path,
    custom_name: str,
    colors: dict[str, str],
    user_themes_dir: Path | None = None,
    state_file: Path | None = None,
) -> ThemeFork:
    """Convenience helper to create a theme fork."""
    mgr = ThemeForkManager(user_themes_dir=user_themes_dir, state_file=state_file)
    return mgr.create_fork(
        base_theme_name=base_theme_name,
        base_theme_path=base_theme_path,
        custom_name=custom_name,
        colors=colors,
    )


def revert_theme_fork(
    fork_name: str,
    user_themes_dir: Path | None = None,
    state_file: Path | None = None,
) -> bool:
    """Convenience helper to revert/delete a theme fork."""
    mgr = ThemeForkManager(user_themes_dir=user_themes_dir, state_file=state_file)
    return mgr.revert_fork(fork_name)
