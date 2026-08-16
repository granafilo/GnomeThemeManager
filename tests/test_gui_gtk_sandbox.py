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
    """Verifica che SandboxPage configuri etichette e icone native per tutti i pulsanti."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = SandboxPage(manager=mock_theme_manager)

    buttons = [
        (page.refresh_button, "Refresh Status", "view-refresh-symbolic"),
        (page.propagate_button, "Propagate Theme to Sandboxed Apps", "emblem-ok-symbolic"),
        (page.error_retry_button, "Retry", "view-refresh-symbolic"),
    ]

    for btn, expected_label, expected_icon in buttons:
        assert btn.get_label() == expected_label, f"Etichetta errata: {expected_label}"
        assert btn.get_icon_name() == expected_icon, f"Icona errata: {expected_icon}"


def test_sandbox_page_refresh_flatpak_and_snap_available(mock_theme_manager: MagicMock) -> None:
    """Verifica la corretta presentazione della diagnostica quando Flatpak e Snap sono disponibili."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

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
    """Verifica che se né Flatpak né Snap sono disponibili, il pulsante di propagazione sia disabilitato."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

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
    """Verifica l'avviso per tema personalizzato non compreso in gtk-common-themes."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=False,
        snap_gtk_common_themes_installed=True,
    )
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="CustomNordic")

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "custom" in page.snap_theme_compat_row.get_subtitle().lower()


def test_sandbox_page_snap_missing_gtk_common_themes(mock_theme_manager: MagicMock) -> None:
    """Verifica la segnalazione quando gtk-common-themes non è installato in Snap."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

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
    """Verifica la transizione allo stato 'error' in caso di eccezione durante il recupero diagnostico."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.get_sandbox_status.side_effect = OSError("Subprocess failed")

    page = SandboxPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"
    assert "Subprocess failed" in page.error_status_page.get_description()


def test_sandbox_page_propagation_confirmed_success(mock_theme_manager: MagicMock) -> None:
    """Verifica che la propagazione confermata invochi manager.propagate_sandbox e mostri feedback."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

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
    """Verifica che esiti parziali con avvisi producano un feedback chiaro."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

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
    """Verifica che in GnomeThemeWindow il callback on_sandbox_propagated aggiorni la pagina Stato."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    with patch.object(win.status_page, "refresh") as mock_status_refresh:
        win.sandbox_page.on_sandbox_propagated()
        mock_status_refresh.assert_called_once()
