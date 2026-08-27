# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for SnapConnector in theme_snap_manager."""

import subprocess
from unittest.mock import patch

from gnome_theme_manager.core.theme_snap_manager.connector import SnapConnector


def test_connector_get_installed_snaps_parsing() -> None:
    """Test parsing snap list output into clean snap names."""
    connector = SnapConnector("custom-theme-test")

    mock_json = """
    [
        {"name": "core22"},
        {"name": "firefox"},
        {"name": "snapd"},
        {"name": "gnome-calculator"}
    ]
    """
    mock_res = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_json, stderr="")

    with (
        patch.object(connector, "_run_cmd", return_value=mock_res),
        patch("shutil.which", return_value="/usr/bin/snap"),
    ):
        snaps = connector.get_installed_snaps()
        assert "firefox" in snaps
        assert "gnome-calculator" in snaps
        assert len(snaps) == 4


def test_connector_get_snaps_using_common_themes() -> None:
    """Test identifying snaps consuming gtk-common-themes."""
    connector = SnapConnector("custom-theme-test")

    with (
        patch.object(
            connector,
            "get_installed_snaps",
            return_value=["firefox", "gnome-calculator", "custom-cli"],
        ),
        patch("shutil.which", return_value="/usr/bin/snap"),
    ):

        def mock_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            snap_target = cmd[2] if len(cmd) > 2 else ""
            if snap_target == "firefox":
                stdout = "gtk-3-themes  firefox:gtk-3-themes  gtk-common-themes:gtk-3-themes"
            elif snap_target == "gnome-calculator":
                stdout = (
                    "gtk-3-themes  gnome-calculator:gtk-3-themes  gtk-common-themes:gtk-3-themes"
                )
            else:
                stdout = "home  custom-cli:home  :home"
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

        with patch.object(connector, "_run_cmd", side_effect=mock_run):
            targets = connector.get_snaps_using_common_themes()
            assert "firefox" in targets
            assert "gnome-calculator" in targets
            assert "custom-cli" not in targets


def test_connector_connect_to_all_target_snaps() -> None:
    """Test connecting slots to discovered target snaps."""
    connector = SnapConnector("custom-theme-test")

    with (
        patch.object(connector, "get_snaps_using_common_themes", return_value={"firefox"}),
        patch("shutil.which", return_value="/usr/bin/snap"),
    ):
        mock_success = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch.object(connector, "_run_cmd", return_value=mock_success):
            results = connector.connect_to_all_target_snaps(["gtk-3-themes", "icon-themes"])
            assert "firefox" in results
            assert results["firefox"]["gtk-3-themes"] is True
            assert results["firefox"]["icon-themes"] is True
