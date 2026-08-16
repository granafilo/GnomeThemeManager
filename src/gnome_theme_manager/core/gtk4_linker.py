# SPDX-License-Identifier: GPL-3.0-or-later

"""Symbolic link management module for GTK4 / Libadwaita themes.

In modern GNOME releases (42+ on Ubuntu 22.04 and 24.04), GTK4 and Libadwaita
applications no longer track the GSettings 'gtk-theme' key.
To apply custom themes to these applications, symbolic links must be created
in the user configuration directory `~/.config/gtk-4.0/`.
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
    """Manages creation, removal, safe backup, and rollback of GTK4 / Libadwaita theme symlinks."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the GTK4 linker.

        Args:
            config_dir: Destination directory for GTK4 configuration
                        (default: ~/.config/gtk-4.0).
        """
        self.config_dir = config_dir if config_dir is not None else GTK4_CONFIG_DIR

        # Define XDG paths
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
        """Load existing manifest. Returns a new empty dict if missing or corrupted."""
        if not self.manifest_path.is_file():
            return {"version": 1, "active_theme": None, "entries": {}}
        try:
            content = self.manifest_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict) or data.get("version") != 1:
                return {"version": 1, "active_theme": None, "entries": {}}
            return data
        except Exception:
            return {"version": 1, "active_theme": None, "entries": {}}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        """Save manifest atomically."""
        self._write_manifest_atomically(manifest)

    def _write_manifest_atomically(self, manifest: dict[str, Any]) -> None:
        """Write manifest file atomically using a temporary file."""
        try:
            self.config_root.mkdir(parents=True, exist_ok=True)
            temp_file = self.manifest_path.with_suffix(".tmp")
            temp_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            temp_file.replace(self.manifest_path)
        except Exception as e:
            raise ThemeApplyError(f"Failed to save manifest atomically: {e}") from e

    def _fingerprint_entry(self, path: Path) -> str:
        """Compute hash fingerprint (SHA256) for a file, directory, or symlink."""
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
        """Capture the filesystem entry state for the manifest."""
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
        """Check if entry at `path` is unchanged and managed by us."""
        if not path.exists() and not path.is_symlink():
            return entry.get("kind") == "missing"

        current_fingerprint = self._fingerprint_entry(path)
        expected_fingerprint = entry.get("managed_fingerprint")

        # For symlinks, also verify the link target
        if path.is_symlink() and entry.get("managed_kind") == "symlink":
            try:
                current_target = os.readlink(path)
                return current_target == entry.get("target")
            except Exception:
                return False

        return current_fingerprint == expected_fingerprint

    def _backup_entry(self, path: Path, name: str) -> Path:
        """Create a backup copy of entry in backup_root with unique name."""
        try:
            self.backup_root.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            backup_path = self.backup_root / f"{name}_{timestamp}"

            # Set safe directory permissions (0700)
            self.backup_root.chmod(0o700)

            if path.is_symlink():
                target = os.readlink(path)
                backup_path.symlink_to(target)
            elif path.is_file():
                shutil.copy2(path, backup_path)
            elif path.is_dir():
                shutil.copytree(path, backup_path, symlinks=True)

            return backup_path
        except Exception as e:
            raise ThemeBackupError(f"Failed to create backup of {path}: {e}") from e

    def _restore_entry(self, entry: dict[str, Any], path: Path) -> None:
        """Restore original state of an entry."""
        try:
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
            raise ThemeRollbackError(f"Error restoring {path}: {e}") from e

    def apply_override(self, theme_path: Path) -> bool:
        """Apply GTK4 override, safely backing up prior state and rolling back on failure."""
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

        manifest = self._load_manifest()
        entries = manifest.setdefault("entries", {})

        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ThemeApplyError(f"Cannot create directory {self.config_dir}: {e}") from e

        targets_to_process = {
            "gtk.css": source_dir / "gtk.css",
            "gtk-dark.css": source_dir / "gtk-dark.css"
            if (source_dir / "gtk-dark.css").exists()
            else None,
            "assets": source_dir / "assets" if (source_dir / "assets").exists() else None,
        }

        rollback_info: list[tuple[Path, dict[str, Any]]] = []
        new_entries = {}

        try:
            for name, source_file in targets_to_process.items():
                dest_path = self.config_dir / name
                existing_entry = entries.get(name)

                current_state = self._capture_entry(dest_path)

                needs_backup = False
                backup_path = None

                if current_state["kind"] != "missing":
                    if existing_entry:
                        if not self._is_manager_owned(dest_path, existing_entry):
                            needs_backup = True
                        else:
                            backup_path = existing_entry.get("backup")
                            if backup_path:
                                backup_path = Path(backup_path)
                    else:
                        needs_backup = True

                if needs_backup:
                    backup_path = self._backup_entry(dest_path, name)

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

                if not source_file:
                    self._safe_remove(dest_path)
                    new_entry["managed_fingerprint"] = "missing"
                    new_entries[name] = new_entry
                    continue

                self._safe_remove(dest_path)
                try:
                    dest_path.symlink_to(source_file.resolve())
                except OSError:
                    if source_file.is_dir():
                        shutil.copytree(source_file, dest_path)
                    else:
                        shutil.copy2(source_file, dest_path)

                new_entry["managed_fingerprint"] = self._fingerprint_entry(dest_path)
                new_entries[name] = new_entry

            manifest["active_theme"] = theme_path.name
            for k, v in entries.items():
                if k not in new_entries:
                    new_entries[k] = v
            manifest["entries"] = new_entries
            self._save_manifest(manifest)
            return True

        except Exception as e:
            logger.error("Error during apply_override, performing rollback: %s", e)
            for dest_path, old_entry in rollback_info:
                try:
                    self._restore_entry(old_entry, dest_path)
                except Exception as re:
                    raise ThemeRollbackError(
                        f"Partial rollback failed for {dest_path}: {re}"
                    ) from e
            raise ThemeApplyError(f"Failed to apply theme override: {e}") from e

    def remove_override(self) -> None:
        """Remove GTK4 override, cleanly restoring original user files."""
        manifest = self._load_manifest()
        entries = manifest.get("entries", {})
        new_entries = {}
        conflicts = []

        for name, entry in list(entries.items()):
            dest_path = self.config_dir / name

            if not dest_path.exists() and not dest_path.is_symlink():
                if entry.get("kind") != "missing":
                    try:
                        self._restore_entry(entry, dest_path)
                    except Exception as e:
                        logger.error("Error restoring %s: %s", name, e)
                continue

            if self._is_manager_owned(dest_path, entry):
                try:
                    self._restore_entry(entry, dest_path)
                except Exception as e:
                    logger.error("Error restoring %s: %s", name, e)
                    new_entries[name] = entry
            else:
                conflicts.append(name)
                new_entries[name] = entry

        if conflicts:
            manifest["entries"] = new_entries
            self._save_manifest(manifest)
            conflicts_str = ", ".join(conflicts)
            logger.warning(
                "Manual external modifications detected. The following items were preserved: %s",
                conflicts_str,
            )
        else:
            manifest["active_theme"] = None
            manifest["entries"] = {}
            self._save_manifest(manifest)

    def is_override_active(self) -> bool:
        """Check if GTK4 override is currently active and valid in ~/.config/gtk-4.0/."""
        target_css = self.config_dir / "gtk.css"
        if not target_css.exists() or not target_css.is_file():
            return False

        manifest = self._load_manifest()
        entries = manifest.get("entries", {})
        if "gtk.css" not in entries:
            return False

        return self._is_manager_owned(target_css, entries["gtk.css"])

    def _safe_symlink(self, source: Path, target: Path) -> None:
        """Safely create a symlink, removing any prior file or link."""
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
        """Safely remove a file, symlink, or directory."""
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
