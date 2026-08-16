# SPDX-License-Identifier: GPL-3.0-or-later

"""GNOME Shell extensions management module.

Provides inspection and activation of the
'user-theme@gnome-shell-extensions.gcampax.github.com' extension required
to apply GNOME Shell themes.
"""

import logging
import subprocess

logger = logging.getLogger("gnome_theme_manager.core")

USER_THEME_EXTENSION_ID = "user-theme@gnome-shell-extensions.gcampax.github.com"


class ExtensionsManager:
    """Manager for GNOME Shell extensions."""

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
