# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo per la propagazione automatica dei temi GNOME alle applicazioni sandboxate.

Nelle distribuzioni Linux moderne (in particolare Ubuntu), molte applicazioni (come
Firefox, Chromium, App Center) vengono eseguite all'interno di ambienti isolati
(sandbox) gestiti da Flatpak o Snap.
"""

import logging
import shutil
import subprocess

from .errors import ThemeValidationError
from .models import PropagationResult, SandboxStatus

logger = logging.getLogger("gnome_theme_manager.core")

KNOWN_SNAP_COMMON_THEMES: frozenset[str] = frozenset(
    {
        "adwaita",
        "adwaita-dark",
        "ambiance",
        "communitheme",
        "highcontrast",
        "highcontrastinverse",
        "mate",
        "mint-y",
        "mint-y-dark",
        "radiance",
        "yaru",
        "yaru-dark",
        "yaru-light",
        "yaru-bark",
        "yaru-bark-dark",
        "yaru-magenta",
        "yaru-magenta-dark",
        "yaru-olive",
        "yaru-olive-dark",
        "yaru-prussiangreen",
        "yaru-prussiangreen-dark",
        "yaru-purple",
        "yaru-purple-dark",
        "yaru-red",
        "yaru-red-dark",
        "yaru-sage",
        "yaru-sage-dark",
        "yaru-viridian",
        "yaru-viridian-dark",
    }
)


def validate_theme_name(name: str) -> str:
    """Valida la forma del nome del tema secondo le linee guida di sicurezza."""
    if not name:
        raise ThemeValidationError("Il nome del tema non può essere vuoto.")
    if "/" in name or "\\" in name:
        raise ThemeValidationError("Il nome del tema non può contenere barre o barre rovesciate.")
    if "\n" in name or "\r" in name:
        raise ThemeValidationError("Il nome del tema non può contenere caratteri di nuova riga.")
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ThemeValidationError("Il nome del tema non può contenere caratteri di controllo.")
    if name.startswith("-"):
        raise ThemeValidationError("Il nome del tema non può iniziare con un trattino.")
    return name


class SandboxBridge:
    """Propaga i temi GNOME alle applicazioni sandboxate gestite da Snap e Flatpak."""

    def __init__(self) -> None:
        """Inizializza il bridge sandbox."""
        logger.debug("Inizializzazione SandboxBridge per Snap e Flatpak")

    def is_snap_available(self) -> bool:
        """Controlla se il comando `snap` è installato e disponibile nel sistema ($PATH)."""
        return shutil.which("snap") is not None

    def is_flatpak_available(self) -> bool:
        """Controlla se il comando `flatpak` è installato e disponibile nel sistema ($PATH)."""
        return shutil.which("flatpak") is not None

    def get_sandbox_status(self) -> SandboxStatus:
        """Recupera lo stato diagnostico dei runtime sandbox rilevati sul sistema."""
        snap_avail = self.is_snap_available()
        flatpak_avail = self.is_flatpak_available()
        snap_gtk_common_installed = False
        flatpak_override_active = False

        if snap_avail:
            try:
                res = subprocess.run(
                    ["snap", "list", "gtk-common-themes"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                snap_gtk_common_installed = res.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                snap_gtk_common_installed = False

        if flatpak_avail:
            try:
                res = subprocess.run(
                    ["flatpak", "override", "--user", "--show"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                out_lower = res.stdout.lower()
                flatpak_override_active = res.returncode == 0 and (
                    "themes" in out_lower or "icons" in out_lower
                )
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                flatpak_override_active = False

        return SandboxStatus(
            snap_available=snap_avail,
            flatpak_available=flatpak_avail,
            snap_gtk_common_themes_installed=snap_gtk_common_installed,
            flatpak_filesystem_override_active=flatpak_override_active,
        )

    def build_flatpak_command(
        self,
        app_id: str | None,
        gtk_theme: str | None,
        icon_theme: str | None,
    ) -> list[str]:
        """Costruisce il comando flatpak come lista di argomenti."""
        cmd = ["flatpak", "override", "--user"]
        if gtk_theme:
            cmd.append(f"--env=GTK_THEME={gtk_theme}")
        if icon_theme:
            cmd.append(f"--env=ICON_THEME={icon_theme}")
        if app_id:
            cmd.append(app_id)
        return cmd

    def build_snap_command(
        self,
        app_name: str,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> list[str]:
        """Costruisce il comando snap come lista di argomenti."""
        return ["snap", "list", app_name]

    def propagate_to_flatpak(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Configura le autorizzazioni di filesystem e le variabili d'ambiente per Flatpak.

        Restituisce sempre un PropagationResult (anche in caso di errore dei comandi
        Flatpak o timeout, popolando i warning senza sollevare eccezioni).
        """
        if not self.is_flatpak_available():
            logger.debug("Flatpak non disponibile nel sistema, propagazione saltata.")
            return PropagationResult(
                flatpak_success=False,
                flatpak_messages=["Flatpak non è installato sul sistema."],
            )

        if gtk_theme:
            validate_theme_name(gtk_theme)
        if icon_theme:
            validate_theme_name(icon_theme)

        base_commands: list[list[str]] = [
            ["flatpak", "override", "--user", "--filesystem=~/.local/share/themes:ro"],
            ["flatpak", "override", "--user", "--filesystem=~/.themes:ro"],
            ["flatpak", "override", "--user", "--filesystem=~/.local/share/icons:ro"],
            ["flatpak", "override", "--user", "--filesystem=~/.icons:ro"],
        ]

        if gtk_theme:
            base_commands.append(self.build_flatpak_command(None, gtk_theme, None))
        if icon_theme:
            base_commands.append(self.build_flatpak_command(None, None, icon_theme))

        messages: list[str] = []
        warnings: list[str] = []
        has_error = False

        for cmd in base_commands:
            " ".join(cmd)
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
            except subprocess.TimeoutExpired:
                warn_msg = "Timeout durante l'esecuzione del comando Flatpak."
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                has_error = True
                break
            except subprocess.CalledProcessError as err:
                err_msg = err.stderr.strip() if err.stderr else str(err)
                warn_msg = f"Errore durante l'override Flatpak: {err_msg}"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                has_error = True
                break
            except (FileNotFoundError, OSError):
                warn_msg = "Impossibile eseguire il comando Flatpak."
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                has_error = True
                break

        if not has_error:
            messages.append(
                "Override filesystem e variabili d'ambiente Flatpak configurati con successo."
            )

        return PropagationResult(
            flatpak_success=not has_error,
            flatpak_messages=messages,
            warnings=warnings,
        )

    def propagate_to_snap(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Verifica la compatibilità dei temi con l'infrastruttura Snap.

        Restituisce sempre un PropagationResult (anche in caso di errore dei comandi
        Snap o timeout, popolando i warning senza sollevare eccezioni).
        """
        if not self.is_snap_available():
            logger.debug("Snap non disponibile nel sistema, verifica saltata.")
            return PropagationResult(
                snap_success=False,
                snap_messages=["Snap non è installato sul sistema."],
            )

        if gtk_theme:
            validate_theme_name(gtk_theme)
        if icon_theme:
            validate_theme_name(icon_theme)

        messages: list[str] = []
        warnings: list[str] = []

        gtk_common_installed = False
        cmd = self.build_snap_command("gtk-common-themes")
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            gtk_common_installed = res.returncode == 0
        except subprocess.TimeoutExpired:
            warn_msg = "Timeout durante l'interrogazione dello snap 'gtk-common-themes'."
            logger.warning(warn_msg)
            warnings.append(warn_msg)
            return PropagationResult(
                snap_success=False,
                snap_messages=["Errore durante l'interrogazione di Snap."],
                warnings=warnings,
            )
        except Exception:
            warn_msg = "Errore durante l'interrogazione di Snap."
            logger.warning(warn_msg)
            warnings.append(warn_msg)
            return PropagationResult(
                snap_success=False,
                snap_messages=["Errore durante l'interrogazione di Snap."],
                warnings=warnings,
            )

        if not gtk_common_installed:
            warn_msg = (
                "Lo snap 'gtk-common-themes' non risulta installato. Le applicazioni Snap "
                "potrebbero non visualizzare correttamente il tema grafico scelto."
            )
            logger.info(warn_msg)
            warnings.append(warn_msg)
            return PropagationResult(
                snap_success=False,
                snap_messages=["Lo snap 'gtk-common-themes' non è presente nel sistema."],
                warnings=warnings,
            )

        if gtk_theme:
            theme_norm = gtk_theme.strip().lower()
            if theme_norm in KNOWN_SNAP_COMMON_THEMES:
                messages.append(
                    f"Il tema '{gtk_theme}' è supportato nativamente da gtk-common-themes in Snap."
                )
            else:
                warn_msg = (
                    f"Il tema personalizzato '{gtk_theme}' non è incluso nel pacchetto standard "
                    f"'gtk-common-themes' di Snap. Alcune app Snap potrebbero mostrare il tema predefinito. "
                    f"Se disponibile, puoi installare lo snap dedicato (es. 'snap install {theme_norm}-themes')."
                )
                logger.info(warn_msg)
                warnings.append(warn_msg)
                messages.append(
                    f"Tema '{gtk_theme}' personalizzato (non incluso in gtk-common-themes)."
                )
        else:
            messages.append("Verifica gtk-common-themes di Snap completata con successo.")

        return PropagationResult(
            snap_success=True,
            snap_messages=messages,
            warnings=warnings,
        )

    def propagate_all(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Esegue la propagazione dei temi a entrambi gli ambienti sandbox (Flatpak e Snap)."""
        logger.info(
            "Avvio propagazione temi a Snap e Flatpak (gtk=%s, icon=%s)", gtk_theme, icon_theme
        )

        flatpak_res = self.propagate_to_flatpak(gtk_theme=gtk_theme, icon_theme=icon_theme)
        snap_res = self.propagate_to_snap(gtk_theme=gtk_theme, icon_theme=icon_theme)

        consolidated_warnings = flatpak_res.warnings + snap_res.warnings

        return PropagationResult(
            flatpak_success=flatpak_res.flatpak_success,
            snap_success=snap_res.snap_success,
            flatpak_messages=flatpak_res.flatpak_messages,
            snap_messages=snap_res.snap_messages,
            warnings=consolidated_warnings,
        )
