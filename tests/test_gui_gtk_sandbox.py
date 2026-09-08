# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.models import (
    PropagationResult,
    SandboxStatus,
    ThemeSet,
)
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.sandbox import SandboxPage


def test_sandbox_page_initial_and_button_labels(mock_theme_manager: MagicMock) -> None:
    """Verify that SandboxPage configures native labels and icons for all buttons."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = SandboxPage(manager=mock_theme_manager)

    buttons = [
        (page.sandbox_help_button, "Sandbox Guide", "help-about-symbolic"),
        (page.refresh_button, "Refresh Status", "emblem-synchronizing-symbolic"),
        (page.flatpak_wizard_button, "Configure", "system-software-install-symbolic"),
        (page.propagate_button, "Propagate Themes", "emblem-ok-symbolic"),
        (page.error_retry_button, "Retry", "emblem-synchronizing-symbolic"),
    ]

    for btn, expected_label, expected_icon in buttons:
        assert btn.get_label() == expected_label, f"Incorrect label: {expected_label}"
        assert btn.get_icon_name() == expected_icon, f"Incorrect icon: {expected_icon}"


def test_sandbox_page_refresh_flatpak_and_snap_available(mock_theme_manager: MagicMock) -> None:
    """Verify correct diagnostics presentation when Flatpak and Snap are available."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=True,
        snap_gtk_common_themes_installed=True,
        flatpak_filesystem_override_active=True,
    )
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="Yaru")

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Available" in page.flatpak_status_row.get_subtitle()
    assert "Active" in page.flatpak_override_row.get_subtitle()
    assert "Available" in page.snap_status_row.get_subtitle()
    assert "Installed" in page.snap_gtk_common_row.get_subtitle()
    assert "natively supported" in page.snap_theme_compat_row.get_subtitle()
    assert page.propagate_button.get_sensitive() is True


def test_sandbox_page_refresh_neither_available_disables_propagate(
    mock_theme_manager: MagicMock,
) -> None:
    """Verify that if neither Flatpak nor Snap is available, propagation button is disabled."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        snap_available=False,
        flatpak_available=False,
        snap_gtk_common_themes_installed=False,
        flatpak_filesystem_override_active=False,
    )
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Not installed" in page.flatpak_status_row.get_subtitle()
    assert "Not installed" in page.snap_status_row.get_subtitle()
    assert page.propagate_button.get_sensitive() is False


def test_sandbox_page_snap_custom_theme_warning(mock_theme_manager: MagicMock) -> None:
    """Verify warning for custom theme not included in gtk-common-themes."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=False,
        snap_gtk_common_themes_installed=True,
    )
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="CustomNordic")

    page = SandboxPage(manager=mock_theme_manager)
    with patch(
        "gnome_theme_manager.core.theme_snap_manager.connector.SnapConnector.get_installed_snaps",
        return_value=[],
    ):
        page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert page.active_gtk_row.get_subtitle() == "CustomNordic"
    assert "custom" in page.snap_theme_compat_row.get_subtitle().lower()
    assert "Not installed" in page.snap_installed_content_row.get_subtitle()


def test_sandbox_page_snap_missing_gtk_common_themes(mock_theme_manager: MagicMock) -> None:
    """Verify reporting when gtk-common-themes is not installed in Snap."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=False,
        snap_gtk_common_themes_installed=False,
    )
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="Yaru")

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Not installed" in page.snap_gtk_common_row.get_subtitle()
    assert "Not verifiable" in page.snap_theme_compat_row.get_subtitle()


def test_sandbox_page_refresh_error_state(mock_theme_manager: MagicMock) -> None:
    """Verify transition to 'error' state on exception during diagnostic retrieval."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.side_effect = OSError("Subprocess failed")

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"
    assert "Subprocess failed" in page.error_status_page.get_description()


def test_sandbox_page_propagation_confirmed_success(mock_theme_manager: MagicMock) -> None:
    """Verify that confirmed propagation invokes manager.propagate_sandbox and displays feedback."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        flatpak_available=True,
        snap_available=True,
    )
    mock_theme_manager.propagate_sandbox.return_value = PropagationResult(
        flatpak_success=True,
        snap_success=True,
        warnings=[],
    )

    page = SandboxPage(manager=mock_theme_manager)
    toasts: list[str] = []
    page._show_toast = lambda msg, **kwargs: toasts.append(msg)

    called_back = False

    def on_prop_cb() -> None:
        nonlocal called_back
        called_back = True

    page.on_sandbox_propagated = on_prop_cb

    page._run_propagation(sync=True)

    mock_theme_manager.propagate_sandbox.assert_called_once()
    assert len(toasts) == 1
    assert "successfully" in toasts[0].lower()
    assert called_back is True


def test_sandbox_page_propagation_partial_warnings(mock_theme_manager: MagicMock) -> None:
    """Verify that partial outcomes with warnings produce clear feedback."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        flatpak_available=True,
        snap_available=True,
    )
    mock_theme_manager.propagate_sandbox.return_value = PropagationResult(
        flatpak_success=True,
        snap_success=False,
        warnings=["Lo snap gtk-common-themes non è presente"],
    )

    page = SandboxPage(manager=mock_theme_manager)
    toasts: list[str] = []
    page._show_toast = lambda msg, **kwargs: toasts.append(msg)

    page._run_propagation(sync=True)

    assert len(toasts) == 1
    assert "avvisi" in toasts[0].lower() or "gtk-common-themes" in toasts[0]


def test_sandbox_page_window_wiring(mock_theme_manager: MagicMock) -> None:
    """Verify that in GnomeThemeWindow the on_sandbox_propagated callback refreshes the Status page."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:
        pytest.skip(f"Display unavailable in headless environment: {err}")

    with patch.object(win.status_page, "refresh") as mock_status_refresh:
        win.sandbox_page.on_sandbox_propagated()
        mock_status_refresh.assert_called_once()


def test_sandbox_page_snap_visibility_and_help_dialog(mock_theme_manager: MagicMock) -> None:
    """Verify conditional visibility of Snap group and opening of help dialog."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        snap_available=False,
        flatpak_available=True,
        snap_gtk_common_themes_installed=False,
        flatpak_filesystem_override_active=True,
    )

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.snap_group is not None
    assert page.snap_group.get_visible() is False
    assert page.flatpak_group is not None
    assert page.flatpak_group.get_visible() is True

    # Test clicking help button
    from gi.repository import Adw

    with patch.object(Adw.Window, "present"):
        page._on_help_clicked(page.sandbox_help_button)


def test_sandbox_page_wizard_dialog_opens(mock_theme_manager: MagicMock) -> None:
    """Verify that clicking wizard button opens FlatpakWizardDialog."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 unavailable.")

    page = SandboxPage(manager=mock_theme_manager)
    with patch("gnome_theme_manager.gui_gtk.pages.sandbox.FlatpakWizardDialog") as mock_dlg_cls:
        mock_instance = MagicMock()
        mock_dlg_cls.return_value = mock_instance
        page.flatpak_wizard_button.emit("clicked")
        mock_dlg_cls.assert_called_once()
        mock_instance.present.assert_called_once()

