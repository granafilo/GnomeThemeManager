# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for FlatpakWizardDialog GUI widget."""

from unittest.mock import MagicMock, patch

import pytest
from gi.repository import GLib

from gnome_theme_manager.core.models import WizardStepInfo
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


@pytest.fixture
def mock_steps() -> list[WizardStepInfo]:
    """Return mock wizard steps."""
    return [
        WizardStepInfo(
            step_id="install_flatpak",
            title="Install Flatpak",
            description="Install Flatpak package",
            command_user="apt install flatpak",
            command_system="pkexec apt install flatpak",
            is_satisfied=False,
        ),
        WizardStepInfo(
            step_id="add_flathub",
            title="Add Flathub",
            description="Add Flathub remote",
            command_user="flatpak remote-add --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo",
            command_system="pkexec flatpak remote-add flathub https://dl.flathub.org/repo/flathub.flatpakrepo",
            is_satisfied=True,
        ),
    ]


def test_flatpak_wizard_init(mock_theme_manager: MagicMock, mock_steps: list[WizardStepInfo]) -> None:
    """Verify wizard dialog initializes with correct title, steps, and selection."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_flatpak_wizard_steps.return_value = mock_steps

    wizard = FlatpakWizardDialog(manager=mock_theme_manager)
    assert wizard.window.get_title() == "Dependency Setup Wizard"
    assert wizard.stack.get_visible_child_name() == "overview"
    assert wizard.user_mode is True
    # Only unsatisfied step is selected by default
    assert "install_flatpak" in wizard.selected_step_ids
    assert "add_flathub" not in wizard.selected_step_ids
    assert wizard.step_results.get("add_flathub") == "already_satisfied"


def test_flatpak_wizard_scope_toggle(mock_theme_manager: MagicMock, mock_steps: list[WizardStepInfo]) -> None:
    """Verify toggling scope switch updates user_mode and reloads steps."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_flatpak_wizard_steps.return_value = mock_steps

    wizard = FlatpakWizardDialog(manager=mock_theme_manager)
    assert wizard.user_mode is True

    # Switch to system mode
    wizard.scope_switch.set_active(False)
    _drain_events()
    assert wizard.user_mode is False
    assert "System-Wide" in wizard.scope_row.get_title()


def test_flatpak_wizard_step_navigation_and_completion(
    mock_theme_manager: MagicMock, mock_steps: list[WizardStepInfo]
) -> None:
    """Verify step-by-step navigation, skip/install actions, and summary page."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    completed_called = False

    def on_complete() -> None:
        nonlocal completed_called
        completed_called = True

    mock_theme_manager.get_flatpak_wizard_steps.return_value = mock_steps

    wizard = FlatpakWizardDialog(manager=mock_theme_manager, on_completed=on_complete)

    # Select both steps for testing navigation
    wizard.selected_step_ids.add("add_flathub")

    # Start wizard
    wizard.start_btn.emit("clicked")
    _drain_events()
    assert wizard.stack.get_visible_child_name() == "step_install_flatpak"
    assert wizard.back_button.get_visible() is True

    # Test back button to overview
    wizard.back_button.emit("clicked")
    _drain_events()
    assert wizard.stack.get_visible_child_name() == "overview"

    # Re-enter wizard
    wizard.start_btn.emit("clicked")
    _drain_events()

    # Skip step 1
    wizard._on_step_skip(mock_steps[0])
    _drain_events()
    assert wizard.step_results["install_flatpak"] == "skipped"
    assert wizard.stack.get_visible_child_name() == "step_add_flathub"

    # Install step 2
    wizard._on_step_install(mock_steps[1])
    _drain_events()
    assert wizard.step_results["add_flathub"] == "installed"
    assert wizard.stack.get_visible_child_name() == "summary"

    # Close on summary
    with patch.object(wizard.window, "close") as mock_close:
        wizard._on_finish_clicked(MagicMock())
        mock_close.assert_called_once()
        assert completed_called is True
