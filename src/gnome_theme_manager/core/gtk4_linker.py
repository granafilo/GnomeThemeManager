"""Modulo per la gestione dei collegamenti simbolici (symlink) per temi GTK4 / Libadwaita.

Nelle versioni recenti di GNOME (42+ su Ubuntu 22.04 e 24.04), le applicazioni
moderne basate su GTK4 e Libadwaita non seguono più la chiave GSettings 'gtk-theme'.
Per applicare un tema personalizzato a queste applicazioni, occorre creare dei
collegamenti simbolici (symlink) nella directory di configurazione utente `~/.config/gtk-4.0/`.
"""

import shutil
from pathlib import Path

from .constants import GTK4_CONFIG_DIR


class GTK4ThemeLinker:
    """Gestisce la creazione e rimozione sicura dei symlink per temi GTK4 / Libadwaita."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Inizializza il linker GTK4.

        Args:
            config_dir: Directory di destinazione per la configurazione GTK4
                        (default: ~/.config/gtk-4.0).
        """
        self.config_dir = config_dir if config_dir is not None else GTK4_CONFIG_DIR

    def apply_override(self, theme_path: Path) -> bool:
        """Applica l'override GTK4 collegando i file CSS e gli assets del tema in ~/.config/gtk-4.0/.

        Cerca prima una cartella 'gtk-4.0' nel tema; se non presente, controlla 'gtk-3.0' come fallback.

        Args:
            theme_path: Il percorso assoluto della cartella del tema (es. /usr/share/themes/Nordic).

        Returns:
            True se l'override è stato applicato con successo, False se il tema non contiene file CSS compatibili.
        """
        # 1. Individua la cartella GTK appropriata all'interno del tema
        gtk4_source = theme_path / "gtk-4.0"
        gtk3_source = theme_path / "gtk-3.0"

        source_dir: Path | None = None
        if gtk4_source.is_dir() and (gtk4_source / "gtk.css").exists():
            source_dir = gtk4_source
        elif gtk3_source.is_dir() and (gtk3_source / "gtk.css").exists():
            source_dir = gtk3_source

        if source_dir is None:
            return False

        # 2. Crea la directory di configurazione utente se non esiste
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 3. Collega gtk.css
        source_css = source_dir / "gtk.css"
        target_css = self.config_dir / "gtk.css"
        self._safe_symlink(source_css, target_css)

        # Collega anche gtk-dark.css se presente nel tema
        source_dark_css = source_dir / "gtk-dark.css"
        target_dark_css = self.config_dir / "gtk-dark.css"
        if source_dark_css.exists():
            self._safe_symlink(source_dark_css, target_dark_css)
        elif target_dark_css.is_symlink() or target_dark_css.exists():
            self._safe_remove(target_dark_css)

        # 4. Collega la cartella 'assets' se presente
        source_assets = source_dir / "assets"
        target_assets = self.config_dir / "assets"
        if source_assets.exists():
            self._safe_symlink(source_assets, target_assets)
        elif target_assets.is_symlink() or target_assets.exists():
            self._safe_remove(target_assets)

        return True

    def remove_override(self) -> None:
        """Rimuove i collegamenti simbolici in ~/.config/gtk-4.0/, ripristinando il tema predefinito."""
        target_css = self.config_dir / "gtk.css"
        target_dark_css = self.config_dir / "gtk-dark.css"
        target_assets = self.config_dir / "assets"

        self._safe_remove(target_css)
        self._safe_remove(target_dark_css)
        self._safe_remove(target_assets)

    # -------------------------------------------------------------------------
    # Metodi di Supporto per Symlink Sicuri
    # -------------------------------------------------------------------------

    def _safe_symlink(self, source: Path, target: Path) -> None:
        """Crea un symlink in modo sicuro, rimuovendo un file o link precedente se presente."""
        self._safe_remove(target)
        try:
            target.symlink_to(source.resolve())
        except OSError:
            # Fallback nel caso in cui i symlink non siano consentiti: copia del file
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)

    @staticmethod
    def _safe_remove(path: Path) -> None:
        """Rimuove un file, symlink o directory in modo sicuro."""
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
