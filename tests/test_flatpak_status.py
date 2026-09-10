# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for FlatpakStatus and check_flatpak_status() detection."""

import subprocess
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core import (
    FlatpakRepairResult,
    FlatpakStatus,
    PropagationResult,
    SandboxBridge,
    ThemeManager,
    check_flatpak_status,
    repair_and_propagate_flatpak,
    repair_flatpak,
)


def test_flatpak_status_dataclass_defaults() -> None:
    """Verify FlatpakStatus dataclass default values."""
    status = FlatpakStatus()
    assert status.flatpak_installed is False
    assert status.flathub_configured is False
    assert status.extension_manager_installed is False
    assert status.user_themes_enabled is False


def test_check_flatpak_status_when_flatpak_not_installed() -> None:
    """Verify check_flatpak_status when Flatpak is absent."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_user_theme_enabled.return_value = True

    with (
        patch("shutil.which", return_value=None),
        patch(
            "gnome_theme_manager.core.sandbox_bridge.is_in_flatpak_sandbox",
            return_value=False,
        ),
    ):
        status = bridge.check_flatpak_status(extensions_manager=mock_ext_mgr)
        assert status.flatpak_installed is False
        assert status.flathub_configured is False
        assert status.extension_manager_installed is False
        assert status.user_themes_enabled is True


def test_check_flatpak_status_flathub_and_extension_manager_installed() -> None:
    """Verify all flags True when flatpak, flathub, and extension-manager are present."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_user_theme_enabled.return_value = True

    def fake_subprocess_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "remotes" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="flathub\nfedora\n",
                stderr="",
            )
        elif "info" in cmd and "com.mattjakeman.ExtensionManager" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="com.mattjakeman.ExtensionManager 0.6.0",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch("subprocess.run", side_effect=fake_subprocess_run),
    ):
        status = bridge.check_flatpak_status(user_mode=None, extensions_manager=mock_ext_mgr)
        assert status.flatpak_installed is True
        assert status.flathub_configured is True
        assert status.extension_manager_installed is True
        assert status.user_themes_enabled is True


def test_check_flatpak_status_flathub_missing() -> None:
    """Verify flathub_configured is False when flathub is not in remotes list."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_user_theme_enabled.return_value = False
    mock_ext_mgr.is_extension_manager_installed.return_value = False

    def fake_subprocess_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "remotes" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="fedora\ncustom-remote\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/flatpak" if name == "flatpak" else None,
        ),
        patch("subprocess.run", side_effect=fake_subprocess_run),
    ):
        status = bridge.check_flatpak_status(user_mode=True, extensions_manager=mock_ext_mgr)
        assert status.flatpak_installed is True
        assert status.flathub_configured is False
        assert status.extension_manager_installed is False
        assert status.user_themes_enabled is False


def test_check_flatpak_status_native_extension_manager_fallback() -> None:
    """Verify extension_manager_installed is True when installed natively via system package."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_user_theme_enabled.return_value = False

    def fake_which(name: str) -> str | None:
        if name in ("flatpak", "extension-manager"):
            return f"/usr/bin/{name}"
        return None

    def fake_subprocess_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        # Remotes succeeds with flathub, but flatpak info fails (not in flatpak)
        if "remotes" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="flathub\n", stderr=""
            )
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="Not found")

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("subprocess.run", side_effect=fake_subprocess_run),
    ):
        status = bridge.check_flatpak_status(user_mode=None, extensions_manager=mock_ext_mgr)
        assert status.flatpak_installed is True
        assert status.flathub_configured is True
        assert status.extension_manager_installed is True


def test_check_flatpak_status_user_and_system_modes() -> None:
    """Verify user_mode flags are correctly passed to flatpak commands."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_user_theme_enabled.return_value = False
    recorded_commands: list[list[str]] = []

    def fake_subprocess_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded_commands.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="flathub\n", stderr="")

    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch("subprocess.run", side_effect=fake_subprocess_run),
    ):
        # User mode
        bridge.check_flatpak_status(user_mode=True, extensions_manager=mock_ext_mgr)
        assert any("--user" in cmd for cmd in recorded_commands)
        assert not any("--system" in cmd for cmd in recorded_commands)

        recorded_commands.clear()

        # System mode
        bridge.check_flatpak_status(user_mode=False, extensions_manager=mock_ext_mgr)
        assert any("--system" in cmd for cmd in recorded_commands)
        assert not any("--user" in cmd for cmd in recorded_commands)


def test_check_flatpak_status_subprocess_errors_handled_gracefully() -> None:
    """Verify exceptions during subprocess execution do not crash detection."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_user_theme_enabled.side_effect = RuntimeError("dconf locked")
    mock_ext_mgr.is_extension_manager_installed.return_value = False

    with (
        patch(
            "shutil.which",
            side_effect=lambda name: "/usr/bin/flatpak" if name == "flatpak" else None,
        ),
        patch("subprocess.run", side_effect=subprocess.SubprocessError("Process error")),
    ):
        status = bridge.check_flatpak_status(extensions_manager=mock_ext_mgr)
        assert status.flatpak_installed is True
        assert status.flathub_configured is False
        assert status.extension_manager_installed is False
        assert status.user_themes_enabled is False


def test_check_flatpak_status_module_level_and_theme_manager() -> None:
    """Verify module-level function and ThemeManager method work and delegate properly."""
    with patch(
        "gnome_theme_manager.core.sandbox_bridge.SandboxBridge.check_flatpak_status"
    ) as mock_check:
        mock_check.return_value = FlatpakStatus(
            flatpak_installed=True,
            flathub_configured=True,
            extension_manager_installed=True,
            user_themes_enabled=True,
        )

        res_func = check_flatpak_status(user_mode=True)
        assert res_func.flatpak_installed is True

        manager = ThemeManager(sandbox_bridge=SandboxBridge())
        res_mgr = manager.check_flatpak_status(user_mode=False)
        assert res_mgr.flathub_configured is True


def test_repair_flatpak_user_success() -> None:
    """Verify repair_flatpak executes flatpak repair --user and streams lines."""
    bridge = SandboxBridge()
    progress_lines: list[str] = []

    mock_process = MagicMock()
    mock_process.stdout = iter(["[1/3] Verifying...", "[2/3] Checking...", "Done!"])
    mock_process.returncode = 0
    mock_process.wait.return_value = None

    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch("subprocess.Popen", return_value=mock_process) as mock_popen,
    ):
        res = bridge.repair_flatpak(
            user_mode=True,
            on_progress=lambda line: progress_lines.append(line),
        )
        assert res.success is True
        assert res.returncode == 0
        assert res.command == ["flatpak", "repair", "--user"]
        assert "Done!" in res.output
        assert len(progress_lines) == 3
        mock_popen.assert_called_once()


def test_repair_flatpak_system_with_pkexec() -> None:
    """Verify repair_flatpak with system mode and pkexec for non-root users."""
    bridge = SandboxBridge()
    mock_process = MagicMock()
    mock_process.stdout = iter(["System repair ok"])
    mock_process.returncode = 0
    mock_process.wait.return_value = None

    def fake_which(cmd: str) -> str | None:
        if cmd in ("flatpak", "pkexec"):
            return f"/usr/bin/{cmd}"
        return None

    with (
        patch("shutil.which", side_effect=fake_which),
        patch("os.geteuid", return_value=1000, create=True),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        res = bridge.repair_flatpak(user_mode=False, use_pkexec=True)
        assert res.success is True
        assert res.command == ["pkexec", "flatpak", "repair", "--system"]


def test_repair_flatpak_not_installed() -> None:
    """Verify repair_flatpak returns failure immediately when flatpak is not present."""
    bridge = SandboxBridge()
    with (
        patch("shutil.which", return_value=None),
        patch("gnome_theme_manager.core.sandbox_bridge.is_in_flatpak_sandbox", return_value=False),
    ):
        res = bridge.repair_flatpak()
        assert res.success is False
        assert "not installed" in res.output.lower() or "not found" in res.error_message.lower()


def test_repair_and_propagate_flatpak_combined() -> None:
    """Verify repair_and_propagate_flatpak runs repair then propagates overrides."""
    bridge = SandboxBridge()
    fake_repair = FlatpakRepairResult(
        success=True, command=["flatpak", "repair", "--user"], output="OK"
    )
    fake_prop = PropagationResult(flatpak_success=True, flatpak_messages=["Overrides applied"])

    with (
        patch.object(bridge, "repair_flatpak", return_value=fake_repair) as mock_rep,
        patch.object(bridge, "propagate_to_flatpak", return_value=fake_prop) as mock_prop,
    ):
        res_rep, res_prop = bridge.repair_and_propagate_flatpak(
            user_mode=True,
            gtk_theme="Adwaita",
            icon_theme="Papirus",
        )
        assert res_rep.success is True
        assert res_prop.flatpak_success is True
        mock_rep.assert_called_once()
        mock_prop.assert_called_once_with(gtk_theme="Adwaita", icon_theme="Papirus")


def test_theme_manager_delegates_repair() -> None:
    """Verify ThemeManager delegates repair_flatpak and repair_and_propagate_flatpak to SandboxBridge."""
    mock_bridge = MagicMock()
    mock_bridge.repair_flatpak.return_value = FlatpakRepairResult(success=True)
    mock_bridge.repair_and_propagate_flatpak.return_value = (
        FlatpakRepairResult(success=True),
        PropagationResult(flatpak_success=True),
    )

    manager = ThemeManager(sandbox_bridge=mock_bridge)
    res1 = manager.repair_flatpak(user_mode=True)
    assert res1.success is True
    mock_bridge.repair_flatpak.assert_called_once()

    res_rep, res_prop = manager.repair_and_propagate_flatpak(user_mode=False)
    assert res_rep.success is True
    assert res_prop.flatpak_success is True
    mock_bridge.repair_and_propagate_flatpak.assert_called_once()


def test_module_level_repair_functions() -> None:
    """Verify module-level repair functions delegate to SandboxBridge instance."""
    fake_rep = FlatpakRepairResult(success=True)
    fake_prop = PropagationResult(flatpak_success=True)

    with (
        patch(
            "gnome_theme_manager.core.sandbox_bridge.SandboxBridge.repair_flatpak",
            return_value=fake_rep,
        ) as m_rep,
        patch(
            "gnome_theme_manager.core.sandbox_bridge.SandboxBridge.repair_and_propagate_flatpak",
            return_value=(fake_rep, fake_prop),
        ) as m_both,
    ):
        r1 = repair_flatpak(user_mode=True)
        assert r1.success is True
        m_rep.assert_called_once()

        r2, p2 = repair_and_propagate_flatpak(user_mode=False)
        assert r2.success is True
        assert p2.flatpak_success is True
        m_both.assert_called_once()


def test_get_wizard_steps_content_and_satisfaction() -> None:
    """Verify get_wizard_steps returns 4 expected steps and reflects satisfaction flags."""
    bridge = SandboxBridge()
    mock_status = FlatpakStatus(
        flatpak_installed=True,
        flathub_configured=False,
        extension_manager_installed=False,
        user_themes_enabled=True,
    )

    with patch.object(bridge, "check_flatpak_status", return_value=mock_status):
        steps = bridge.get_wizard_steps(user_mode=True)
        assert len(steps) == 4
        step_ids = [s.step_id for s in steps]
        assert step_ids == [
            "install_flatpak",
            "add_flathub",
            "install_extension_manager",
            "enable_user_themes",
        ]

        # Check satisfaction flags
        assert steps[0].is_satisfied is True
        assert steps[1].is_satisfied is False
        assert steps[2].is_satisfied is False
        assert steps[3].is_satisfied is True

        # Check commands
        assert "flathub.flatpakrepo" in steps[1].command_user
        assert "com.mattjakeman.ExtensionManager" in steps[2].command_user
        assert "gnome-extensions enable" in steps[3].command_user


def test_theme_manager_and_module_get_wizard_steps() -> None:
    """Verify ThemeManager and module level get_flatpak_wizard_steps work correctly."""
    from gnome_theme_manager.core import WizardStepInfo, get_flatpak_wizard_steps

    mock_step = WizardStepInfo(
        step_id="mock_step",
        title="Mock Title",
        description="Mock Desc",
        command_user="echo 1",
        command_system="echo 2",
    )

    mock_bridge = MagicMock()
    mock_bridge.get_wizard_steps.return_value = [mock_step]

    manager = ThemeManager(sandbox_bridge=mock_bridge)
    res_mgr = manager.get_flatpak_wizard_steps(user_mode=True)
    assert len(res_mgr) == 1
    assert res_mgr[0].step_id == "mock_step"
    mock_bridge.get_wizard_steps.assert_called_once()

    with patch(
        "gnome_theme_manager.core.sandbox_bridge.SandboxBridge.get_wizard_steps",
        return_value=[mock_step],
    ):
        res_mod = get_flatpak_wizard_steps(user_mode=False)
        assert len(res_mod) == 1
        assert res_mod[0].title == "Mock Title"


def test_check_flatpak_status_detects_extension_manager_via_extensions_manager() -> None:
    """Verify check_flatpak_status reflects is_extension_manager_installed from ExtensionsManager."""
    bridge = SandboxBridge()
    mock_ext_mgr = MagicMock()
    mock_ext_mgr.is_extension_manager_installed.return_value = True
    mock_ext_mgr.is_user_theme_enabled.return_value = True

    with (
        patch("shutil.which", return_value="/usr/bin/flatpak"),
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="flathub\n", stderr=""
            ),
        ),
    ):
        status = bridge.check_flatpak_status(user_mode=True, extensions_manager=mock_ext_mgr)
        assert status.extension_manager_installed is True
        mock_ext_mgr.is_extension_manager_installed.assert_called_once()


def test_execute_wizard_step_success() -> None:
    """Verify execute_wizard_step executes commands and captures streaming output."""
    from gnome_theme_manager.core import WizardStepInfo, execute_wizard_step

    step = WizardStepInfo(
        step_id="test_step",
        title="Test Step",
        description="Test description",
        command_user="echo 'Hello' && echo 'World'",
        command_system="echo 'System'",
    )

    lines: list[str] = []
    res = execute_wizard_step(step, user_mode=True, on_progress=lambda l: lines.append(l))
    assert res.success is True
    assert res.returncode == 0
    assert "Hello" in res.output
    assert "World" in res.output
    assert len(lines) >= 2


def test_execute_wizard_step_pkexec_cancellation() -> None:
    """Verify execute_wizard_step handles policykit / pkexec cancellation gracefully."""
    from gnome_theme_manager.core import WizardStepInfo, execute_wizard_step

    step = WizardStepInfo(
        step_id="test_pkexec",
        title="Root Step",
        description="Root required",
        command_user="echo 1",
        command_system="pkexec test-cmd",
    )

    mock_process = MagicMock()
    mock_process.stdout = iter(["Error: Not authorized / dismissed."])
    mock_process.returncode = 126
    mock_process.wait.return_value = None

    with (
        patch("shutil.which", return_value="/usr/bin/pkexec"),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        res = execute_wizard_step(step, user_mode=False)
        assert res.success is False
        assert res.returncode == 126
        assert (
            "cancelled" in (res.error_message or "").lower()
            or "denied" in (res.error_message or "").lower()
        )


def test_execute_wizard_step_missing_binary() -> None:
    """Verify execute_wizard_step returns failure with returncode 127 when binary is missing."""
    from gnome_theme_manager.core import WizardStepInfo, execute_wizard_step

    step = WizardStepInfo(
        step_id="test_missing",
        title="Missing",
        description="Desc",
        command_user="nonexistent_binary_foo_bar_xyz",
        command_system="nonexistent_binary_foo_bar_xyz",
    )

    with (
        patch("shutil.which", return_value=None),
        patch("gnome_theme_manager.core.sandbox_bridge.is_in_flatpak_sandbox", return_value=False),
    ):
        res = execute_wizard_step(step, user_mode=True)
        assert res.success is False
        assert res.returncode == 127
        assert "not installed" in (res.error_message or "").lower()


def test_theme_manager_execute_wizard_step_delegates() -> None:
    """Verify ThemeManager delegates execute_wizard_step to SandboxBridge."""
    from gnome_theme_manager.core import ThemeManager, WizardStepInfo, WizardStepResult

    mock_bridge = MagicMock()
    mock_step = WizardStepInfo(
        step_id="step_1",
        title="Title",
        description="Desc",
        command_user="echo 1",
        command_system="echo 2",
    )
    mock_res = WizardStepResult(step_id="step_1", success=True, command="echo 1", output="1")
    mock_bridge.execute_wizard_step.return_value = mock_res

    mgr = ThemeManager(sandbox_bridge=mock_bridge)
    res = mgr.execute_wizard_step(mock_step, user_mode=True)
    assert res.success is True
    assert res.output == "1"
    mock_bridge.execute_wizard_step.assert_called_once_with(
        step=mock_step,
        user_mode=True,
        on_progress=None,
    )
