# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for FlatpakPropagationDialog GUI widget."""

import time
from unittest.mock import MagicMock, patch

import pytest
from gi.repository import GLib

from gnome_theme_manager.core.models import FlatpakRepairResult, PropagationResult
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.widgets.flatpak_dialog import FlatpakPropagationDialog


def _drain_events(max_iterations: int = 50) -> None:
    """Drain pending GLib/GTK main loop events."""
    ctx = GLib.MainContext.default()
    for _ in range(max_iterations):
        if ctx.pending():
            ctx.iteration(False)
        else:
            break


def test_flatpak_dialog_init(mock_theme_manager: MagicMock) -> None:
    """Verify FlatpakPropagationDialog initializes with correct default state."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    dlg = FlatpakPropagationDialog(manager=mock_theme_manager)
    assert dlg.window.get_title() == "Flatpak Propagation & Repair"
    assert dlg.stack.get_visible_child_name() == "prompt"
    assert dlg.radio_user.get_active() is True
    assert dlg.radio_system.get_active() is False


def test_flatpak_dialog_ignore_closes_window(mock_theme_manager: MagicMock) -> None:
    """Verify Ignore button closes the dialog."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    dlg = FlatpakPropagationDialog(manager=mock_theme_manager)
    with patch.object(dlg.window, "close") as mock_close:
        dlg.btn_ignore.emit("clicked")
        mock_close.assert_called_once()


def test_flatpak_dialog_propagation_success(mock_theme_manager: MagicMock) -> None:
    """Verify successful repair and propagation flow."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    on_prop_called = False

    def on_prop_cb() -> None:
        nonlocal on_prop_called
        on_prop_called = True

    mock_theme_manager.repair_and_propagate_flatpak.return_value = (
        FlatpakRepairResult(
            success=True, command=["flatpak", "repair", "--user"], output="All good"
        ),
        PropagationResult(flatpak_success=True, flatpak_messages=["Overrides applied"]),
    )

    dlg = FlatpakPropagationDialog(manager=mock_theme_manager, on_propagated=on_prop_cb)
    dlg._start_propagation()

    # Wait for worker thread to complete and idle events to process
    for _ in range(100):
        _drain_events()
        if not dlg._is_running:
            break
        time.sleep(0.02)

    _drain_events()
    assert dlg.stack.get_visible_child_name() == "result"
    assert dlg.result_status_page.get_icon_name() == "emblem-ok-symbolic"
    assert on_prop_called is True


def test_flatpak_dialog_propagation_failure(mock_theme_manager: MagicMock) -> None:
    """Verify failed repair and propagation shows error on result page."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.repair_and_propagate_flatpak.return_value = (
        FlatpakRepairResult(success=False, returncode=1, error_message="Permission denied"),
        PropagationResult(flatpak_success=False, warnings=["Overrides failed"]),
    )

    dlg = FlatpakPropagationDialog(manager=mock_theme_manager)
    dlg._start_propagation()

    for _ in range(100):
        _drain_events()
        if not dlg._is_running:
            break
        time.sleep(0.02)

    _drain_events()
    assert dlg.stack.get_visible_child_name() == "result"
    assert dlg.result_status_page.get_icon_name() == "dialog-error-symbolic"
    assert "Permission denied" in dlg.result_status_page.get_description()


def test_flatpak_dialog_inhibit_close_while_running(mock_theme_manager: MagicMock) -> None:
    """Verify close request is inhibited while operation is running."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    dlg = FlatpakPropagationDialog(manager=mock_theme_manager)
    dlg._is_running = True
    assert dlg._on_close_request(dlg.window) is True
    dlg._is_running = False
    assert dlg._on_close_request(dlg.window) is False
