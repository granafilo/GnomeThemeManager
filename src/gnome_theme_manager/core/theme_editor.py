# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme Composition and Mixer domain logic.

Allows mixing individual components (GTK3, GTK4, Shell, Icons, Cursors, Color Scheme)
into a cohesive named ThemeComposition and saving it as a user-composed Global Theme.
"""

import logging
from dataclasses import dataclass
from typing import Any

from .global_themes import GlobalTheme, GlobalThemeManager
from .models import ThemeSet

logger = logging.getLogger("gnome_theme_manager.core.theme_editor")


@dataclass(frozen=True)
class ThemeComposition:
    """Represents a mix of theme components ready to be saved or applied."""

    name: str
    gtk3: str | None = None
    gtk4: str | None = None
    shell: str | None = None
    icon: str | None = None
    cursor: str | None = None
    color_scheme: str | None = None
    description: str = ""
    user_composed: bool = True

    def to_theme_set(self) -> ThemeSet:
        """Convert composition into a domain ThemeSet.

        Note: GTK theme preference takes gtk4 if specified, otherwise gtk3.
        """
        return ThemeSet(
            gtk_theme=self.gtk4 or self.gtk3,
            icon_theme=self.icon,
            cursor_theme=self.cursor,
            color_scheme=self.color_scheme,
            shell_theme=self.shell,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize composition to dictionary."""
        return {
            "name": self.name,
            "gtk3": self.gtk3,
            "gtk4": self.gtk4,
            "shell": self.shell,
            "icon": self.icon,
            "cursor": self.cursor,
            "color_scheme": self.color_scheme,
            "description": self.description,
            "user_composed": self.user_composed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThemeComposition":
        """Construct ThemeComposition from dictionary."""
        return cls(
            name=str(data.get("name", "")).strip(),
            gtk3=data.get("gtk3"),
            gtk4=data.get("gtk4"),
            shell=data.get("shell"),
            icon=data.get("icon") or data.get("icons"),
            cursor=data.get("cursor") or data.get("cursors"),
            color_scheme=data.get("color_scheme"),
            description=str(data.get("description", "")).strip(),
            user_composed=bool(data.get("user_composed", True)),
        )

    def is_empty(self) -> bool:
        """Check if no components are defined."""
        return not any(
            [
                self.gtk3,
                self.gtk4,
                self.shell,
                self.icon,
                self.cursor,
                self.color_scheme,
            ]
        )


class ThemeMixer:
    """Mixer service for creating and saving ThemeCompositions as Global Themes."""

    def __init__(self, global_theme_manager: GlobalThemeManager | None = None) -> None:
        """Initialize ThemeMixer.

        Args:
            global_theme_manager: Optional GlobalThemeManager instance.
        """
        self._global_theme_manager = global_theme_manager or GlobalThemeManager()

    def mix_and_save(
        self,
        composition: ThemeComposition,
        overwrite: bool = False,
    ) -> GlobalTheme:
        """Save a ThemeComposition as a user Global Theme with origin='user' and user_composed=True.

        Args:
            composition: ThemeComposition data.
            overwrite: If True, overwrite existing user theme with same name.

        Returns:
            Saved GlobalTheme instance.

        Raises:
            ValueError: If composition has an invalid name or is empty.
            FileExistsError: If theme with same name already exists and overwrite is False.
        """
        if not composition.name.strip():
            raise ValueError("Composition name cannot be empty.")
        if composition.is_empty():
            raise ValueError("Cannot save an empty theme composition.")

        theme_set = composition.to_theme_set()
        description = composition.description or "User composed theme"

        global_theme = self._global_theme_manager.save_global_theme(
            name=composition.name,
            theme_set=theme_set,
            description=description,
            overwrite=overwrite,
            user_composed=composition.user_composed,
        )
        logger.info(
            "Theme composition '%s' successfully saved as Global Theme '%s'.",
            composition.name,
            global_theme.id,
        )
        return global_theme
