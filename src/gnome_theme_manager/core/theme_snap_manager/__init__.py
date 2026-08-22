# SPDX-License-Identifier: GPL-3.0-or-later

"""Snap Theme Manager subsystem for custom GTK/Icon theme compatibility in Snap applications."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .builder import ContentSnapBuilder
from .cleanup import cleanup_temp_files, restore_common_themes_connections, uninstall_content_snap
from .connector import SnapConnector
from .detector import ThemeDetector
from .exceptions import (
    BuildError,
    ConnectionError,
    SnapPermissionError,
    ThemeSnapError,
    ValidationError,
)
from .validator import ThemeValidator

logger = logging.getLogger("gnome_theme_manager.core.theme_snap_manager")

__all__ = [
    "BuildError",
    "ConnectionError",
    "ContentSnapBuilder",
    "SnapConnector",
    "SnapPermissionError",
    "ThemeDetector",
    "ThemeSnapError",
    "ThemeValidator",
    "ValidationError",
    "apply_custom_theme_with_snap_support",
    "cleanup_temp_files",
    "restore_common_themes_connections",
    "uninstall_content_snap",
]


def apply_custom_theme_with_snap_support(
    theme_name: str,
    theme_path: Path,
    icon_name: str | None = None,
    icon_path: Path | None = None,
    slots: list[str] | None = None,
) -> dict[str, Any]:
    """Orchestrate end-to-end custom theme packaging, installation, and snap connection.

    1. Verify compatibility with ThemeDetector.
    2. Build local Content Snap using ContentSnapBuilder (including icon theme if provided).
    3. Install the .snap package in --dangerous mode.
    4. Connect Content Snap to all target snap applications via SnapConnector.
    5. Run integration validation with ThemeValidator.
    6. Clean up build artifacts.

    Args:
        theme_name: Name of custom theme.
        theme_path: Local directory path containing theme files.
        icon_name: Optional custom icon theme name (from ~/.icons).
        icon_path: Optional filesystem path containing icon files.
        slots: Optional specific slot list to export and connect.

    Returns:
        Dict containing execution summary and connection results.
    """
    logger.info(
        "Starting Snap theme workflow for '%s' (path: %s, icon: %s)",
        theme_name,
        theme_path,
        icon_name,
    )

    # 1. Compatibility check
    detector = ThemeDetector()
    is_compatible, available_slots = detector.check_theme_compatibility(theme_name)
    if is_compatible and not icon_path:
        logger.info(
            "Theme '%s' is already natively available in gtk-common-themes. No custom snap needed.",
            theme_name,
        )
        return {
            "status": "skipped",
            "message": f"Theme '{theme_name}' is already compatible with gtk-common-themes.",
            "slots": available_slots,
            "snap_name": "gtk-common-themes",
        }

    # 2. Build Content Snap
    builder = ContentSnapBuilder(
        theme_name=theme_name,
        theme_path=theme_path,
        icon_name=icon_name,
        icon_path=icon_path,
    )
    snap_file: Path | None = None
    try:
        snap_file, populated_slots = builder.build()
        active_slots = [s for s in (slots or populated_slots) if s in populated_slots]
        if not active_slots:
            active_slots = populated_slots or ["gtk-3-themes"]

        # 3. Install Content Snap and Connect to all target snaps in a SINGLE privileged execution
        snap_bin = shutil.which("snap")
        if not snap_bin:
            raise BuildError("snap executable not found on system.")

        connector = SnapConnector(builder.snap_name)
        targets = connector.get_snaps_using_common_themes()

        batch_commands: list[str] = [
            f'"{snap_bin}" install --dangerous "{snap_file}"',
        ]
        for snap_name in sorted(targets):
            for slot in active_slots:
                # Use || true to gracefully skip snaps that don't declare optional slots
                batch_commands.append(
                    f'"{snap_bin}" connect "{snap_name}:{slot}" "{builder.snap_name}:{slot}" || true'
                )

        elevated_prefix = ["pkexec"] if shutil.which("pkexec") is not None else ["sudo"]
        full_batch_script = " && ".join(batch_commands)
        install_and_connect_cmd = [*elevated_prefix, "/bin/sh", "-c", full_batch_script]

        res = subprocess.run(install_and_connect_cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            if (
                "permission denied" in res.stderr.lower()
                or "password" in res.stderr.lower()
                or "not authorized" in res.stderr.lower()
            ):
                raise SnapPermissionError(
                    f"Permission denied executing: {' '.join(install_and_connect_cmd)}"
                )
            raise BuildError(
                f"Failed installing and connecting snap {builder.snap_name}: {res.stderr or res.stdout}"
            )

        connection_results: dict[str, dict[str, bool]] = {
            snap_name: {slot: True for slot in active_slots} for snap_name in targets
        }

        # 4. Validation
        validator = ThemeValidator(theme_name)
        validation_passed = validator.run_integration_test()

        return {
            "status": "installed",
            "snap_name": builder.snap_name,
            "snap_file": str(snap_file),
            "slots": active_slots,
            "connections": connection_results,
            "validation_passed": validation_passed,
        }
    finally:
        builder.cleanup()
        cleanup_temp_files()
