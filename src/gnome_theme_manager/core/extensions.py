# SPDX-License-Identifier: GPL-3.0-or-later

"""GNOME Shell extensions management module.

Provides inspection and activation of the
'user-theme@gnome-shell-extensions.gcampax.github.com' extension required
to apply GNOME Shell themes.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import UI_PREFS_FILE

logger = logging.getLogger("gnome_theme_manager.core")

USER_THEME_EXTENSION_ID = "user-theme@gnome-shell-extensions.gcampax.github.com"


@dataclass
class UIPrefs:
    """User UI preferences stored in ui_prefs.json."""

    auto_enable_user_theme: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert preferences to dictionary."""
        return {
            "auto_enable_user_theme": self.auto_enable_user_theme,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIPrefs":
        """Load preferences from dictionary."""
        return cls(
            auto_enable_user_theme=bool(data.get("auto_enable_user_theme", False)),
        )


class ExtensionsManager:
    """Manager for GNOME Shell extensions and extension-related UI preferences."""

    def __init__(self, prefs_file: Path | None = None) -> None:
        """Initialize ExtensionsManager.

        Args:
            prefs_file: Optional Path to ui_prefs.json state file.
        """
        self.prefs_file = (
            Path(prefs_file).expanduser() if prefs_file is not None else UI_PREFS_FILE.expanduser()
        )

    def get_prefs(self) -> UIPrefs:
        """Load UI preferences from ui_prefs.json or return defaults."""
        if not self.prefs_file.is_file():
            return UIPrefs()
        try:
            content = self.prefs_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                return UIPrefs.from_dict(data)
        except Exception as err:
            logger.warning("Failed to parse ui_prefs.json: %s", err)
        return UIPrefs()

    def save_prefs(self, prefs: UIPrefs) -> None:
        """Save UI preferences to ui_prefs.json atomically."""
        try:
            self.prefs_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.prefs_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(prefs.to_dict(), f, indent=2)
            temp_file.replace(self.prefs_file)
        except Exception as err:
            logger.error("Failed to save ui_prefs.json: %s", err)

    def set_auto_enable_user_theme(self, enabled: bool) -> None:
        """Update the auto_enable_user_theme preference."""
        prefs = self.get_prefs()
        prefs.auto_enable_user_theme = enabled
        self.save_prefs(prefs)

    def is_user_theme_enabled(self) -> bool:
        """Check if the user-theme extension is enabled on GNOME Shell.

        Returns:
            True if the extension is active/enabled, False otherwise.
        """
        try:
            res = subprocess.run(
                ["gnome-extensions", "list", "--enabled"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                enabled_list = res.stdout.splitlines()
                return USER_THEME_EXTENSION_ID in enabled_list
        except Exception as err:
            logger.warning("Unable to determine extension status via gnome-extensions: %s", err)
        return False

    def enable_user_theme(self) -> bool:
        """Attempt to enable the user-theme extension via 'gnome-extensions enable'.

        Returns:
            True if the command succeeded with exit code 0, False otherwise.
        """
        try:
            res = subprocess.run(
                ["gnome-extensions", "enable", USER_THEME_EXTENSION_ID],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception as err:
            logger.error("Error enabling user-theme extension: %s", err)
        return False
