# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Flatpak wizard idempotence, sequence execution, and error recovery."""

import time
from unittest.mock import MagicMock, patch

import pytest
from gi.repository import GLib

from gnome_theme_manager.core.models import FlatpakStatus, WizardStepInfo, WizardStepResult
from gnome_theme_manager.core.sandbox_bridge import SandboxBridge
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.widgets.flatpak_wizard import FlatpakWizardDialog


def _drain_events(max_iterations: int = 50) -> None:
    """Drain pending GLib/GTK main loop events."""
    ctx = GLib.MainContext.default()
    for _ in range(max_iterations):
        if ctx.pending():
            ctx.iteration(False)
        else:
            break


# =====================================================================
# 1. CORE IDEMPOTENCE & COMMAND SAFETY TESTS
# =====================================================================


def test_core_flathub_step_idempotence_command_flags() -> None:
    """Verify Flathub setup command includes --if-not-exists in both scopes."""
    bridge = SandboxBridge()
    steps = bridge.get_wizard_steps(user_mode=True)
    flathub_step = next(s for s in steps if s.step_id == "add_flathub")

    # Command must contain --if-not-exists for idempotent re-execution
    assert "--if-not-exists" in flathub_step.command_user
    assert "--if-not-exists" in flathub_step.command_system
    assert "https://dl.flathub.org/repo/flathub.flatpakrepo" in flathub_step.command_user


def test_core_step_satisfaction_flags_when_already_configured() -> None:
    """Verify is_satisfied is True when components are already detected."""
    bridge = SandboxBridge()
    mock_status = FlatpakStatus(
        flatpak_installed=True,
        flathub_configured=True,
        extension_manager_installed=True,
        user_themes_enabled=True,
    )

    with patch.object(bridge, "check_flatpak_status", return_value=mock_status):
        steps = bridge.get_wizard_steps(user_mode=True)
        for s in steps:
            assert s.is_satisfied is True, f"Step {s.step_id} should be satisfied"


def test_core_step_execution_single_and_sequence() -> None:
    """Verify executing steps individually or sequentially produces correct output."""
    bridge = SandboxBridge()
    step = WizardStepInfo(
        step_id="test_step",
        title="Test Step",
        description="Testing step execution",
        command_user="echo 'Configuring component'",
        command_system="echo 'Configuring component'",
        is_satisfied=False,
    )

    progress_messages: list[str] = []

    # Single step execution
    result = bridge.execute_wizard_step(
        step=step,
        user_mode=True,
        on_progress=lambda line: progress_messages.append(line),
    )

    assert result.success is True
    assert result.returncode == 0
    assert "Configuring component" in result.output
    assert any("Configuring component" in msg for msg in progress_messages)

    # Sequence execution of two steps
    step2 = WizardStepInfo(
        step_id="test_step_2",
        title="Test Step 2",
        description="Testing second step",
        command_user="echo 'Second component done'",
        command_system="echo 'Second component done'",
        is_satisfied=False,
    )

    seq_results = [
        bridge.execute_wizard_step(step=s, user_mode=True)
        for s in [step, step2]
    ]

    assert all(r.success for r in seq_results)
    assert seq_results[0].step_id == "test_step"
    assert seq_results[1].step_id == "test_step_2"


def test_core_step_idempotent_reexecution_succeeds() -> None:
    """Verify running an idempotent command (such as with --if-not-exists) twice succeeds."""
    bridge = SandboxBridge()
    step = WizardStepInfo(
        step_id="add_flathub",
        title="Add Flathub",
        description="Add Flathub",
        command_user="echo 'Remote already exists (ignored)'",
        command_system="echo 'Remote already exists (ignored)'",
        is_satisfied=True,
    )

    # First execution
    r1 = bridge.execute_wizard_step(step, user_mode=True)
    assert r1.success is True
    assert r1.returncode == 0

    # Second execution (idempotent re-run)
    r2 = bridge.execute_wizard_step(step, user_mode=True)
    assert r2.success is True
    assert r2.returncode == 0


# =====================================================================
# 2. GUI IDEMPOTENCE & ALREADY SATISFIED BEHAVIOR
# =====================================================================


def test_gui_wizard_idempotence_display(mock_theme_manager: MagicMock) -> None:
    """Verify satisfied steps are unchecked by default and display satisfied banner in step page."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_steps = [
        WizardStepInfo(
            step_id="add_flathub",
            title="Add Flathub",
            description="Flathub repository",
            command_user="flatpak remote-add --if-not-exists --user flathub ...",
            command_system="flatpak remote-add --if-not-exists flathub ...",
            is_satisfied=True,
        ),
        WizardStepInfo(
            step_id="install_ext_mgr",
            title="Install Extension Manager",
            description="Extension Manager app",
            command_user="flatpak install -y ...",
            command_system="flatpak install -y ...",
            is_satisfied=False,
        ),
    ]
    mock_theme_manager.get_flatpak_wizard_steps.return_value = mock_steps

    wizard = FlatpakWizardDialog(manager=mock_theme_manager)

    # add_flathub is already satisfied, so it should not be checked by default
    assert "add_flathub" not in wizard.selected_step_ids
    assert "install_ext_mgr" in wizard.selected_step_ids
    assert wizard.step_results.get("add_flathub") == "already_satisfied"

    # If the user explicitly checks add_flathub and starts the wizard
    wizard.selected_step_ids.add("add_flathub")
    wizard.start_btn.emit("clicked")
    _drain_events()

    # Step page for add_flathub should be active
    assert wizard.stack.get_visible_child_name() == "step_add_flathub"
    step_page = wizard.stack.get_child_by_name("step_add_flathub")
    assert step_page is not None


# =====================================================================
# 3. GUI ERROR RECOVERY: 3 RECOVERY OPTIONS
# =====================================================================


def test_gui_wizard_error_recovery_cancel_all(mock_theme_manager: MagicMock) -> None:
    """Verify Recovery Option 3 ('Cancel All' / 'Annulla tutto') closes the wizard dialog."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    step = WizardStepInfo(
        step_id="step_fail",
        title="Failing Step",
        description="This step will fail",
        command_user="false",
        command_system="false",
        is_satisfied=False,
    )
    mock_theme_manager.get_flatpak_wizard_steps.return_value = [step]
    mock_theme_manager.execute_wizard_step.return_value = WizardStepResult(
        step_id="step_fail",
        success=False,
        command="false",
        output="Simulated failure",
        returncode=1,
        error_message="Command exited with code 1",
    )

    wizard = FlatpakWizardDialog(manager=mock_theme_manager)
    wizard.selected_step_ids = {"step_fail"}
    wizard.start_btn.emit("clicked")
    _drain_events()

    step_page = wizard.stack.get_child_by_name("step_step_fail")
    assert step_page is not None

    sub_stack = wizard.step_sub_stacks["step_fail"]
    install_btn = wizard.step_install_btns["step_fail"]
    cancel_all_btn = wizard.step_cancel_all_btns["step_fail"]

    # Trigger install to cause failure
    install_btn.emit("clicked")

    for _ in range(50):
        _drain_events()
        if not wizard._is_executing:
            break
        time.sleep(0.02)

    _drain_events()
    assert wizard.step_results.get("step_fail") == "failed"
    assert sub_stack.get_visible_child_name() == "error"

    # Click Option 3: Cancel All
    with patch.object(wizard.window, "close") as mock_close:
        cancel_all_btn.emit("clicked")
        mock_close.assert_called_once()


def test_gui_wizard_error_recovery_skip_and_continue(mock_theme_manager: MagicMock) -> None:
    """Verify Recovery Option 2 ('Skip and Continue' / 'Salta e continua') advances to next step."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    step1 = WizardStepInfo(
        step_id="step_fail",
        title="Failing Step",
        description="Fails first",
        command_user="false",
        command_system="false",
        is_satisfied=False,
    )
    step2 = WizardStepInfo(
        step_id="step_ok",
        title="Second Step",
        description="Second step succeeds",
        command_user="true",
        command_system="true",
        is_satisfied=False,
    )
    mock_theme_manager.get_flatpak_wizard_steps.return_value = [step1, step2]
    mock_theme_manager.execute_wizard_step.return_value = WizardStepResult(
        step_id="step_fail",
        success=False,
        command="false",
        output="Failed",
        returncode=1,
        error_message="Failed",
    )

    wizard = FlatpakWizardDialog(manager=mock_theme_manager)
    wizard.selected_step_ids = {"step_fail", "step_ok"}
    wizard.start_btn.emit("clicked")
    _drain_events()

    sub_stack1 = wizard.step_sub_stacks["step_fail"]
    install_btn = wizard.step_install_btns["step_fail"]
    skip_err_btn = wizard.step_skip_err_btns["step_fail"]

    # Trigger failure on step 1
    install_btn.emit("clicked")

    for _ in range(50):
        _drain_events()
        if not wizard._is_executing:
            break
        time.sleep(0.02)

    _drain_events()
    assert sub_stack1.get_visible_child_name() == "error"

    # Click Option 2: Skip and Continue
    skip_err_btn.emit("clicked")
    _drain_events()

    # Step 1 should be marked skipped, and view should move to step 2
    assert wizard.step_results.get("step_fail") == "skipped"
    assert wizard.stack.get_visible_child_name() == "step_step_ok"


def test_gui_wizard_error_recovery_retry(mock_theme_manager: MagicMock) -> None:
    """Verify Recovery Option 1 ('Retry' / 'Riprova') re-executes the step."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    step = WizardStepInfo(
        step_id="step_retry",
        title="Retry Step",
        description="Fails once, then retried",
        command_user="echo 'test'",
        command_system="echo 'test'",
        is_satisfied=False,
    )
    mock_theme_manager.get_flatpak_wizard_steps.return_value = [step]

    # First run fails, second run succeeds
    fail_result = WizardStepResult(
        step_id="step_retry",
        success=False,
        command="test",
        output="Temporary lock error",
        returncode=1,
        error_message="Temporary lock error",
    )
    ok_result = WizardStepResult(
        step_id="step_retry",
        success=True,
        command="test",
        output="Done!",
        returncode=0,
    )
    mock_theme_manager.execute_wizard_step.side_effect = [fail_result, ok_result]

    wizard = FlatpakWizardDialog(manager=mock_theme_manager)
    wizard.selected_step_ids = {"step_retry"}
    wizard.start_btn.emit("clicked")
    _drain_events()

    sub_stack = wizard.step_sub_stacks["step_retry"]
    install_btn = wizard.step_install_btns["step_retry"]
    retry_btn = wizard.step_retry_btns["step_retry"]

    # Trigger first execution -> failure
    install_btn.emit("clicked")

    for _ in range(50):
        _drain_events()
        if not wizard._is_executing:
            break
        time.sleep(0.02)

    _drain_events()
    assert wizard.step_results.get("step_retry") == "failed"
    assert sub_stack.get_visible_child_name() == "error"

    # Click Option 1: Retry -> triggers second execution which succeeds
    retry_btn.emit("clicked")

    for _ in range(50):
        _drain_events()
        if not wizard._is_executing:
            break
        time.sleep(0.02)

    _drain_events()
    assert wizard.step_results.get("step_retry") == "installed"
    assert sub_stack.get_visible_child_name() == "success"
