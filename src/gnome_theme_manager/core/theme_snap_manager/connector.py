# SPDX-License-Identifier: GPL-3.0-or-later

"""Snap connector for connecting Content Snaps to installed applications."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .exceptions import SnapPermissionError

logger = logging.getLogger("gnome_theme_manager.core.theme_snap_manager.connector")


def _get_elevated_cmd(base_cmd: list[str]) -> list[str]:
    """Prefix command with pkexec (if available and in graphical session) or sudo."""
    if shutil.which("pkexec") is not None:
        return ["pkexec", *base_cmd]
    return ["sudo", *base_cmd]


class SnapConnector:
    """Manages connections between a custom Content Snap and installed Snap applications."""

    def __init__(self, content_snap_name: str) -> None:
        """Initialize connector with target content snap name."""
        self.content_snap_name = content_snap_name.strip()

    @staticmethod
    def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute a shell command capturing text output."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    def get_installed_snaps(self) -> list[str]:
        """Query and return list of installed snap names."""
        snap_bin = shutil.which("snap")
        if snap_bin:
            # Attempt structured JSON output first
            res = self._run_cmd([snap_bin, "list", "--json"])
            if res.returncode == 0 and res.stdout.strip():
                try:
                    data = json.loads(res.stdout)
                    if isinstance(data, list):
                        return [
                            str(item["name"])
                            for item in data
                            if isinstance(item, dict) and item.get("name") is not None
                        ]
                except Exception as err:
                    logger.debug("Failed parsing 'snap list --json': %s", err)

            # Fallback to standard textual listing
            res_text = self._run_cmd([snap_bin, "list"])
            if res_text.returncode == 0:
                snaps: list[str] = []
                for line in res_text.stdout.splitlines()[1:]:
                    parts = line.split()
                    if parts:
                        snaps.append(parts[0])
                if snaps:
                    return snaps

        # Filesystem discovery (fallback / sandbox mode)
        ignored = {
            "bin",
            "README",
            "core",
            "core18",
            "core20",
            "core22",
            "core24",
            "core26",
            "bare",
            "snapd",
        }
        found_snaps: set[str] = set()
        snap_dir = Path("/snap")
        if snap_dir.is_dir():
            try:
                for child in snap_dir.iterdir():
                    if (
                        child.is_dir()
                        and child.name not in ignored
                        and not child.name.startswith(".")
                    ):
                        found_snaps.add(child.name)
            except OSError:
                pass

        snaps_archive_dir = Path("/var/lib/snapd/snaps")
        if snaps_archive_dir.is_dir():
            try:
                for snap_file in snaps_archive_dir.glob("*.snap"):
                    name = snap_file.stem.split("_")[0]
                    if name and name not in ignored:
                        found_snaps.add(name)
            except OSError:
                pass

        return sorted(found_snaps)

    def get_snaps_using_common_themes(self) -> set[str]:
        """Identify installed snap applications that consume gtk-common-themes."""
        snap_bin = shutil.which("snap")
        if snap_bin:
            target_snaps: set[str] = set()

            def _parse_lines(output: str) -> None:
                for line in output.splitlines():
                    if "gtk-common-themes" in line or (
                        self.content_snap_name and self.content_snap_name in line
                    ):
                        parts = line.split()
                        if len(parts) >= 2:
                            for part in parts:
                                if ":" in part:
                                    app = part.split(":", 1)[0]
                                    if app not in (
                                        "core",
                                        "core20",
                                        "core22",
                                        "snapd",
                                        "bare",
                                        "gtk-common-themes",
                                    ):
                                        target_snaps.add(app)

            # 1. Single command query for gtk-common-themes slot/plug
            res = self._run_cmd([snap_bin, "connections", "gtk-common-themes"])
            if res.returncode == 0 and res.stdout.strip():
                _parse_lines(res.stdout)
                if target_snaps:
                    logger.debug("Snaps using gtk-common-themes: %s", target_snaps)
                    return target_snaps

            # 2. General connections query
            res_gen = self._run_cmd([snap_bin, "connections"])
            if res_gen.returncode == 0 and res_gen.stdout.strip():
                _parse_lines(res_gen.stdout)
                if target_snaps:
                    logger.debug("Snaps using gtk-common-themes: %s", target_snaps)
                    return target_snaps

            # 3. Fallback per installed snap (useful if snapd restricts batch queries)
            installed = self.get_installed_snaps()
            for snap_name in installed:
                if snap_name in ("core", "core20", "core22", "snapd", "bare", "gtk-common-themes"):
                    continue
                res_ind = self._run_cmd([snap_bin, "connections", snap_name])
                if res_ind.returncode == 0 and (
                    "gtk-common-themes" in res_ind.stdout
                    or self.content_snap_name in res_ind.stdout
                ):
                    target_snaps.add(snap_name)

            if target_snaps:
                logger.debug("Snaps using gtk-common-themes: %s", target_snaps)
                return target_snaps

        # Filesystem fallback for sandbox / no CLI
        mount_dir = Path("/var/lib/snapd/mount")
        target_snaps_fs: set[str] = set()
        if mount_dir.is_dir():
            try:
                for fstab_file in mount_dir.glob("snap.*.fstab"):
                    parts = fstab_file.name.split(".")
                    if len(parts) >= 3 and parts[0] == "snap" and parts[-1] == "fstab":
                        app_name = parts[1]
                        if app_name not in (
                            "core",
                            "core18",
                            "core20",
                            "core22",
                            "core24",
                            "core26",
                            "snapd",
                            "bare",
                            "gtk-common-themes",
                            "cups",
                        ):
                            try:
                                content = fstab_file.read_text(
                                    encoding="utf-8", errors="ignore"
                                ).lower()
                                if (
                                    "theme" in content
                                    or "gtk-common-themes" in content
                                    or (
                                        self.content_snap_name
                                        and self.content_snap_name.lower() in content
                                    )
                                ):
                                    target_snaps_fs.add(app_name)
                            except OSError:
                                pass
            except OSError:
                pass

        return target_snaps_fs

    def _connect_slot(self, snap_name: str, slot: str) -> bool:
        """Connect a specific slot from content snap to target application."""
        snap_bin = shutil.which("snap")
        if not snap_bin:
            return False

        # e.g., pkexec snap connect firefox:gtk-3-themes custom-theme-colloid:gtk-3-themes
        cmd = _get_elevated_cmd(
            [
                snap_bin,
                "connect",
                f"{snap_name}:{slot}",
                f"{self.content_snap_name}:{slot}",
            ]
        )
        res = self._run_cmd(cmd)
        if res.returncode != 0:
            if (
                "permission denied" in res.stderr.lower()
                or "password" in res.stderr.lower()
                or "not authorized" in res.stderr.lower()
            ):
                raise SnapPermissionError(f"Permission denied executing: {' '.join(cmd)}")
            logger.warning(
                "Failed connecting %s:%s to %s:%s (exit %d): %s",
                snap_name,
                slot,
                self.content_snap_name,
                slot,
                res.returncode,
                res.stderr.strip() or res.stdout.strip(),
            )
            return False

        logger.info("Connected %s:%s -> %s:%s", snap_name, slot, self.content_snap_name, slot)
        return True

    def connect_to_all_target_snaps(self, slots: list[str]) -> dict[str, dict[str, bool]]:
        """Connect the Content Snap to all target applications for each provided slot.

        Executes all connections in a single privileged batch script so PolicyKit/sudo
        prompts for authentication only once.

        Args:
            slots: List of slot names (e.g. ['gtk-3-themes', 'icon-themes']).

        Returns:
            Dictionary mapping {snap_name: {slot: success_boolean}}.
        """
        snap_bin = shutil.which("snap")
        if not snap_bin:
            return {}

        targets = self.get_snaps_using_common_themes()
        results: dict[str, dict[str, bool]] = {}

        if not targets:
            logger.info("No snap applications consuming gtk-common-themes were found.")
            return results

        # Prepare shell commands to execute together
        shell_commands: list[str] = []
        for snap_name in sorted(targets):
            results[snap_name] = {}
            for slot in slots:
                results[snap_name][slot] = True  # optimistic prefill
                shell_commands.append(
                    f'"{snap_bin}" connect "{snap_name}:{slot}" "{self.content_snap_name}:{slot}"'
                )

        if not shell_commands:
            return results

        batch_script = " && ".join(shell_commands)
        elevated_cmd = _get_elevated_cmd(["/bin/sh", "-c", batch_script])
        res = self._run_cmd(elevated_cmd)

        if res.returncode != 0:
            if (
                "permission denied" in res.stderr.lower()
                or "password" in res.stderr.lower()
                or "not authorized" in res.stderr.lower()
            ):
                raise SnapPermissionError(f"Permission denied executing: {' '.join(elevated_cmd)}")
            logger.warning(
                "Batch snap connect had failures (exit %d): %s",
                res.returncode,
                res.stderr.strip() or res.stdout.strip(),
            )
            # Fallback to verify individually if batch exit was non-zero
            for snap_name in targets:
                for slot in slots:
                    results[snap_name][slot] = False

        return results

    def disconnect_from_all_snaps(self, slots: list[str]) -> None:
        """Disconnect Content Snap from all installed applications in a single batch."""
        snap_bin = shutil.which("snap")
        if not snap_bin:
            return

        targets = self.get_installed_snaps()
        shell_commands: list[str] = []
        for snap_name in targets:
            for slot in slots:
                shell_commands.append(
                    f'"{snap_bin}" disconnect "{snap_name}:{slot}" "{self.content_snap_name}:{slot}" || true'
                )

        if not shell_commands:
            return

        batch_script = " ; ".join(shell_commands)
        elevated_cmd = _get_elevated_cmd(["/bin/sh", "-c", batch_script])
        self._run_cmd(elevated_cmd)
