# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo Facade principale per l'orchestrazione delle operazioni sui temi in GNOME.

La classe `ThemeManager` implementa il Facade Pattern, costituendo il punto di ingresso
unico e ad alto livello per consumare tutte le funzionalità del package core:
- Scansione e rilevamento dei temi sul filesystem (`ThemeScanner`)
- Lettura e scrittura delle impostazioni dconf/GSettings (`GSettingsClient`)
- Override symlink per applicazioni moderne GTK4 / Libadwaita (`GTK4ThemeLinker`)
- Estrazione sicura e installazione di archivi di temi (`ThemeInstaller`)
- Salvataggio e gestione di profili e preset (`PresetManager`)
"""

import logging
from pathlib import Path

from .constants import GSETTINGS_COLOR_SCHEMES, GSETTINGS_KEY_COLOR_SCHEME
from .errors import GSettingsUnavailableError, ThemeNotFoundError
from .gsettings import GSettingsClient
from .gtk4_linker import GTK4ThemeLinker
from .installer import ThemeInstaller
from .models import (
    ApplyResult,
    PropagationResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from .presets import PresetManager
from .sandbox_bridge import SandboxBridge
from .scanner import ThemeScanner

logger = logging.getLogger("gnome_theme_manager.core")


class ThemeManager:
    """Classe Facade di coordinamento per tutte le operazioni sui temi di GNOME.

    Astrae e disaccoppia la complessità dei singoli sottosistemi (GSettings, Filesystem,
    Linker, Installer, Presets, SandboxBridge) fornendo un'API pulita, priva di dipendenze UI,
    altamente testabile con iniezione opzionale delle dipendenze.
    """

    def __init__(
        self,
        scanner: ThemeScanner | None = None,
        gsettings: GSettingsClient | None = None,
        gtk4_linker: GTK4ThemeLinker | None = None,
        installer: ThemeInstaller | None = None,
        presets: PresetManager | None = None,
        sandbox_bridge: SandboxBridge | None = None,
    ) -> None:
        """Inizializza il coordinatore Facade con iniezione opzionale dei componenti.

        Args:
            scanner: Istanza custom di ThemeScanner (opzionale).
            gsettings: Istanza custom o mock di GSettingsClient (opzionale).
            gtk4_linker: Istanza custom di GTK4ThemeLinker (opzionale).
            installer: Istanza custom di ThemeInstaller (opzionale).
            presets: Istanza custom di PresetManager (opzionale).
            sandbox_bridge: Istanza custom di SandboxBridge (opzionale).
        """
        self._scanner = scanner or ThemeScanner()
        self._gtk4_linker = gtk4_linker or GTK4ThemeLinker()
        self._installer = installer or ThemeInstaller()
        self._presets = presets or PresetManager()
        self._sandbox = sandbox_bridge or SandboxBridge()

        # Inizializzazione protetta di GSettingsClient
        if gsettings is not None:
            self._gsettings: GSettingsClient | None = gsettings
        else:
            try:
                self._gsettings = GSettingsClient()
            except GSettingsUnavailableError as err:
                logger.warning("GSettingsClient non inizializzabile: %s", err)
                self._gsettings = None

    @property
    def scanner(self) -> ThemeScanner:
        """Restituisce lo scanner dei temi associato."""
        return self._scanner

    @property
    def gsettings(self) -> GSettingsClient | None:
        """Restituisce il client GSettings associato (None se non disponibile)."""
        return self._gsettings

    @property
    def gtk4_linker(self) -> GTK4ThemeLinker:
        """Restituisce il gestore dei collegamenti GTK4 associato."""
        return self._gtk4_linker

    @property
    def installer(self) -> ThemeInstaller:
        """Restituisce l'installer dei temi associato."""
        return self._installer

    @property
    def presets(self) -> PresetManager:
        """Restituisce il gestore dei preset associato."""
        return self._presets

    @property
    def sandbox(self) -> SandboxBridge:
        """Restituisce il bridge sandbox associato."""
        return self._sandbox

    def _ensure_gsettings(self) -> GSettingsClient:
        """Verifica la disponibilità di GSettingsClient e lo restituisce.

        Raises:
            GSettingsUnavailableError: Se GSettings non è disponibile nell'ambiente corrente.
        """
        if self._gsettings is None:
            raise GSettingsUnavailableError(
                "GSettings non è disponibile in questo ambiente. "
                "Assicurati di eseguire su GNOME e che PyGObject (Gio) sia installato."
            )
        return self._gsettings

    # -------------------------------------------------------------------------
    # Interrogazione e Diagnostica di Sistema
    # -------------------------------------------------------------------------

    def get_current_themes(self) -> ThemeSet:
        """Recupera la configurazione dei temi attualmente attivi sul desktop GNOME.

        Returns:
            Istanza di ThemeSet con i valori correnti.

        Raises:
            GSettingsUnavailableError: Se GSettings non è disponibile.
        """
        client = self._ensure_gsettings()
        current = client.get_current()
        logger.debug("Recuperati temi attivi: %s", current)
        return current

    def get_system_status(self) -> SystemStatus:
        """Verifica e restituisce la compatibilità e lo stato dell'ambiente desktop corrente.

        Returns:
            Istanza di SystemStatus con informazioni su GSettings, estensioni, percorsi e sandbox.
        """
        gsettings_avail = self._gsettings is not None
        shell_supported = bool(self._gsettings and self._gsettings.is_shell_theme_supported)

        color_scheme_supported = False
        if (
            self._gsettings
            and hasattr(self._gsettings, "_has_key")
            and hasattr(self._gsettings, "_settings")
        ):
            color_scheme_supported = self._gsettings._has_key(
                self._gsettings._settings, GSETTINGS_KEY_COLOR_SCHEME
            )

        sandbox_stat = self._sandbox.get_sandbox_status()
        gtk4_override_stat = self._gtk4_linker.is_override_active()

        return SystemStatus(
            gsettings_available=gsettings_avail,
            shell_theme_supported=shell_supported,
            color_scheme_supported=color_scheme_supported,
            user_themes_path=self._installer.user_themes_dir,
            user_icons_path=self._installer.user_icons_dir,
            sandbox_status=sandbox_stat,
            gtk4_override_active=gtk4_override_stat,
        )

    def get_sandbox_status(self) -> SandboxStatus:
        """Restituisce lo stato diagnostico dei runtime sandbox (Flatpak e Snap).

        Returns:
            Istanza di SandboxStatus con i dettagli di disponibilità e override.
        """
        return self._sandbox.get_sandbox_status()

    def propagate_sandbox(
        self,
        gtk_theme: str | None = None,
        icon_theme: str | None = None,
    ) -> PropagationResult:
        """Propaga i temi attivi (o specificati) agli ambienti sandbox Flatpak e Snap.

        Non esegue operazioni con privilegi elevati né installa pacchetti automaticamente.
        Concede permessi di filesystem per Flatpak e verifica la compatibilità per Snap.

        Args:
            gtk_theme: Nome opzionale del tema GTK (se None, tenta di usare quello attivo).
            icon_theme: Nome opzionale del tema icone (se None, tenta di usare quello attivo).

        Returns:
            Istanza di PropagationResult con messaggi, esiti e avvisi.
        """
        if gtk_theme is None or icon_theme is None:
            try:
                current = self.get_current_themes()
                gtk_theme = gtk_theme or current.gtk_theme
                icon_theme = icon_theme or current.icon_theme
            except GSettingsUnavailableError:
                logger.debug(
                    "GSettings non disponibile per determinare i temi attivi durante la propagazione sandbox."
                )

        return self._sandbox.propagate_all(gtk_theme=gtk_theme, icon_theme=icon_theme)

    def list_themes(
        self,
        theme_type: ThemeType | None = None,
        user_only: bool = False,
    ) -> list[Theme]:
        """Elenca i temi installati sul sistema, con opzioni di filtro.

        Args:
            theme_type: Filtra per tipologia specifica (GTK, ICON, CURSOR, SHELL) o None per tutti.
            user_only: Se True, include solo i temi installati nella home utente.

        Returns:
            Lista ordinata di oggetti Theme trovati.
        """
        themes: list[Theme]
        if theme_type == ThemeType.GTK:
            themes = self._scanner.scan_gtk_themes(user_only=user_only)
        elif theme_type == ThemeType.ICON:
            themes = self._scanner.scan_icon_themes(user_only=user_only)
        elif theme_type == ThemeType.CURSOR:
            themes = self._scanner.scan_cursor_themes(user_only=user_only)
        elif theme_type == ThemeType.SHELL:
            themes = self._scanner.scan_shell_themes(user_only=user_only)
        else:
            themes = self._scanner.scan_all(user_only=user_only)

        return sorted(themes, key=lambda t: (t.theme_type.value, t.name.lower()))

    def find_theme(self, name: str, theme_type: ThemeType) -> Theme | None:
        """Cerca un tema specifico per nome e tipologia nel filesystem.

        Args:
            name: Nome del tema cercato.
            theme_type: Tipologia del tema.

        Returns:
            L'oggetto Theme corrispondente o None se non trovato.
        """
        return self._scanner.find_theme(name=name, theme_type=theme_type)

    # -------------------------------------------------------------------------
    # Applicazione Temi e Preset
    # -------------------------------------------------------------------------

    def apply_themes(
        self,
        theme_set: ThemeSet,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Valida e applica un insieme di temi al desktop GNOME.

        Verifica l'esistenza fisica dei temi prima di modificare GSettings, applica
        opzionalmente i symlink per GTK4 / Libadwaita e propaga la configurazione
        alle applicazioni Snap e Flatpak (solo se è specificato un tema GTK o icone).

        Args:
            theme_set: Insieme di temi da applicare.
            apply_gtk4_override: Se True, applica i symlink in ~/.config/gtk-4.0 per temi GTK.
            propagate_sandbox: Se True, propaga i temi GTK/icone alle app Flatpak e Snap.

        Returns:
            ApplyResult contenente i dettagli dei componenti applicati e gli eventuali warning.

        Raises:
            ThemeNotFoundError: Se uno dei temi specificati non esiste sul filesystem.
            ValueError: Se lo schema colore non è supportato.
            GSettingsUnavailableError: Se GSettings non è disponibile.
        """
        logger.info(
            "Richiesta applicazione temi: %s (gtk4_override=%s, propagate_sandbox=%s)",
            theme_set,
            apply_gtk4_override,
            propagate_sandbox,
        )
        client = self._ensure_gsettings()
        warnings: list[str] = []

        # 1. Validazione preventiva dell'esistenza dei temi sul filesystem
        found_gtk: Theme | None = None
        if theme_set.gtk_theme is not None:
            found_gtk = self._scanner.find_theme(theme_set.gtk_theme, ThemeType.GTK)
            if not found_gtk:
                raise ThemeNotFoundError(
                    f"Il tema GTK '{theme_set.gtk_theme}' non è stato trovato nel sistema."
                )

        if theme_set.icon_theme is not None:
            found_icon = self._scanner.find_theme(theme_set.icon_theme, ThemeType.ICON)
            if not found_icon:
                raise ThemeNotFoundError(
                    f"Il tema icone '{theme_set.icon_theme}' non è stato trovato nel sistema."
                )

        if theme_set.cursor_theme is not None:
            found_cursor = self._scanner.find_theme(theme_set.cursor_theme, ThemeType.CURSOR)
            if not found_cursor:
                raise ThemeNotFoundError(
                    f"Il tema cursori '{theme_set.cursor_theme}' non è stato trovato nel sistema."
                )

        found_shell: Theme | None = None
        if theme_set.shell_theme is not None:
            found_shell = self._scanner.find_theme(theme_set.shell_theme, ThemeType.SHELL)
            if not found_shell:
                raise ThemeNotFoundError(
                    f"Il tema GNOME Shell '{theme_set.shell_theme}' non è stato trovato nel sistema."
                )

        # 2. Validazione schema colore
        if (
            theme_set.color_scheme is not None
            and theme_set.color_scheme not in GSETTINGS_COLOR_SCHEMES
        ):
            raise ValueError(
                f"Schema colore '{theme_set.color_scheme}' non valido. Valori ammessi: {list(GSETTINGS_COLOR_SCHEMES)}"
            )

        # 3. Controllo supporto tema Shell
        shell_to_apply = theme_set.shell_theme
        if shell_to_apply is not None and not client.is_shell_theme_supported:
            warning_msg = (
                "Impossibile applicare il tema GNOME Shell: l'estensione 'User Themes' "
                "(schema org.gnome.shell.extensions.user-theme) non è installata o attiva."
            )
            logger.warning(warning_msg)
            warnings.append(warning_msg)
            shell_to_apply = None

        # 4. Applicazione tramite GSettings
        target_set = ThemeSet(
            gtk_theme=theme_set.gtk_theme,
            icon_theme=theme_set.icon_theme,
            cursor_theme=theme_set.cursor_theme,
            color_scheme=theme_set.color_scheme,
            shell_theme=shell_to_apply,
        )
        client.apply(target_set)

        # 5. Applicazione override GTK4 / Libadwaita
        gtk4_applied = False
        if found_gtk is not None and apply_gtk4_override:
            gtk4_applied = self._gtk4_linker.apply_override(found_gtk.path)
            if gtk4_applied:
                logger.info("Override GTK4/Libadwaita applicato per '%s'", found_gtk.name)
            else:
                logger.debug(
                    "Nessuna cartella CSS compatibile con GTK4/3 trovata in '%s'", found_gtk.name
                )

        # 6. Propagazione automatica agli ambienti sandbox (Flatpak e Snap)
        propagation_result: PropagationResult | None = None
        if propagate_sandbox and (
            theme_set.gtk_theme is not None or theme_set.icon_theme is not None
        ):
            propagation_result = self._sandbox.propagate_all(
                gtk_theme=theme_set.gtk_theme,
                icon_theme=theme_set.icon_theme,
            )
            if propagation_result.warnings:
                warnings.extend(propagation_result.warnings)

        return ApplyResult(
            gtk_theme=theme_set.gtk_theme,
            gtk4_override_applied=gtk4_applied,
            icon_theme=theme_set.icon_theme,
            cursor_theme=theme_set.cursor_theme,
            shell_theme=shell_to_apply,
            color_scheme=theme_set.color_scheme,
            warnings=warnings,
            sandbox_propagation=propagation_result,
        )

    def apply_unified_theme(
        self,
        theme_name: str,
        color_scheme: str | None = None,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Applica un tema globale unificato (GTK e Shell con lo stesso nome).

        Args:
            theme_name: Nome del tema da cercare come GTK e Shell.
            color_scheme: Schema colore opzionale ('default', 'prefer-dark', 'prefer-light').
            apply_gtk4_override: Se True, applica l'override GTK4 se disponibile.
            propagate_sandbox: Se True, propaga i temi alle app Flatpak e Snap.

        Returns:
            ApplyResult contenente i dettagli dei temi applicati.

        Raises:
            ThemeNotFoundError: Se il tema non esiste né come GTK né come Shell.
        """
        has_gtk = bool(self._scanner.find_theme(theme_name, ThemeType.GTK))
        has_shell = bool(self._scanner.find_theme(theme_name, ThemeType.SHELL))

        if not has_gtk and not has_shell:
            raise ThemeNotFoundError(
                f"Il tema '{theme_name}' non è stato trovato come GTK o GNOME Shell nel sistema."
            )

        theme_set = ThemeSet(
            gtk_theme=theme_name if has_gtk else None,
            shell_theme=theme_name if has_shell else None,
            color_scheme=color_scheme,
        )

        return self.apply_themes(
            theme_set,
            apply_gtk4_override=apply_gtk4_override,
            propagate_sandbox=propagate_sandbox,
        )

    def apply_preset(
        self,
        preset_name: str,
        apply_gtk4_override: bool = True,
        propagate_sandbox: bool = True,
    ) -> ApplyResult:
        """Carica e applica un preset memorizzato.

        Args:
            preset_name: Nome identificativo del preset salvato.
            apply_gtk4_override: Se True, applica l'override GTK4 per il tema GTK del preset.
            propagate_sandbox: Se True, propaga i temi alle app Flatpak e Snap.

        Returns:
            ApplyResult con l'esito dell'applicazione.

        Raises:
            FileNotFoundError: Se il preset non esiste.
            ThemeNotFoundError: Se uno dei temi definiti nel preset non è installato.
        """
        theme_set = self._presets.load_preset(preset_name)
        logger.info("Applicazione preset '%s': %s", preset_name, theme_set)
        return self.apply_themes(
            theme_set,
            apply_gtk4_override=apply_gtk4_override,
            propagate_sandbox=propagate_sandbox,
        )

    # -------------------------------------------------------------------------
    # Gestione Preset / Profili
    # -------------------------------------------------------------------------

    def save_current_as_preset(self, name: str, overwrite: bool = False) -> Path:
        """Salva lo stato corrente dei temi del desktop come preset riutilizzabile.

        Args:
            name: Nome identificativo del preset.
            overwrite: Se True, sovrascrive un preset esistente con lo stesso nome.

        Returns:
            Il percorso Path del file JSON creato.

        Raises:
            FileExistsError: Se il preset esiste già e overwrite=False.
        """
        current_set = self.get_current_themes()
        return self._presets.save_preset(name, current_set, overwrite=overwrite)

    def load_preset(self, name: str) -> ThemeSet:
        """Carica un preset memorizzato restituendo il set di temi associato.

        Args:
            name: Nome del preset da caricare.

        Returns:
            L'istanza di ThemeSet corrispondente.

        Raises:
            ValueError: Se il nome del preset non è valido.
            FileNotFoundError: Se il preset non esiste.
        """
        return self._presets.load_preset(name)

    def list_presets(self) -> list[str]:
        """Restituisce l'elenco dei preset disponibili ordinati alfabeticamente."""
        return self._presets.list_presets()

    def delete_preset(self, name: str) -> bool:
        """Elimina un preset esistente.

        Args:
            name: Nome del preset da rimuovere.

        Returns:
            True se il preset è stato rimosso.

        Raises:
            FileNotFoundError: Se il preset non esiste.
        """
        return self._presets.delete_preset(name)

    # -------------------------------------------------------------------------
    # Installazione e Disinstallazione Temi da Cartelle o Archivi
    # -------------------------------------------------------------------------

    def inspect_theme_source(self, source_path: Path) -> list[tuple[str, ThemeType]]:
        """Ispeziona una sorgente locale (archivio o cartella) rilevando temi e componenti.

        Non modifica la sorgente originale e non esegue alcuna installazione sul sistema.

        Args:
            source_path: Percorso del file archivio o della cartella da analizzare.

        Returns:
            Lista di tuple (nome_tema, tipo_tema) per ciascun componente identificato.

        Raises:
            FileNotFoundError: Se source_path non esiste.
            ArchiveExtractionError: Se l'archivio è corrotto o non supportato.
            ThemeValidationError: Se non viene rilevata alcuna struttura di tema valida.
        """
        logger.info("Ispezione sorgente tema richiesta: %s", source_path)
        results = self._installer.inspect_source(source_path=Path(source_path))
        return [(name, t_type) for name, _, t_type in results]

    def install_theme_directory(
        self,
        directory_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
    ) -> list[Theme]:
        """Installa temi da una cartella locale nelle directory utente (~/.local/share/...).

        Non modifica, non sposta e non elimina la cartella sorgente originale.

        Args:
            directory_path: Percorso della cartella del tema.
            theme_type: Tipologia opzionale per filtrare l'installazione.
            custom_name: Nome personalizzato per la cartella di destinazione.
            overwrite: Se True, sovrascrive eventuali cartelle preesistenti.

        Returns:
            Lista delle istanze Theme installate con successo nelle directory utente.
        """
        logger.info("Installazione cartella tema richiesta: %s", directory_path)
        return self._installer.install_directory(
            directory_path=Path(directory_path),
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
        )

    def install_theme_archive(
        self,
        archive_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
    ) -> list[Theme]:
        """Estrae, valida e installa temi da un archivio compresso (.zip, .tar.*).

        Args:
            archive_path: Percorso del file archivio da installare.
            theme_type: Tipologia opzionale per filtrare l'installazione.
            custom_name: Nome personalizzato per la cartella di destinazione.
            overwrite: Se True, sovrascrive eventuali cartelle preesistenti.

        Returns:
            Lista delle istanze Theme installate con successo nelle directory utente.
        """
        logger.info("Installazione archivio richiesta: %s", archive_path)
        return self._installer.install(
            archive_path=Path(archive_path),
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
        )

    def install_theme(
        self,
        source_path: Path,
        theme_type: ThemeType | None = None,
        custom_name: str | None = None,
        overwrite: bool = False,
    ) -> list[Theme]:
        """Installa uno o più temi da una sorgente locale (cartella o archivio).

        Riconosce automaticamente se la sorgente è una directory o un file archivio.

        Args:
            source_path: Percorso del file archivio o della cartella del tema.
            theme_type: Tipologia opzionale per filtrare l'installazione.
            custom_name: Nome personalizzato per la cartella di destinazione.
            overwrite: Se True, sovrascrive eventuali cartelle preesistenti.

        Returns:
            Lista delle istanze Theme installate con successo nelle directory utente.
        """
        logger.info("Installazione tema richiesta da sorgente: %s", source_path)
        return self._installer.install(
            archive_path=Path(source_path),
            theme_type=theme_type,
            custom_name=custom_name,
            overwrite=overwrite,
        )

    def uninstall_theme(self, name: str, theme_type: ThemeType) -> bool:
        """Disinstalla un tema specifico dalle cartelle utente.

        Args:
            name: Nome della directory del tema da disinstallare.
            theme_type: Tipologia del tema.

        Returns:
            True se il tema è stato rimosso con successo.

        Raises:
            ThemeNotFoundError: Se il tema non è presente nelle cartelle utente.
        """
        logger.info("Disinstallazione tema richiesta: '%s' (%s)", name, theme_type)
        return self._installer.uninstall(theme_name=name, theme_type=theme_type)
