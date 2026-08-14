# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo per la gestione dei collegamenti simbolici (symlink) per temi GTK4 / Libadwaita.

Nelle versioni recenti di GNOME (42+ su Ubuntu 22.04 e 24.04), le applicazioni
moderne basate su GTK4 e Libadwaita non seguono più la chiave GSettings 'gtk-theme'.
Per applicare un tema personalizzato a queste applicazioni, occorre creare dei
collegamenti simbolici (symlink) nella directory di configurazione utente `~/.config/gtk-4.0/`.
"""

import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from .constants import GTK4_CONFIG_DIR
from .errors import ThemeApplyError, ThemeBackupError, ThemeRollbackError

logger = logging.getLogger("gnome_theme_manager.core")


class GTK4ThemeLinker:
    """Gestisce la creazione, rimozione e il backup sicuro dei symlink per temi GTK4 / Libadwaita."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Inizializza il linker GTK4.

        Args:
            config_dir: Directory di destinazione per la configurazione GTK4
                        (default: ~/.config/gtk-4.0).
        """
        self.config_dir = config_dir if config_dir is not None else GTK4_CONFIG_DIR

        # Definizione percorsi XDG conformemente alle specifiche
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config and xdg_config.strip():
            self.config_root = Path(xdg_config).expanduser() / "gnome-theme-manager"
        else:
            self.config_root = Path.home() / ".config" / "gnome-theme-manager"

        self.manifest_path = self.config_root / "gtk4_manifest.json"
        self.state_dir = self.config_root / "state"

        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data and xdg_data.strip():
            self.backup_root = Path(xdg_data).expanduser() / "gnome-theme-manager" / "backups"
        else:
            self.backup_root = Path.home() / ".local" / "share" / "gnome-theme-manager" / "backups"

    def _load_manifest(self) -> dict[str, Any]:
        """Carica il manifest esistente. Ritorna un dizionario vuoto/nuovo se assente o corrotto."""
        if not self.manifest_path.is_file():
            return {"version": 1, "active_theme": None, "entries": {}}
        try:
            content = self.manifest_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict) or data.get("version") != 1:
                # Versione non supportata o manifest corrotto
                return {"version": 1, "active_theme": None, "entries": {}}
            return data
        except Exception:
            return {"version": 1, "active_theme": None, "entries": {}}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        """Salva il manifest in modo atomico."""
        self._write_manifest_atomically(manifest)

    def _write_manifest_atomically(self, manifest: dict[str, Any]) -> None:
        """Scrive il file del manifest in modo atomico usando un file temporaneo."""
        try:
            self.config_root.mkdir(parents=True, exist_ok=True)
            temp_file = self.manifest_path.with_suffix(".tmp")
            temp_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            temp_file.replace(self.manifest_path)
        except Exception as e:
            raise ThemeApplyError(f"Impossibile salvare il manifest in modo atomico: {e}") from e

    def _fingerprint_entry(self, path: Path) -> str:
        """Calcola l'impronta hash (SHA256) per un file, directory o symlink."""
        if not path.exists() and not path.is_symlink():
            return "missing"

        if path.is_symlink():
            try:
                target = os.readlink(path)
                return f"symlink:{target}"
            except Exception:
                return "symlink_broken"

        h = hashlib.sha256()
        if path.is_file():
            try:
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                return f"sha256:{h.hexdigest()}"
            except Exception:
                return "error"
        elif path.is_dir():
            try:
                for root, dirs, files in os.walk(path):
                    dirs.sort()
                    files.sort()
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            rel_path = file_path.relative_to(path)
                            h.update(str(rel_path).encode("utf-8"))
                            with open(file_path, "rb") as f:
                                for chunk in iter(lambda: f.read(65536), b""):
                                    h.update(chunk)
                        except Exception:
                            pass
                return f"sha256:{h.hexdigest()}"
            except Exception:
                return "error"

        return "unknown"

    def _capture_entry(self, path: Path) -> dict[str, Any]:
        """Rileva lo stato di un elemento del filesystem per il manifest."""
        if not path.exists() and not path.is_symlink():
            return {
                "kind": "missing",
                "managed_kind": "symlink",
                "target": None,
                "backup": None,
                "original_fingerprint": "missing",
                "managed_fingerprint": "missing",
            }

        kind = "file"
        target = None
        if path.is_symlink():
            kind = "symlink"
            target = os.readlink(path)
        elif path.is_dir():
            kind = "directory"

        fingerprint = self._fingerprint_entry(path)

        return {
            "kind": kind,
            "managed_kind": "symlink",
            "target": target,
            "backup": None,
            "original_fingerprint": fingerprint,
            "managed_fingerprint": None,
        }

    def _is_manager_owned(self, path: Path, entry: dict[str, Any]) -> bool:
        """Verifica se l'elemento a `path` è rimasto invariato e gestito da noi."""
        if not path.exists() and not path.is_symlink():
            return entry.get("kind") == "missing"

        current_fingerprint = self._fingerprint_entry(path)
        expected_fingerprint = entry.get("managed_fingerprint")

        # Se è un symlink, verifichiamo anche il target del link
        if path.is_symlink() and entry.get("managed_kind") == "symlink":
            try:
                current_target = os.readlink(path)
                return current_target == entry.get("target")
            except Exception:
                return False

        return current_fingerprint == expected_fingerprint

    def _backup_entry(self, path: Path, name: str) -> Path:
        """Crea una copia di backup dell'elemento in backup_root con un nome univoco."""
        try:
            self.backup_root.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            backup_path = self.backup_root / f"{name}_{timestamp}"

            # Garantiamo permessi corretti per la cartella dei backup (0700)
            self.backup_root.chmod(0o700)

            if path.is_symlink():
                # Salviamo il link simbolico come tale nel percorso di backup
                target = os.readlink(path)
                backup_path.symlink_to(target)
            elif path.is_file():
                shutil.copy2(path, backup_path)
            elif path.is_dir():
                shutil.copytree(path, backup_path, symlinks=True)

            return backup_path
        except Exception as e:
            raise ThemeBackupError(f"Impossibile creare il backup di {path}: {e}") from e

    def _restore_entry(self, entry: dict[str, Any], path: Path) -> None:
        """Ripristina lo stato originale di un elemento."""
        try:
            # Rimuoviamo l'elemento corrente se presente
            self._safe_remove(path)

            kind = entry.get("kind", "missing")
            backup_file = entry.get("backup")

            if kind == "missing":
                return
            elif kind == "symlink":
                if backup_file:
                    bp = Path(backup_file)
                    if bp.is_symlink():
                        orig_target = os.readlink(bp)
                        path.symlink_to(orig_target)
                    else:
                        # Fallback se il backup non è un symlink
                        target = entry.get("target")
                        if target:
                            path.symlink_to(target)
                else:
                    target = entry.get("target")
                    if target:
                        path.symlink_to(target)
            elif kind == "file" and backup_file:
                bp = Path(backup_file)
                if bp.is_file():
                    shutil.copy2(bp, path)
            elif kind == "directory" and backup_file:
                bp = Path(backup_file)
                if bp.is_dir():
                    shutil.copytree(bp, path, symlinks=True)
        except Exception as e:
            raise ThemeRollbackError(f"Errore durante il ripristino di {path}: {e}") from e

    def apply_override(self, theme_path: Path) -> bool:
        """Applica l'override GTK4 salvando in modo sicuro lo stato precedente ed eseguendo il rollback in caso di errore."""
        gtk4_source = theme_path / "gtk-4.0"
        gtk3_source = theme_path / "gtk-3.0"

        source_dir: Path | None = None
        if gtk4_source.is_dir() and (gtk4_source / "gtk.css").exists():
            source_dir = gtk4_source
        elif gtk3_source.is_dir() and (gtk3_source / "gtk.css").exists():
            source_dir = gtk3_source

        if source_dir is None:
            self.remove_override()
            return False

        # Carichiamo il manifest corrente
        manifest = self._load_manifest()
        entries = manifest.setdefault("entries", {})

        # Prepariamo la directory destinazione
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ThemeApplyError(f"Impossibile creare la directory {self.config_dir}: {e}") from e

        # Elementi da gestire
        targets_to_process = {
            "gtk.css": source_dir / "gtk.css",
            "gtk-dark.css": source_dir / "gtk-dark.css"
            if (source_dir / "gtk-dark.css").exists()
            else None,
            "assets": source_dir / "assets" if (source_dir / "assets").exists() else None,
        }

        # Teniamo traccia dello stato pre-applicazione per un eventuale rollback in-memory
        rollback_info: list[tuple[Path, dict[str, Any]]] = []
        new_entries = {}

        try:
            for name, source_file in targets_to_process.items():
                dest_path = self.config_dir / name
                existing_entry = entries.get(name)

                # Rileviamo lo stato corrente
                current_state = self._capture_entry(dest_path)

                # Determiniamo se dobbiamo eseguire il backup
                needs_backup = False
                backup_path = None

                if current_state["kind"] != "missing":
                    if existing_entry:
                        # Se l'elemento era registrato, verifichiamo se l'utente l'ha modificato esternamente
                        if not self._is_manager_owned(dest_path, existing_entry):
                            needs_backup = True
                        else:
                            # Era gestito ed è invariato, conserviamo l'eventuale backup precedente
                            backup_path = existing_entry.get("backup")
                            if backup_path:
                                backup_path = Path(backup_path)
                    else:
                        # Non registrato nel manifest, ma presente: è un file utente originale
                        needs_backup = True

                # Eseguiamo il backup se richiesto
                if needs_backup:
                    backup_path = self._backup_entry(dest_path, name)

                # Registriamo l'entry nel manifest temporaneo
                new_entry = {
                    "kind": current_state["kind"]
                    if needs_backup or not existing_entry
                    else existing_entry["kind"],
                    "managed_kind": "symlink",
                    "target": str(source_file.resolve()) if source_file else None,
                    "backup": str(backup_path) if backup_path else None,
                    "original_fingerprint": current_state["original_fingerprint"]
                    if needs_backup or not existing_entry
                    else existing_entry["original_fingerprint"],
                    "managed_fingerprint": None,
                }

                # Salviamo le info per il rollback immediato in memoria
                rollback_info.append(
                    (
                        dest_path,
                        existing_entry
                        or {
                            "kind": "missing",
                            "managed_kind": "symlink",
                            "target": None,
                            "backup": None,
                            "original_fingerprint": "missing",
                            "managed_fingerprint": "missing",
                        },
                    )
                )

                # Se non c'è una sorgente per questo elemento (es. gtk-dark.css non presente nel tema)
                if not source_file:
                    self._safe_remove(dest_path)
                    new_entry["managed_fingerprint"] = "missing"
                    new_entries[name] = new_entry
                    continue

                # Applichiamo il collegamento simbolico in modo sicuro
                self._safe_remove(dest_path)
                try:
                    dest_path.symlink_to(source_file.resolve())
                except OSError:
                    # Fallback in caso di mancato supporto symlink: copia
                    if source_file.is_dir():
                        shutil.copytree(source_file, dest_path)
                    else:
                        shutil.copy2(source_file, dest_path)

                # Calcoliamo il fingerprint gestito
                new_entry["managed_fingerprint"] = self._fingerprint_entry(dest_path)
                new_entries[name] = new_entry

            # Se siamo arrivati qui, l'operazione ha avuto successo. Aggiorniamo il manifest
            manifest["active_theme"] = theme_path.name
            # Manteniamo le entry esistenti che non abbiamo sovrascritto
            for k, v in entries.items():
                if k not in new_entries:
                    new_entries[k] = v
            manifest["entries"] = new_entries
            self._save_manifest(manifest)
            return True

        except Exception as e:
            # Rollback in-memory immediato se un'operazione fallisce
            logger.error("Errore durante apply_override, esecuzione rollback: %s", e)
            for dest_path, old_entry in rollback_info:
                try:
                    self._restore_entry(old_entry, dest_path)
                except Exception as re:
                    # Chain dell'eccezione se il rollback fallisce
                    raise ThemeRollbackError(
                        f"Il rollback parziale è fallito per {dest_path}: {re}"
                    ) from e
            raise ThemeApplyError(f"Impossibile applicare l'override del tema: {e}") from e

    def remove_override(self) -> None:
        """Rimuove l'override GTK4 ripristinando in modo pulito i file originari dell'utente."""
        manifest = self._load_manifest()
        entries = manifest.get("entries", {})
        new_entries = {}
        conflitti = []

        for name, entry in list(entries.items()):
            dest_path = self.config_dir / name

            if not dest_path.exists() and not dest_path.is_symlink():
                # L'elemento è assente sul filesystem reale
                if entry.get("kind") != "missing":
                    # Ripristiniamo l'elemento dal backup originale se presente
                    try:
                        self._restore_entry(entry, dest_path)
                    except Exception as e:
                        logger.error("Errore durante il ripristino di %s: %s", name, e)
                continue

            # Verifichiamo se l'elemento è ancora gestito da noi o se è stato modificato esternamente
            if self._is_manager_owned(dest_path, entry):
                try:
                    self._restore_entry(entry, dest_path)
                except Exception as e:
                    logger.error("Errore durante il ripristino di %s: %s", name, e)
                    new_entries[name] = entry
            else:
                # Conflitto: l'utente ha modificato il file esternamente. Conserviamo e non tocchiamo
                conflitti.append(name)
                # Conserviamo la registrazione nel manifest per evitare perdite future
                new_entries[name] = entry

        # Pulizia manifest o aggiornamento a seconda dei conflitti residui
        if conflitti:
            manifest["entries"] = new_entries
            self._save_manifest(manifest)
            conflitti_str = ", ".join(conflitti)
            logger.warning(
                "Rilevati conflitti di modifica manuale. Gli elementi seguenti sono stati conservati: %s",
                conflitti_str,
            )
        else:
            manifest["active_theme"] = None
            manifest["entries"] = {}
            self._save_manifest(manifest)

    def is_override_active(self) -> bool:
        """Verifica se l'override GTK4 è attualmente attivo e valido in ~/.config/gtk-4.0/."""
        target_css = self.config_dir / "gtk.css"
        if not target_css.exists() or not target_css.is_file():
            return False

        manifest = self._load_manifest()
        entries = manifest.get("entries", {})
        if "gtk.css" not in entries:
            return False

        return self._is_manager_owned(target_css, entries["gtk.css"])

    def _safe_symlink(self, source: Path, target: Path) -> None:
        """Crea un symlink in modo sicuro, rimuovendo un file o link precedente se presente (retrocompatibilità)."""
        self._safe_remove(target)
        try:
            target.symlink_to(source.resolve())
        except OSError:
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
