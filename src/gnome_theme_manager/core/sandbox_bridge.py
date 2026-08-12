"""Modulo per la propagazione automatica dei temi GNOME alle applicazioni sandboxate.

Nelle distribuzioni Linux moderne (in particolare Ubuntu), molte applicazioni (come
Firefox, Chromium, App Center) vengono eseguite all'interno di ambienti isolati
(sandbox) gestiti da Flatpak o Snap.

Quando un utente installa un tema personalizzato in directory utente come:
  - ~/.local/share/themes/ oppure ~/.themes/
  - ~/.local/share/icons/ oppure ~/.icons/

le applicazioni sandbox non hanno i permessi di lettura per accedere a tali percorsi.
Questo modulo fornisce `SandboxBridge`, che:
1. Concede a Flatpak i permessi di lettura (read-only) sulle cartelle dei temi e imposta
   le variabili d'ambiente GTK_THEME e ICON_THEME a livello utente (`--user`).
2. Verifica la presenza di `gtk-common-themes` su Snap e notifica l'utente se un tema
   personalizzato richiede un pacchetto snap dedicato.
3. Opera interamente senza richiedere permessi root o comandi con `sudo`.
"""

import logging
import shutil
import subprocess

from .models import PropagationResult, SandboxStatus

logger = logging.getLogger("gnome_theme_manager.core")

# Elenco dei temi GTK inclusi nel pacchetto standard Snap gtk-common-themes
# (usato per verificare se il tema attivo è supportato senza snap aggiuntivi)
KNOWN_SNAP_COMMON_THEMES: frozenset[str] = frozenset({
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
})


class SandboxBridge:
    """Propaga i temi GNOME alle applicazioni sandboxate gestite da Snap e Flatpak."""

    def __init__(self) -> None:
        """Inizializza il bridge sandbox."""
        logger.debug("Inizializzazione SandboxBridge per Snap e Flatpak")

    def is_snap_available(self) -> bool:
        """Controlla se il comando `snap` è installato e disponibile nel sistema ($PATH).

        Returns:
            True se il binario snap è presente, False altrimenti.
        """
        available = shutil.which("snap") is not None
        logger.debug("Verifica disponibilità Snap: %s", available)
        return available

    def is_flatpak_available(self) -> bool:
        """Controlla se il comando `flatpak` è installato e disponibile nel sistema ($PATH).

        Returns:
            True se il binario flatpak è presente, False altrimenti.
        """
        available = shutil.which("flatpak") is not None
        logger.debug("Verifica disponibilità Flatpak: %s", available)
        return available

    def get_sandbox_status(self) -> SandboxStatus:
        """Recupera lo stato diagnostico dei runtime sandbox rilevati sul sistema.

        Verifica se i comandi snap e flatpak sono disponibili, se lo snap gtk-common-themes
        è installato e se gli override filesystem per Flatpak sono già attivi.

        Returns:
            Istanza di SandboxStatus contenente i dati diagnostici.
        """
        snap_avail = self.is_snap_available()
        flatpak_avail = self.is_flatpak_available()
        snap_gtk_common_installed = False
        flatpak_override_active = False

        # 1. Verifica snap gtk-common-themes
        if snap_avail:
            try:
                res = subprocess.run(
                    ["snap", "list", "gtk-common-themes"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                snap_gtk_common_installed = (res.returncode == 0)
            except (subprocess.SubprocessError, FileNotFoundError, OSError) as err:
                logger.debug("Impossibile verificare snap list gtk-common-themes: %s", err)
                snap_gtk_common_installed = False

        # 2. Verifica override globale utente di Flatpak
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
                flatpak_override_active = (
                    res.returncode == 0
                    and ("themes" in out_lower or "icons" in out_lower)
                )
            except (subprocess.SubprocessError, FileNotFoundError, OSError) as err:
                logger.debug("Impossibile verificare flatpak override --show: %s", err)
                flatpak_override_active = False

        return SandboxStatus(
            snap_available=snap_avail,
            flatpak_available=flatpak_avail,
            snap_gtk_common_themes_installed=snap_gtk_common_installed,
            flatpak_filesystem_override_active=flatpak_override_active,
        )

    def propagate_to_flatpak(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Configura le autorizzazioni di filesystem e le variabili d'ambiente per Flatpak.

        Esegue comandi `flatpak override --user` per concedere l'accesso in sola lettura
        alle cartelle temi e icone utente, e imposta le variabili GTK_THEME e ICON_THEME.

        Args:
            gtk_theme: Nome del tema GTK da impostare (opzionale).
            icon_theme: Nome del tema icone da impostare (opzionale).

        Returns:
            PropagationResult con l'esito delle operazioni e gli eventuali avvisi.
        """
        if not self.is_flatpak_available():
            logger.debug("Flatpak non disponibile nel sistema, propagazione saltata.")
            return PropagationResult(
                flatpak_success=False,
                flatpak_messages=["Flatpak non è installato sul sistema."],
            )

        commands: list[list[str]] = [
            ["flatpak", "override", "--user", "--filesystem=~/.local/share/themes:ro"],
            ["flatpak", "override", "--user", "--filesystem=~/.themes:ro"],
            ["flatpak", "override", "--user", "--filesystem=~/.local/share/icons:ro"],
            ["flatpak", "override", "--user", "--filesystem=~/.icons:ro"],
        ]

        if gtk_theme:
            commands.append(["flatpak", "override", "--user", f"--env=GTK_THEME={gtk_theme}"])
        if icon_theme:
            commands.append(["flatpak", "override", "--user", f"--env=ICON_THEME={icon_theme}"])

        messages: list[str] = []
        warnings: list[str] = []
        has_error = False

        for cmd in commands:
            cmd_str = " ".join(cmd)
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                logger.debug("Comando Flatpak completato: %s", cmd_str)
            except subprocess.TimeoutExpired:
                warn_msg = f"Timeout durante l'esecuzione del comando Flatpak: {cmd_str}"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                has_error = True
            except subprocess.CalledProcessError as err:
                err_msg = err.stderr.strip() if err.stderr else str(err)
                warn_msg = f"Errore durante l'override Flatpak ({cmd_str}): {err_msg}"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                has_error = True
            except (FileNotFoundError, OSError) as err:
                warn_msg = f"Impossibile eseguire il comando Flatpak ({cmd_str}): {err}"
                logger.warning(warn_msg)
                warnings.append(warn_msg)
                has_error = True

        if not has_error:
            messages.append("Override filesystem e variabili d'ambiente Flatpak configurati con successo.")

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

        Controlla se lo snap `gtk-common-themes` è installato nel sistema.
        Se il tema attivo non è compreso tra quelli standard, notifica l'utente con
        un avviso descrittivo e suggerisce l'installazione del relativo snap.

        Args:
            gtk_theme: Nome del tema GTK applicato (opzionale).
            icon_theme: Nome del tema icone applicato (opzionale).

        Returns:
            PropagationResult con l'esito della verifica e gli avvisi informativi.
        """
        if not self.is_snap_available():
            logger.debug("Snap non disponibile nel sistema, verifica saltata.")
            return PropagationResult(
                snap_success=False,
                snap_messages=["Snap non è installato sul sistema."],
            )

        messages: list[str] = []
        warnings: list[str] = []

        gtk_common_installed = False
        try:
            res = subprocess.run(
                ["snap", "list", "gtk-common-themes"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            gtk_common_installed = (res.returncode == 0)
        except subprocess.TimeoutExpired:
            warn_msg = "Timeout durante l'interrogazione dello snap 'gtk-common-themes'."
            logger.warning(warn_msg)
            warnings.append(warn_msg)
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as err:
            warn_msg = f"Errore durante l'interrogazione di Snap: {err}"
            logger.warning(warn_msg)
            warnings.append(warn_msg)

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

        # Se gtk-common-themes è installato, verifichiamo la compatibilità del tema specifico
        if gtk_theme:
            theme_norm = gtk_theme.strip().lower()
            if theme_norm in KNOWN_SNAP_COMMON_THEMES:
                messages.append(f"Il tema '{gtk_theme}' è supportato nativamente da gtk-common-themes in Snap.")
            else:
                warn_msg = (
                    f"Il tema personalizzato '{gtk_theme}' non è incluso nel pacchetto standard "
                    f"'gtk-common-themes' di Snap. Alcune app Snap potrebbero mostrare il tema predefinito. "
                    f"Se disponibile, puoi installare lo snap dedicato (es. 'snap install {theme_norm}-themes')."
                )
                logger.info(warn_msg)
                warnings.append(warn_msg)
                messages.append(f"Tema '{gtk_theme}' personalizzato (non incluso in gtk-common-themes).")
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
        """Esegue la propagazione dei temi a entrambi gli ambienti sandbox (Flatpak e Snap).

        Args:
            gtk_theme: Nome del tema GTK da propagare.
            icon_theme: Nome del tema icone da propagare.

        Returns:
            Istanza consolidata di PropagationResult contenente i messaggi e avvisi aggregati.
        """
        logger.info("Avvio propagazione temi a Snap e Flatpak (gtk=%s, icon=%s)", gtk_theme, icon_theme)
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
