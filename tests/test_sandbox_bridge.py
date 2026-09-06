# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for SandboxBridge module and Snap / Flatpak integration."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    PropagationResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.core.sandbox_bridge import SandboxBridge

# =============================================================================
# 1. Binary Availability Detection Tests ($PATH)
# =============================================================================


def test_snap_available_detection() -> None:
    """Verify that is_snap_available() returns True when snap is present."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value="/usr/bin/snap"):
        assert bridge.is_snap_available() is True


def test_snap_not_available() -> None:
    """Verify that is_snap_available() returns False when snap is not installed."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None):
        assert bridge.is_snap_available() is False


def test_flatpak_available_detection() -> None:
    """Verify that is_flatpak_available() returns True when flatpak is present."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value="/usr/bin/flatpak"):
        assert bridge.is_flatpak_available() is True


def test_flatpak_not_available() -> None:
    """Verify that is_flatpak_available() returns False when flatpak is not installed."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None):
        assert bridge.is_flatpak_available() is False


# =============================================================================
# 2. Test get_sandbox_status()
# =============================================================================


def test_sandbox_status_all_active() -> None:
    """Verify correct generation of SandboxStatus when both runtimes are active."""
    bridge = SandboxBridge()

    def mock_subprocess_run(cmd: list[str], **kwargs) -> MagicMock:
        res = MagicMock()
        res.returncode = 0
        if cmd[:3] == ["snap", "list", "gtk-common-themes"]:
            res.stdout = "Name               Version    Rev   Tracking  Publisher   Notes\ngtk-common-themes  0.1-81     2125  latest/stable  canonical✓  -"
        elif cmd[:4] == ["flatpak", "override", "--user", "--show"]:
            res.stdout = "[Context]\nfilesystems=~/.local/share/themes;~/.icons;\n"
        return res

    with (
        patch("shutil.which", side_effect=lambda bin_name: f"/usr/bin/{bin_name}"),
        patch("subprocess.run", side_effect=mock_subprocess_run),
    ):
        status: SandboxStatus = bridge.get_sandbox_status()
        assert status.snap_available is True
        assert status.flatpak_available is True
        assert status.snap_gtk_common_themes_installed is True
        assert status.flatpak_filesystem_override_active is True


def test_sandbox_status_not_available() -> None:
    """Verify SandboxStatus when neither Snap nor Flatpak is installed."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None):
        status: SandboxStatus = bridge.get_sandbox_status()
        assert status.snap_available is False
        assert status.flatpak_available is False
        assert status.snap_gtk_common_themes_installed is False
        assert status.flatpak_filesystem_override_active is False


# =============================================================================
# 3. Flatpak Propagation Tests
# =============================================================================


def test_propagate_to_flatpak_success() -> None:
    """Verify that propagate_to_flatpak executes correct commands and returns flatpak_success=True."""
    bridge = SandboxBridge()
    executed_commands: list[list[str]] = []

    def mock_run(cmd: list[str], **kwargs) -> MagicMock:
        executed_commands.append(cmd)
        res = MagicMock()
        res.returncode = 0
        res.stdout = ""
        res.stderr = ""
        return res

    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch("subprocess.run", side_effect=mock_run),
    ):
        result = bridge.propagate_to_flatpak(gtk_theme="Nordic", icon_theme="Papirus")

        assert result.flatpak_success is True
        assert len(result.warnings) == 0
        assert len(result.flatpak_messages) > 0
        # Verify that all override commands and environment variables were executed
        assert [
            "flatpak",
            "override",
            "--user",
            "--filesystem=~/.local/share/themes:ro",
        ] in executed_commands
        assert ["flatpak", "override", "--user", "--filesystem=~/.themes:ro"] in executed_commands
        assert [
            "flatpak",
            "override",
            "--user",
            "--filesystem=~/.local/share/icons:ro",
        ] in executed_commands
        assert ["flatpak", "override", "--user", "--filesystem=~/.icons:ro"] in executed_commands
        assert ["flatpak", "override", "--user", "--env=GTK_THEME=Nordic"] in executed_commands
        assert ["flatpak", "override", "--user", "--env=ICON_THEME=Papirus"] in executed_commands


def test_propagate_to_flatpak_not_installed() -> None:
    """Verify that propagate_to_flatpak returns False without calling subprocess if flatpak does not exist."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None), patch("subprocess.run") as mock_run:
        result = bridge.propagate_to_flatpak(gtk_theme="Adwaita")
        assert result.flatpak_success is False
        mock_run.assert_not_called()


# =============================================================================
# 4. Snap Propagation and Compatibility Tests
# =============================================================================


def test_propagate_to_snap_with_gtk_common_themes() -> None:
    """Verify that a standard theme (e.g. Yaru) with gtk-common-themes installed succeeds."""
    bridge = SandboxBridge()
    mock_res = MagicMock()
    mock_res.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/snap"),
        patch("subprocess.run", return_value=mock_res),
    ):
        result = bridge.propagate_to_snap(gtk_theme="Yaru", icon_theme="Yaru")
        assert result.snap_success is True
        assert len(result.warnings) == 0
        assert any("natively supported" in m for m in result.snap_messages)


def test_propagate_to_snap_custom_theme_warning() -> None:
    """Verify that a custom theme not in gtk-common-themes produces an informative warning."""
    bridge = SandboxBridge()
    mock_res = MagicMock()
    mock_res.returncode = 0

    with (
        patch("shutil.which", return_value="/usr/bin/snap"),
        patch("subprocess.run", return_value=mock_res),
    ):
        result = bridge.propagate_to_snap(gtk_theme="Nordic-Darker", icon_theme="Papirus")
        assert result.snap_success is True
        assert len(result.warnings) == 1
        assert "not included in the standard" in result.warnings[0]
        assert "Theme Snap Manager" in result.warnings[0]


def test_propagate_to_snap_not_installed() -> None:
    """Verify that propagate_to_snap returns False if snap is not available."""
    bridge = SandboxBridge()
    with patch("shutil.which", return_value=None), patch("subprocess.run") as mock_run:
        result = bridge.propagate_to_snap(gtk_theme="Yaru")
        assert result.snap_success is False
        mock_run.assert_not_called()


def test_propagate_to_snap_no_gtk_common_themes() -> None:
    """Verify that propagate_to_snap reports a warning if gtk-common-themes is not installed."""
    bridge = SandboxBridge()
    mock_res = MagicMock()
    mock_res.returncode = 1  # snap list failed

    with (
        patch("shutil.which", return_value="/usr/bin/snap"),
        patch("subprocess.run", return_value=mock_res),
    ):
        result = bridge.propagate_to_snap(gtk_theme="Yaru")
        assert result.snap_success is False
        assert len(result.warnings) > 0
        assert "gtk-common-themes" in result.warnings[0]


# =============================================================================
# 5. Test propagate_all() and Results Merging
# =============================================================================


def test_propagate_all_combines_results() -> None:
    """Verify that propagate_all correctly merges messages, warnings and status of Flatpak and Snap."""
    bridge = SandboxBridge()

    flatpak_stub = PropagationResult(
        flatpak_success=True,
        flatpak_messages=["Flatpak configurato."],
        warnings=[],
    )
    snap_stub = PropagationResult(
        snap_success=True,
        snap_messages=["Snap verificato."],
        warnings=["Avviso Snap custom theme."],
    )

    with (
        patch.object(bridge, "propagate_to_flatpak", return_value=flatpak_stub),
        patch.object(bridge, "propagate_to_snap", return_value=snap_stub),
    ):
        result = bridge.propagate_all(gtk_theme="Nordic", icon_theme="Papirus")

        assert result.flatpak_success is True
        assert result.snap_success is True
        assert result.flatpak_messages == ["Flatpak configurato."]
        assert result.snap_messages == ["Snap verificato."]
        assert result.warnings == ["Avviso Snap custom theme."]


# =============================================================================
# 6. Exception and Timeout Handling Tests in Subprocess
# =============================================================================


def test_subprocess_timeout_handling() -> None:
    """Verify that TimeoutExpired in subprocess.run returns PropagationResult with flatpak_success=False and warning."""
    bridge = SandboxBridge()
    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="flatpak override", timeout=10),
        ),
    ):
        res = bridge.propagate_to_flatpak(gtk_theme="Nordic")
        assert res.flatpak_success is False
        assert len(res.warnings) == 1
        assert "Timeout" in res.warnings[0]


def test_subprocess_error_handling() -> None:
    """Verify that CalledProcessError in subprocess.run returns PropagationResult with flatpak_success=False and warning."""
    bridge = SandboxBridge()
    err = subprocess.CalledProcessError(
        returncode=1, cmd="flatpak override", stderr="Permission denied"
    )
    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch("subprocess.run", side_effect=err),
    ):
        res = bridge.propagate_to_flatpak(gtk_theme="Nordic")
        assert res.flatpak_success is False
        assert len(res.warnings) == 1
        assert "Permission denied" in res.warnings[0]


def test_subprocess_file_not_found_handling() -> None:
    """Verify that FileNotFoundError in subprocess.run returns PropagationResult with flatpak_success=False and warning."""
    bridge = SandboxBridge()
    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch("subprocess.run", side_effect=FileNotFoundError("No such file")),
    ):
        res = bridge.propagate_to_flatpak(gtk_theme="Nordic")
        assert res.flatpak_success is False
        assert len(res.warnings) == 1
        assert "Unable to execute" in res.warnings[0]


# =============================================================================
# 7. Integration Tests with ThemeManager
# =============================================================================


def test_apply_themes_with_sandbox_propagation() -> None:
    """Verify that ThemeManager.apply_themes invokes SandboxBridge and populates sandbox_propagation."""
    mock_scanner = MagicMock()
    mock_scanner.find_theme.return_value = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=Path("/home/user/.local/share/themes/Nordic"),
        is_user_level=True,
    )
    mock_gsettings = MagicMock()
    mock_gsettings.is_shell_theme_supported = True
    mock_linker = MagicMock()
    mock_linker.apply_override.return_value = True

    mock_sandbox = MagicMock()
    mock_sandbox.propagate_all.return_value = PropagationResult(
        flatpak_success=True,
        snap_success=True,
        flatpak_messages=["Flatpak OK"],
        snap_messages=["Snap OK"],
        warnings=[],
    )

    mock_validator = MagicMock()
    mock_validator.validate.return_value = MagicMock(valid=True, warnings=[], missing_files=[])

    manager = ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        gtk4_linker=mock_linker,
        sandbox_bridge=mock_sandbox,
        validator=mock_validator,
    )

    res: ApplyResult = manager.apply_themes(ThemeSet(gtk_theme="Nordic"), propagate_sandbox=True)

    assert res.sandbox_propagation is not None
    assert res.sandbox_propagation.flatpak_success is True
    mock_sandbox.propagate_all.assert_called_once_with(gtk_theme="Nordic", icon_theme=None)


def test_apply_themes_no_sandbox_flag() -> None:
    """Verify that with propagate_sandbox=False sandbox propagation is not executed."""
    mock_scanner = MagicMock()
    mock_scanner.find_theme.return_value = Theme(
        name="Nordic",
        theme_type=ThemeType.GTK,
        path=Path("/home/user/.local/share/themes/Nordic"),
        is_user_level=True,
    )
    mock_gsettings = MagicMock()
    mock_gsettings.is_shell_theme_supported = True
    mock_sandbox = MagicMock()
    mock_validator = MagicMock()
    mock_validator.validate.return_value = MagicMock(valid=True, warnings=[], missing_files=[])

    manager = ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        sandbox_bridge=mock_sandbox,
        validator=mock_validator,
    )

    res: ApplyResult = manager.apply_themes(ThemeSet(gtk_theme="Nordic"), propagate_sandbox=False)

    assert res.sandbox_propagation is None
    mock_sandbox.propagate_all.assert_not_called()


def test_manager_system_status_includes_sandbox() -> None:
    """Verify that get_system_status() includes sandbox_status."""
    mock_sandbox = MagicMock()
    mock_sandbox.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=True,
        snap_gtk_common_themes_installed=True,
        flatpak_filesystem_override_active=True,
    )
    mock_gsettings = MagicMock()
    mock_gsettings.is_shell_theme_supported = True

    manager = ThemeManager(
        gsettings=mock_gsettings,
        sandbox_bridge=mock_sandbox,
    )

    status: SystemStatus = manager.get_system_status()
    assert status.sandbox_status is not None
    assert status.sandbox_status.snap_available is True
    assert status.sandbox_status.flatpak_available is True


# =============================================================================
# 8. CLI Tests: sandbox-status and --no-sandbox flag
# =============================================================================


def test_cli_sandbox_status_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that the CLI command 'gnome-theme-manager sandbox-status' prints the correct status."""
    with patch("gnome_theme_manager.core.manager.ThemeManager.get_system_status") as mock_status:
        mock_status.return_value = SystemStatus(
            gsettings_available=True,
            shell_theme_supported=True,
            color_scheme_supported=True,
            user_themes_path=Path("/home/user/.local/share/themes"),
            user_icons_path=Path("/home/user/.local/share/icons"),
            sandbox_status=SandboxStatus(
                snap_available=True,
                flatpak_available=True,
                snap_gtk_common_themes_installed=True,
                flatpak_filesystem_override_active=False,
            ),
        )

        exit_code = main(["sandbox-status"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Sandbox Integration Status" in captured.out
        assert "Snap:" in captured.out
        assert "Flatpak:" in captured.out


def test_cli_apply_no_sandbox_flag() -> None:
    """Verify that apply command with --no-sandbox flag passes propagate_sandbox=False to manager."""
    with (
        patch("gnome_theme_manager.core.manager.ThemeManager.apply_themes") as mock_apply,
        patch("gnome_theme_manager.core.manager.ThemeManager.find_theme", return_value=True),
    ):
        mock_apply.return_value = ApplyResult(gtk_theme="Nordic", warnings=[])

        exit_code = main(["apply", "--gtk", "Nordic", "--no-sandbox"])
        assert exit_code == 0
        mock_apply.assert_called_once()
        _, kwargs = mock_apply.call_args
        assert kwargs.get("propagate_sandbox") is False


# =============================================================================
# 9. Test Sandbox Detection and Propagation inside Flatpak Container
# =============================================================================


def test_sandbox_bridge_in_container(tmp_path: Path) -> None:
    """Verify that inside Flatpak sandbox, Flatpak and Snap are detected from files and override is written."""
    bridge = SandboxBridge()
    fake_override = tmp_path / ".local" / "share" / "flatpak" / "overrides" / "global"
    fake_override.parent.mkdir(parents=True, exist_ok=True)
    fake_override.write_text("[Context]\nfilesystems=~/.local/share/themes:ro;\n")

    fake_snap = tmp_path / "snap"
    fake_snap.mkdir(parents=True, exist_ok=True)

    with (
        patch("shutil.which", return_value=None),
        patch("gnome_theme_manager.core.sandbox_bridge.is_in_flatpak_sandbox", return_value=True),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        assert bridge.is_flatpak_available() is True
        assert bridge.is_snap_available() is True

        status = bridge.get_sandbox_status()
        assert status.flatpak_available is True
        assert status.flatpak_filesystem_override_active is True
        assert status.snap_available is True

        res = bridge.propagate_to_flatpak(gtk_theme="Nordic", icon_theme="Papirus")
        assert res.flatpak_success is True
        assert fake_override.is_file()
        content = fake_override.read_text()
        assert "GTK_THEME = Nordic" in content or "gtk_theme = Nordic" in content
