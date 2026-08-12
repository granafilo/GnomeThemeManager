"""Modulo per il salvataggio, caricamento ed eliminazione di preset/profili di temi.

I preset consentono di memorizzare istantanee (snapshot) complete delle preferenze
desktop (tema GTK, icone, cursori, GNOME Shell e schema colori) in formato JSON
all'interno della cartella di configurazione utente (~/.config/gnome-theme-manager/presets/).
"""

import json
import logging
import re
from pathlib import Path

from .constants import PRESETS_DIR
from .models import ThemeSet

logger = logging.getLogger("gnome_theme_manager.core")


class PresetManager:
    """Gestore del ciclo di vita dei preset di configurazione per GnomeThemeManager."""

    def __init__(self, presets_dir: Path | None = None) -> None:
        """Inizializza il gestore dei preset.

        Args:
            presets_dir: Directory di memorizzazione dei file JSON dei preset
                         (default: ~/.config/gnome-theme-manager/presets).
        """
        self.presets_dir = (
            Path(presets_dir).expanduser()
            if presets_dir is not None
            else PRESETS_DIR.expanduser()
        )

    def _sanitize_name(self, name: str) -> str:
        """Valida e ripulisce il nome del preset prevenendo Path Traversal.

        Args:
            name: Nome del preset da verificare.

        Returns:
            Nome valido senza spazi superflui.

        Raises:
            ValueError: Se il nome è vuoto o contiene caratteri non validi/separatori di percorso.
        """
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Il nome del preset non può essere vuoto.")

        # Impediamo separatori di percorso o sequenze di risalita directory
        if "/" in cleaned or "\\" in cleaned or ".." in cleaned:
            raise ValueError(f"Nome preset non valido: '{name}'. Non sono ammessi caratteri di percorso.")

        if not re.match(r"^[\w\-. ]+$", cleaned):
            raise ValueError(f"Nome preset '{name}' contiene caratteri non consentiti.")

        return cleaned

    def save_preset(self, name: str, theme_set: ThemeSet, overwrite: bool = False) -> Path:
        """Salva una configurazione ThemeSet come preset JSON.

        Args:
            name: Nome identificativo del preset (es. 'NordicDark', 'MinimalWork').
            theme_set: Istanza di ThemeSet contenente le preferenze da salvare.
            overwrite: Se True, sovrascrive un eventuale preset esistente con lo stesso nome.

        Returns:
            Il percorso Path del file JSON salvato.

        Raises:
            ValueError: Se il nome del preset non è valido o se theme_set è vuoto.
            FileExistsError: Se il preset esiste già e overwrite=False.
        """
        preset_name = self._sanitize_name(name)

        if theme_set.is_empty():
            raise ValueError("Impossibile salvare un preset privo di qualsiasi configurazione.")

        self.presets_dir.mkdir(parents=True, exist_ok=True)
        preset_path = self.presets_dir / f"{preset_name}.json"

        if preset_path.exists() and not overwrite:
            raise FileExistsError(
                f"Il preset '{preset_name}' esiste già in '{preset_path}'. "
                "Specificare overwrite=True per sovrascriverlo."
            )

        data = theme_set.to_dict()
        preset_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        logger.info("Preset salvato con successo: '%s' in %s", preset_name, preset_path)
        return preset_path

    def load_preset(self, name: str) -> ThemeSet:
        """Carica un preset dal file JSON corrispondente.

        Args:
            name: Nome del preset da caricare.

        Returns:
            L'istanza ThemeSet deserializzata dal file.

        Raises:
            ValueError: Se il nome del preset non è valido.
            FileNotFoundError: Se il file del preset non esiste.
        """
        preset_name = self._sanitize_name(name)
        preset_path = self.presets_dir / f"{preset_name}.json"

        if not preset_path.is_file():
            raise FileNotFoundError(
                f"Il preset '{preset_name}' non è stato trovato in '{self.presets_dir}'."
            )

        try:
            content = preset_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except (json.JSONDecodeError, OSError) as err:
            logger.error("Errore durante la lettura del preset '%s': %s", preset_name, err)
            raise ValueError(f"File preset '{preset_name}.json' corrotto o illeggibile: {err}") from err

        theme_set = ThemeSet.from_dict(data)
        logger.info("Preset caricato con successo: '%s'", preset_name)
        return theme_set

    def list_presets(self) -> list[str]:
        """Elenca i nomi di tutti i preset disponibili nella directory.

        Returns:
            Lista ordinata alfabeticamente dei nomi dei preset (senza estensione .json).
        """
        if not self.presets_dir.is_dir():
            return []

        presets = [
            f.stem
            for f in self.presets_dir.glob("*.json")
            if f.is_file() and not f.name.startswith(".")
        ]
        presets.sort(key=str.lower)
        return presets

    def delete_preset(self, name: str) -> bool:
        """Elimina il file JSON di un preset.

        Args:
            name: Nome del preset da eliminare.

        Returns:
            True se il file è stato eliminato con successo.

        Raises:
            ValueError: Se il nome del preset non è valido.
            FileNotFoundError: Se il preset da eliminare non esiste.
        """
        preset_name = self._sanitize_name(name)
        preset_path = self.presets_dir / f"{preset_name}.json"

        if not preset_path.is_file():
            raise FileNotFoundError(
                f"Impossibile eliminare: il preset '{preset_name}' non esiste in '{self.presets_dir}'."
            )

        preset_path.unlink()
        logger.info("Preset eliminato con successo: '%s'", preset_name)
        return True
