# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for ThemeValidator and cleanup routines in theme_snap_manager."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from gnome_theme_manager.core.theme_snap_manager.cleanup import (
    cleanup_temp_files,
    uninstall_content_snap,
)
from gnome_theme_manager.core.theme_snap_manager.validator import ThemeValidator


def test_validator_mount_verification() -> None:
    """Test validating theme mount via mocked shell check."""
    validator = ThemeValidator("Nordic")

    with patch("shutil.which", return_value="/usr/bin/snap"):
        mock_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch.object(validator, "_run_cmd", return_value=mock_proc):
            assert validator.validate_theme_mount("firefox") is True

        mock_fail = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with patch.object(validator, "_run_cmd", return_value=mock_fail):
            assert validator.validate_theme_mount("firefox") is False


def test_validator_integration_test() -> None:
    """Test run_integration_test aggregating multiple snap validations."""
    validator = ThemeValidator("Nordic")

    with patch.object(
        validator,
        "validate_multiple_snaps",
        return_value={"firefox": True, "thunderbird": True, "gnome-calculator": False},
    ):
        assert validator.run_integration_test() is True


def test_cleanup_uninstall_content_snap() -> None:
    """Test uninstall_content_snap command execution."""
    with (
        patch("shutil.which", return_value="/usr/bin/snap"),
        patch(
            "gnome_theme_manager.core.theme_snap_manager.cleanup._run_cmd",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ),
    ):
        assert uninstall_content_snap("custom-theme-nordic") is True


def test_cleanup_temp_files(tmp_path: Path) -> None:
    """Test cleaning temporary gtm-snap build directories."""
    fake_temp_dir = tmp_path / "gtm-snap-fake-123"
    fake_temp_dir.mkdir()
    (fake_temp_dir / "file.txt").write_text("hello")

    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        cleaned = cleanup_temp_files("gtm-snap-*")
        assert cleaned == 1
        assert not fake_temp_dir.exists()
