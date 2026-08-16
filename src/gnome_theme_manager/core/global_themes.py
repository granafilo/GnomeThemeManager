# SPDX-License-Identifier: GPL-3.0-or-later

"""Global Themes data models and manager.

Provides discovery, loading, and application of full desktop Global Themes
composed of GTK, Icon, Cursor, GNOME Shell, and color scheme settings.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .constants import GLOBAL_THEMES_FILE, PRESETS_DIR
from .models import ThemeSet, ThemeType
from .scanner import ThemeScanner

logger = logging.getLogger("gnome_theme_manager.core.global_themes")

# Bundled data directory inside python package
BUNDLED_GLOBAL_THEMES_DIR = Path(__file__).parent.parent / "data" / "global_themes"


@dataclass(frozen=True)
class GlobalTheme:
    """Representation of a full desktop Global Theme."""

    id: str
    name: str
    description: str
    components: ThemeSet
    author: str | None = None
    origin: Literal["bundled", "user"] = "bundled"
    is_bundled: bool = False
    created_at: str | None = None
    thumbnail_path: Path | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize GlobalTheme to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "origin": self.origin,
            "is_bundled": self.is_bundled,
            "created_at": self.created_at,
            "thumbnail_path": str(self.thumbnail_path) if self.thumbnail_path else None,
            "tags": list(self.tags),
            "components": self.components.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        is_bundled: bool | None = None,
        base_dir: Path | None = None,
    ) -> "GlobalTheme":
        """Construct a GlobalTheme instance from a dictionary."""
        theme_id = str(data.get("id", "")).strip()
        name = str(data.get("name", theme_id or "Unnamed Theme")).strip()
        description = str(data.get("description", "")).strip()
        author = data.get("author")

        origin_val: Literal["bundled", "user"] = "bundled"
        raw_origin = data.get("origin")
        if raw_origin in ("bundled", "user"):
            origin_val = raw_origin
        elif is_bundled is False or data.get("is_bundled") is False:
            origin_val = "user"

        bundled_flag = is_bundled if is_bundled is not None else (origin_val == "bundled")
        created_at = data.get("created_at")

        thumb_str = data.get("thumbnail_path") or data.get("thumbnail")
        thumb_path: Path | None = None
        if thumb_str:
            p = Path(thumb_str)
            if not p.is_absolute() and base_dir is not None:
                thumb_path = base_dir / p
            else:
                thumb_path = p

        comp_dict = data.get("components", {})
        components = ThemeSet(
            gtk_theme=comp_dict.get("gtk_theme") or comp_dict.get("gtk3") or comp_dict.get("gtk4"),
            icon_theme=comp_dict.get("icon_theme") or comp_dict.get("icons"),
            cursor_theme=comp_dict.get("cursor_theme") or comp_dict.get("cursors"),
            color_scheme=comp_dict.get("color_scheme"),
            shell_theme=comp_dict.get("shell_theme") or comp_dict.get("shell"),
        )

        tags = list(data.get("tags", []))

        return cls(
            id=theme_id,
            name=name,
            description=description,
            components=components,
            author=author,
            origin=origin_val,
            is_bundled=bundled_flag,
            created_at=created_at,
            thumbnail_path=thumb_path,
            tags=tags,
        )


class GlobalThemeManager:
    """Manager for loading, saving, querying, and managing Global Themes."""

    def __init__(
        self,
        bundled_dir: Path | None = None,
        user_presets_dir: Path | None = None,
        state_file: Path | None = None,
        scanner: ThemeScanner | None = None,
        current_themes_provider: Callable[[], ThemeSet] | None = None,
    ) -> None:
        """Initialize GlobalThemeManager.

        Args:
            bundled_dir: Directory containing bundled global theme JSON files (optional fallback).
            user_presets_dir: Directory containing legacy user presets.json.
            state_file: Path to global_themes.json in state directory.
            scanner: ThemeScanner instance to discover real installed themes.
            current_themes_provider: Optional callable returning current ThemeSet.
        """
        self._bundled_dir = (
            Path(bundled_dir).expanduser()
            if bundled_dir is not None
            else BUNDLED_GLOBAL_THEMES_DIR
        )
        self._user_presets_dir = (
            Path(user_presets_dir).expanduser()
            if user_presets_dir is not None
            else PRESETS_DIR.expanduser()
        )
        self._state_file = (
            Path(state_file).expanduser()
            if state_file is not None
            else GLOBAL_THEMES_FILE.expanduser()
        )
        self._scanner = scanner or ThemeScanner()
        self._current_themes_provider = current_themes_provider

    def _sanitize_name(self, name: str) -> str:
        """Validate and sanitize global theme name preventing path traversal and illegal characters."""
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Theme name cannot be empty.")
        if len(cleaned) > 255:
            raise ValueError(f"Theme name is too long ({len(cleaned)} characters, maximum 255).")
        if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
            raise ValueError(f"Invalid theme name: '{name}'. Path characters are not allowed.")
        if cleaned in (".", ".."):
            raise ValueError(f"Invalid theme name: '{name}'. Path characters are not allowed.")
        if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
            raise ValueError(f"Theme name '{name}' contains disallowed control characters.")
        return cleaned

    def save_global_theme(
        self,
        name: str,
        theme_set: ThemeSet,
        description: str = "",
        overwrite: bool = False,
    ) -> GlobalTheme:
        """Save a ThemeSet as a user-level Global Theme.

        Args:
            name: Human readable name.
            theme_set: ThemeSet components.
            description: Optional description.
            overwrite: If True, overwrite existing user theme with same name.

        Returns:
            The saved GlobalTheme instance.

        Raises:
            ValueError: If name is invalid or ThemeSet is empty.
            FileExistsError: If theme exists and overwrite=False.
        """
        clean_name = self._sanitize_name(name)
        if theme_set.is_empty():
            raise ValueError("Cannot save an empty theme configuration.")

        theme_id = f"user-{clean_name.lower().replace(' ', '-')}"
        existing_themes = self.list_global_themes()

        existing = next((t for t in existing_themes if t.name == clean_name or t.id == theme_id), None)
        if existing and existing.origin == "bundled":
            raise ValueError(f"Cannot overwrite bundled system theme '{clean_name}'.")
        if existing and not overwrite:
            raise FileExistsError(f"Global Theme '{clean_name}' already exists.")

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        user_theme = GlobalTheme(
            id=theme_id,
            name=clean_name,
            description=description or "User created global theme",
            components=theme_set,
            origin="user",
            is_bundled=False,
            created_at=now_iso,
        )

        all_state = self._load_state_themes()
        if not all_state:
            all_state = self._auto_generate_from_system()

        # Update or append in state list
        updated: list[GlobalTheme] = [t for t in all_state if t.id != user_theme.id and t.name != user_theme.name]
        # Insert user theme at top
        updated.insert(0, user_theme)

        self._save_state_themes(updated)
        logger.info("Global Theme '%s' saved successfully.", clean_name)
        return user_theme

    def delete_global_theme(self, theme_id_or_name: str) -> bool:
        """Delete a user-created Global Theme.

        Args:
            theme_id_or_name: ID or exact name of the theme to delete.

        Returns:
            True if deleted.

        Raises:
            ValueError: If attempting to delete a bundled theme.
            FileNotFoundError: If theme not found.
        """
        all_themes = self.list_global_themes()
        target = next((t for t in all_themes if t.id == theme_id_or_name or t.name == theme_id_or_name), None)

        if target is None:
            raise FileNotFoundError(f"Global Theme '{theme_id_or_name}' not found.")

        if target.origin == "bundled" or target.is_bundled:
            raise ValueError(f"Cannot delete bundled system theme '{target.name}'.")

        all_state = self._load_state_themes()
        updated = [t for t in all_state if t.id != target.id and t.name != target.name]
        self._save_state_themes(updated)
        logger.info("Global Theme '%s' deleted successfully.", target.name)
        return True

    def _auto_generate_from_system(self) -> list[GlobalTheme]:
        """Inspect available installed themes and generate 3 reliable initial Global Themes."""
        generated: list[GlobalTheme] = []

        # 1. Current / Default System theme
        current = self._current_themes_provider() if self._current_themes_provider else None
        if current and not current.is_empty():
            current_theme = GlobalTheme(
                id="auto-current",
                name="Current Setup",
                description="Snapshot of active system themes and preferences.",
                components=current,
                author="System",
                is_bundled=True,
                tags=["default", "active"],
            )
            generated.append(current_theme)

        # Get all installed themes per component
        if hasattr(self._scanner, "scan_gtk_themes"):
            gtk_themes = [t.name for t in self._scanner.scan_gtk_themes()]
            icon_themes = [t.name for t in self._scanner.scan_icon_themes()]
            cursor_themes = [t.name for t in self._scanner.scan_cursor_themes()]
            shell_themes = [t.name for t in self._scanner.scan_shell_themes()]
        elif hasattr(self._scanner, "list_themes"):
            gtk_themes = [t.name for t in self._scanner.list_themes(ThemeType.GTK)]
            icon_themes = [t.name for t in self._scanner.list_themes(ThemeType.ICON)]
            cursor_themes = [t.name for t in self._scanner.list_themes(ThemeType.CURSOR)]
            shell_themes = [t.name for t in self._scanner.list_themes(ThemeType.SHELL)]
        else:
            gtk_themes, icon_themes, cursor_themes, shell_themes = [], [], [], []

        def pick_match(pool: list[str], keywords: list[str], fallback: str | None = None) -> str | None:
            for kw in keywords:
                for item in pool:
                    if kw.lower() in item.lower():
                        return item
            if pool:
                return pool[0]
            return fallback

        # 2. Dark theme suite
        dark_gtk = pick_match(gtk_themes, ["dark", "night", "black"], fallback=current.gtk_theme if current else None)
        dark_icon = pick_match(icon_themes, ["dark", "papirus-dark", "yaru-dark", "black"], fallback=current.icon_theme if current else None)
        dark_cursor = pick_match(cursor_themes, ["dark", "bibata", "yaru", "adwaita"], fallback=current.cursor_theme if current else None)
        dark_shell = pick_match(shell_themes, ["dark", "yaru", "default"], fallback=current.shell_theme if current else None)

        if dark_gtk or dark_icon:
            dark_theme = GlobalTheme(
                id="auto-dark",
                name="Dark Suite",
                description="Cohesive dark style using themes detected on your system.",
                components=ThemeSet(
                    gtk_theme=dark_gtk,
                    icon_theme=dark_icon,
                    cursor_theme=dark_cursor,
                    shell_theme=dark_shell,
                    color_scheme="prefer-dark",
                ),
                author="Auto-Generated",
                is_bundled=True,
                tags=["dark"],
            )
            generated.append(dark_theme)

        # 3. Light / Modern theme suite
        light_gtk = pick_match(gtk_themes, ["light", "yaru", "adwaita"], fallback=gtk_themes[0] if gtk_themes else None)
        light_icon = pick_match(icon_themes, ["light", "papirus", "yaru", "adwaita"], fallback=icon_themes[0] if icon_themes else None)
        light_cursor = pick_match(cursor_themes, ["light", "adwaita", "yaru"], fallback=cursor_themes[0] if cursor_themes else None)
        light_shell = pick_match(shell_themes, ["light", "yaru", "default"], fallback=shell_themes[0] if shell_themes else None)

        if light_gtk or light_icon:
            light_theme = GlobalTheme(
                id="auto-light",
                name="Light Suite",
                description="Clean light desktop appearance using themes detected on your system.",
                components=ThemeSet(
                    gtk_theme=light_gtk,
                    icon_theme=light_icon,
                    cursor_theme=light_cursor,
                    shell_theme=light_shell,
                    color_scheme="prefer-light",
                ),
                author="Auto-Generated",
                is_bundled=True,
                tags=["light"],
            )
            generated.append(light_theme)

        # Save to state file
        try:
            self._save_state_themes(generated)
        except Exception as err:
            logger.warning("Could not persist auto-generated global themes: %s", err)

        return generated

    def _save_state_themes(self, themes: list[GlobalTheme]) -> None:
        """Save themes to global_themes.json in state directory."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"global_themes": [t.to_dict() for t in themes]}
        self._state_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _load_state_themes(self) -> list[GlobalTheme]:
        """Load themes from ~/.local/state/gnome-theme-manager/global_themes.json."""
        if not self._state_file.is_file():
            return []

        try:
            content = self._state_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                return []
            items = data.get("global_themes", [])
            themes: list[GlobalTheme] = []
            for it in items:
                if isinstance(it, dict):
                    themes.append(GlobalTheme.from_dict(it, is_bundled=bool(it.get("is_bundled", False))))
            return themes
        except Exception as err:
            logger.warning("Error reading state file %s: %s", self._state_file, err)
            return []

    def _load_bundled_themes(self) -> list[GlobalTheme]:
        """Load built-in curated global themes from data directory."""
        themes: list[GlobalTheme] = []
        if not self._bundled_dir.is_dir():
            return themes

        for json_path in sorted(self._bundled_dir.glob("*.json")):
            try:
                content = json_path.read_text(encoding="utf-8")
                data = json.loads(content)
                if not isinstance(data, dict):
                    continue
                if not data.get("id"):
                    data["id"] = json_path.stem
                theme = GlobalTheme.from_dict(
                    data,
                    is_bundled=True,
                    base_dir=self._bundled_dir,
                )
                themes.append(theme)
            except Exception as err:
                logger.warning("Failed to load bundled global theme from %s: %s", json_path, err)

        return themes

    def _load_user_preset_themes(self) -> list[GlobalTheme]:
        """Load user presets as global themes."""
        themes: list[GlobalTheme] = []
        presets_file = self._user_presets_dir / "presets.json"
        if not presets_file.is_file():
            return themes

        try:
            content = presets_file.read_text(encoding="utf-8")
            data = json.loads(content)
            preset_items = data.get("presets", [])
            for item in preset_items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not name:
                    continue
                theme_id = f"user-{name.lower().replace(' ', '-')}"
                theme = GlobalTheme.from_dict(
                    {
                        "id": theme_id,
                        "name": name,
                        "description": "User created preset",
                        "components": item.get("components", {}),
                    },
                    is_bundled=False,
                    base_dir=self._user_presets_dir,
                )
                themes.append(theme)
        except Exception as err:
            logger.warning("Failed to load user presets as global themes: %s", err)

        return themes

    def list_global_themes(self) -> list[GlobalTheme]:
        """List all available global themes with strict ordering.

        Rules:
        1. Global Themes with origin 'user' on top (most recent created_at first).
        2. Global Themes with origin 'bundled' at the bottom.

        Returns:
            List of GlobalTheme instances ordered according to rule.
        """
        state_themes = self._load_state_themes()
        if not state_themes:
            state_themes = self._auto_generate_from_system()

        bundled = self._load_bundled_themes()
        user_presets = self._load_user_preset_themes()

        theme_map: dict[str, GlobalTheme] = {}
        for theme in bundled:
            theme_map[theme.id] = theme
        for theme in state_themes:
            theme_map[theme.id] = theme
        for theme in user_presets:
            theme_map[theme.id] = theme

        all_themes = list(theme_map.values())

        user_themes = [t for t in all_themes if t.origin == "user"]
        bundled_themes = [t for t in all_themes if t.origin == "bundled"]

        # Sort user themes by created_at descending (or name if no date)
        user_themes.sort(key=lambda t: (t.created_at or "", t.name.lower()), reverse=True)
        # Sort bundled themes consistently
        bundled_themes.sort(key=lambda t: t.name.lower())

        return user_themes + bundled_themes

    def get_global_theme(self, theme_id: str) -> GlobalTheme | None:
        """Find a GlobalTheme by its ID.

        Args:
            theme_id: Identifier of the global theme.

        Returns:
            GlobalTheme if found, None otherwise.
        """
        for theme in self.list_global_themes():
            if theme.id == theme_id or theme.name == theme_id:
                return theme
        return None
