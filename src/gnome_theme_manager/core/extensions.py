# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo per la gestione delle estensioni di GNOME Shell.

Fornisce il controllo dello stato di attivazione e l'abilitazione programmata dell'estensione
'user-theme@gnome-shell-extensions.gcampax.github.com' necessaria per l'applicazione
dei temi GNOME Shell.
"""

import logging
import subprocess

logger = logging.getLogger("gnome_theme_manager.core")

USER_THEME_EXTENSION_ID = "user-theme@gnome-shell-extensions.gcampax.github.com"


class ExtensionsManager:
    """Gestore delle estensioni GNOME Shell."""

    def is_user_theme_enabled(self) -> bool:
        """Controlla se l'estensione user-theme è abilitata su GNOME Shell.

        Returns:
            True se l'estensione è attiva/abilitata, False altrimenti.
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
            logger.warning(
                "Impossibile determinare lo stato dell'estensione tramite gnome-extensions: %s", err
            )
        return False

    def enable_user_theme(self) -> bool:
        """Tenta di abilitare l'estensione user-theme via cli 'gnome-extensions enable'.

        Returns:
            True se l'operazione è andata a buon fine con exit code 0, False altrimenti.
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
            logger.error("Errore durante l'abilitazione dell'estensione user-theme: %s", err)
        return False
