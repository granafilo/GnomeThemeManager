# SPDX-License-Identifier: GPL-3.0-or-later

"""Rollback, uninstallation, and cleanup routines for custom theme Content Snaps."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .connector import SnapConnector
from .exceptions import SnapPermissionError

logger = logging.getLogger("gnome_theme_manager.core.theme_snap_manager.cleanup")


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute a shell command capturing text output."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def _get_elevated_cmd(base_cmd: list[str]) -> list[str]:
    """Prefix command with pkexec (if available) or sudo."""
    if shutil.which("pkexec") is not None:
        return ["pkexec", *base_cmd]
    return ["sudo", *base_cmd]


def uninstall_content_snap(snap_name: str) -> bool:
    """Uninstall a custom Content Snap package.

    Args:
        snap_name: Name of the Content Snap to remove (e.g. 'custom-theme-colloid').

    Returns:
        True if uninstallation succeeded.
    """
    snap_bin = shutil.which("snap")
    if not snap_bin:
        return False

    cmd = _get_elevated_cmd([snap_bin, "remove", snap_name])
    res = _run_cmd(cmd)
    if res.returncode != 0:
        if (
            "permission denied" in res.stderr.lower()
            or "password" in res.stderr.lower()
            or "not authorized" in res.stderr.lower()
        ):
            raise SnapPermissionError(f"Permission denied executing: {' '.join(cmd)}")
        logger.warning(
            "Failed removing snap '%s': %s", snap_name, res.stderr.strip() or res.stdout.strip()
        )
        return False

    logger.info("Successfully uninstalled Content Snap: %s", snap_name)
    return True


def restore_common_themes_connections(slots: list[str] | None = None) -> None:
    """Restore default gtk-common-themes connections across installed snap applications.

    Args:
        slots: Optional list of slots to restore (defaults to gtk-3-themes, icon-themes, sound-themes).
    """
    snap_bin = shutil.which("snap")
    if not snap_bin:
        return

    active_slots = slots or ["gtk-3-themes", "icon-themes", "sound-themes"]
    connector = SnapConnector("gtk-common-themes")
    target_snaps = connector.get_snaps_using_common_themes()

    for snap_name in target_snaps:
        for slot in active_slots:
            cmd = _get_elevated_cmd(
                [
                    snap_bin,
                    "connect",
                    f"{snap_name}:{slot}",
                    f"gtk-common-themes:{slot}",
                ]
            )
            _run_cmd(cmd)

    logger.info("Restored standard gtk-common-themes connections for snaps: %s", target_snaps)


def cleanup_temp_files(pattern: str = "gtm-snap-*") -> int:
    """Remove leftover build directories matching the specified pattern in temp directory."""
    temp_base = Path(tempfile.gettempdir())
    cleaned_count = 0

    for temp_dir in temp_base.glob(pattern):
        if temp_dir.is_dir():
            try:
                shutil.rmtree(temp_dir)
                cleaned_count += 1
            except Exception as err:
                logger.warning("Failed deleting temporary directory '%s': %s", temp_dir, err)

    logger.debug("Cleaned up %d temporary theme snap build directories.", cleaned_count)
    return cleaned_count
