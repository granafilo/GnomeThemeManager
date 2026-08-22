# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme validator for testing and verifying theme mounts inside Snap sandboxes."""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger("gnome_theme_manager.core.theme_snap_manager.validator")


class ThemeValidator:
    """Validates that a custom theme is accessible and properly mounted inside Snap environments."""

    def __init__(self, theme_name: str) -> None:
        """Initialize validator with theme name."""
        self.theme_name = theme_name.strip()

    @staticmethod
    def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Run command returning completed process."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    def validate_theme_mount(self, snap_name: str) -> bool:
        """Verify theme presence within snap environment."""
        snap_bin = shutil.which("snap")
        if not snap_bin:
            return False

        # Test theme presence inside snap filesystem mount points
        check_script = (
            f"test -d /snap/{snap_name}/current/data-dir/themes/{self.theme_name} || "
            f"test -d /snap/gtk-common-themes/current/share/themes/{self.theme_name} || "
            f"test -d $SNAP/data-dir/themes/{self.theme_name} || "
            f"test -d ~/.themes/{self.theme_name}"
        )

        cmd = ["sudo", snap_bin, "run", "--shell", snap_name, "-c", check_script]
        res = self._run_cmd(cmd)
        is_mounted = res.returncode == 0
        logger.debug(
            "Validation for snap '%s' (theme '%s'): %s", snap_name, self.theme_name, is_mounted
        )
        return is_mounted

    def validate_multiple_snaps(self, snap_names: list[str]) -> dict[str, bool]:
        """Validate theme mounts across multiple target snaps."""
        results: dict[str, bool] = {}
        for snap_name in snap_names:
            try:
                results[snap_name] = self.validate_theme_mount(snap_name)
            except Exception as err:
                logger.warning("Failed validating theme on snap '%s': %s", snap_name, err)
                results[snap_name] = False
        return results

    def run_integration_test(self) -> bool:
        """Run verification on standard GNOME snap applications."""
        standard_test_snaps = ["firefox", "thunderbird", "gnome-calculator"]
        results = self.validate_multiple_snaps(standard_test_snaps)

        successful_mounts = sum(1 for is_valid in results.values() if is_valid)
        # Pass if at least 2 snap applications or all available installed ones pass
        passed = successful_mounts >= min(2, len(results)) if results else False
        logger.info("Integration test results (%d/%d): %s", successful_mounts, len(results), passed)
        return passed
