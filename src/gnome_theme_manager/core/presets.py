# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo per il salvataggio, caricamento ed eliminazione di preset/profili di temi.

I preset consentono di memorizzare istantanee (snapshot) complete delle preferenze
desktop (tema GTK, icone, cursori, GNOME Shell e schema colori) in formato JSON
all'interno della cartella di configurazione utente (~/.config/gnome-theme-manager/presets/).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .constants import PRESETS_DIR
from .models import ThemeSet

logger = logging.getLogger("gnome_theme_manager.core")


class PresetManager:
    """Gestore del ciclo di vita dei preset di configurazione per GnomeThemeManager."""

    def __init__(self, presets_dir: Path | None = None) -> None:
        """Inizializza il gestore dei preset.

        Args:
            presets_dir: Directory di memorizzazione (default: ~/.local/state/gnome-theme-manager).
        """
        self.presets_dir = (
            Path(presets_dir).expanduser() if presets_dir is not None else PRESETS_DIR.expanduser()
        )
        self.presets_file = self.presets_dir / "presets.json"

    def _sanitize_name(self, name: str) -> str:
        """Valida e ripulisce il nome del preset prevenendo Path Traversal e nomi non validi.

        Consente nomi utente normali inclusi spazi, trattini, underscore, accenti e
        caratteri Unicode. Rifiuta esplicitamente:
        - stringa vuota o composta solo da spazi;
        - separatori di percorso '/' e '\\';
        - sequenze di risalita di directory '..';
        - nomi che sono esattamente '.' o '..';
        - caratteri di controllo (ASCII 0-31 e 127);
        - nomi con lunghezza superiore a 255 caratteri.

        Args:
            name: Nome del preset da verificare.

        Returns:
            Nome valido senza spazi superflui alle estremità.

        Raises:
            ValueError: Se il nome è vuoto, contiene caratteri non validi o
                        separatori di percorso filesystem.
        """
        cleaned = name.strip()

        # Nome vuoto o solo spazi
        if not cleaned:
            raise ValueError("Il nome del preset non può essere vuoto.")

        # Lunghezza eccessiva (limite del filesystem)
        if len(cleaned) > 255:
            raise ValueError(f"Nome preset troppo lungo ({len(cleaned)} caratteri, massimo 255).")

        # Separatori di percorso filesystem (prevenzione Path Traversal)
        if "/" in cleaned or "\\" in cleaned:
            raise ValueError(
                f"Nome preset non valido: '{name}'. Non sono ammessi caratteri di percorso."
            )

        # Sequenza di risalita directory
        if ".." in cleaned:
            raise ValueError(
                f"Nome preset non valido: '{name}'. Non sono ammessi caratteri di percorso."
            )

        # Nomi riservati come '.' singolo o '..'
        if cleaned == "." or cleaned == "..":
            raise ValueError(
                f"Nome preset non valido: '{name}'. Non sono ammessi caratteri di percorso."
            )

        # Caratteri di controllo ASCII (0-31 e 127)
        if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
            raise ValueError(
                f"Nome preset '{name}' contiene caratteri di controllo non consentiti."
            )

        return cleaned

    def _read_presets_file(self) -> dict:
        """Legge il file presets.json e restituisce il dizionario."""
        if not self.presets_file.is_file():
            return {"presets": []}
        try:
            content = self.presets_file.read_text(encoding="utf-8")
            return json.loads(content)
        except json.JSONDecodeError as err:
            logger.error("File presets.json corrotto o illeggibile: %s", err)
            raise ValueError(f"File presets.json corrotto o illeggibile: {err}") from err
        except Exception as err:
            logger.error("Errore durante la lettura di presets.json: %s", err)
            return {"presets": []}

    def _write_presets_file(self, data: dict) -> None:
        """Scrive il dizionario nel file presets.json."""
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        self.presets_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def save_preset(self, name: str, theme_set: ThemeSet, overwrite: bool = False) -> Path:
        """Salva una configurazione ThemeSet come preset nel file presets.json."""
        preset_name = self._sanitize_name(name)
        if theme_set.is_empty():
            raise ValueError("Impossibile salvare un preset privo di qualsiasi configurazione.")

        data = self._read_presets_file()
        presets = data.get("presets", [])

        # Cerca duplicati
        existing_index = -1
        for i, p in enumerate(presets):
            if p.get("name") == preset_name:
                existing_index = i
                break

        if existing_index != -1 and not overwrite:
            raise FileExistsError(f"Il preset '{preset_name}' esiste già.")

        # Crea la nuova voce esplicita secondo lo schema
        new_preset = {
            "name": preset_name,
            "components": {
                "gtk3": theme_set.gtk_theme,
                "gtk4": theme_set.gtk_theme,  # Fintanto che usiamo lo stesso tema per gtk3/gtk4
                "shell": theme_set.shell_theme,
                "icons": theme_set.icon_theme,
                "cursors": theme_set.cursor_theme,
            },
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if existing_index != -1:
            presets[existing_index] = new_preset
        else:
            presets.append(new_preset)

        data["presets"] = presets
        self._write_presets_file(data)
        logger.info("Preset salvato con successo: '%s'", preset_name)
        return self.presets_file

    def load_preset(self, name: str) -> ThemeSet:
        """Carica un preset dal file presets.json."""
        preset_name = self._sanitize_name(name)
        data = self._read_presets_file()
        presets = data.get("presets", [])

        for p in presets:
            if p.get("name") == preset_name:
                comp = p.get("components", {})
                return ThemeSet(
                    gtk_theme=comp.get("gtk3") or comp.get("gtk4"),
                    shell_theme=comp.get("shell"),
                    icon_theme=comp.get("icons"),
                    cursor_theme=comp.get("cursors"),
                )

        raise FileNotFoundError(f"Il preset '{preset_name}' non è stato trovato.")

    def list_presets(self) -> list[str]:
        """Elenca i nomi di tutti i preset disponibili."""
        data = self._read_presets_file()
        presets = data.get("presets", [])
        names = [p.get("name") for p in presets if p.get("name")]
        names.sort(key=str.lower)
        return names

    def delete_preset(self, name: str) -> bool:
        """Elimina un preset dal file presets.json."""
        preset_name = self._sanitize_name(name)
        data = self._read_presets_file()
        presets = data.get("presets", [])

        initial_len = len(presets)
        presets = [p for p in presets if p.get("name") != preset_name]

        if len(presets) == initial_len:
            raise FileNotFoundError(f"Il preset '{preset_name}' non esiste.")

        data["presets"] = presets
        self._write_presets_file(data)
        logger.info("Preset eliminato con successo: '%s'", preset_name)
        return True
