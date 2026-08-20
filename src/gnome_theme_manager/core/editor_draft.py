# SPDX-License-Identifier: GPL-3.0-or-later

"""Persistent Editor Draft state manager (Task 2.5).

Persists active Theme Editor customization state (components, colors, name) to
`~/.local/state/gnome-theme-manager/editor_draft.json` on changes, and allows
prompting the user to resume an unfinished draft on app restart.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import EDITOR_DRAFT_FILE

logger = logging.getLogger("gnome_theme_manager.core.editor_draft")


@dataclass(frozen=True)
class EditorDraft:
    """Represents a saved Theme Editor draft session."""

    theme_name: str = ""
    gtk_theme: str | None = None
    shell_theme: str | None = None
    icon_theme: str | None = None
    cursor_theme: str | None = None
    color_scheme: str | None = None
    colors: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize draft to dictionary."""
        return {
            "theme_name": self.theme_name,
            "gtk_theme": self.gtk_theme,
            "shell_theme": self.shell_theme,
            "icon_theme": self.icon_theme,
            "cursor_theme": self.cursor_theme,
            "color_scheme": self.color_scheme,
            "colors": dict(self.colors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditorDraft":
        """Construct EditorDraft from dictionary."""
        return cls(
            theme_name=str(data.get("theme_name", "")),
            gtk_theme=data.get("gtk_theme"),
            shell_theme=data.get("shell_theme"),
            icon_theme=data.get("icon_theme"),
            cursor_theme=data.get("cursor_theme"),
            color_scheme=data.get("color_scheme"),
            colors=dict(data.get("colors", {})),
        )

    def is_empty(self) -> bool:
        """Return True if draft has no name, components or colors."""
        return not any(
            [
                self.theme_name.strip(),
                self.gtk_theme,
                self.shell_theme,
                self.icon_theme,
                self.cursor_theme,
                self.color_scheme,
                self.colors,
            ]
        )


class EditorDraftManager:
    """Manages reading, writing and clearing editor_draft.json."""

    def __init__(self, draft_file: Path | None = None) -> None:
        """Initialize EditorDraftManager.

        Args:
            draft_file: Path to editor_draft.json file.
        """
        self._draft_file = draft_file or EDITOR_DRAFT_FILE

    def has_draft(self) -> bool:
        """Return True if a valid non-empty draft exists."""
        draft = self.load_draft()
        return draft is not None and not draft.is_empty()

    def load_draft(self) -> EditorDraft | None:
        """Load EditorDraft from file, returning None if absent or invalid."""
        if not self._draft_file.is_file():
            return None

        try:
            content = self._draft_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                return EditorDraft.from_dict(data)
        except Exception as err:
            logger.warning("Failed to load editor draft from %s: %s", self._draft_file, err)

        return None

    def save_draft(self, draft: EditorDraft) -> None:
        """Save EditorDraft to json file atomically."""
        try:
            self._draft_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self._draft_file.with_suffix(".tmp")
            temp_file.write_text(
                json.dumps(draft.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_file.replace(self._draft_file)
            logger.debug("Saved editor draft to %s", self._draft_file)
        except Exception as err:
            logger.error("Failed to save editor draft to %s: %s", self._draft_file, err)

    def clear_draft(self) -> None:
        """Remove editor_draft.json file."""
        try:
            if self._draft_file.is_file():
                self._draft_file.unlink()
                logger.debug("Cleared editor draft at %s", self._draft_file)
        except Exception as err:
            logger.warning("Failed to clear editor draft at %s: %s", self._draft_file, err)
