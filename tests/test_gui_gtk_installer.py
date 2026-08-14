# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.errors import (
    ArchiveExtractionError,
    ThemeValidationError,
)
from gnome_theme_manager.core.models import (
    ApplyResult,
    Theme,
    ThemeType,
)
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.installer import (
    InstallerPage,
    format_components_label,
)


def test_format_components_label() -> None:
    """Verifica la formattazione testuale dei tipi di tema rilevati."""
    assert format_components_label([]) == "Nessun componente riconosciuto"
    assert format_components_label([ThemeType.GTK]) == "Applicazioni (GTK)"
    assert (
        format_components_label([ThemeType.GTK, ThemeType.SHELL])
        == "Applicazioni (GTK), GNOME Shell"
    )
    # Duplicati rimossi
    assert (
        format_components_label([ThemeType.GTK, ThemeType.GTK, ThemeType.ICON])
        == "Applicazioni (GTK), Icone"
    )


def test_installer_page_initial_state(mock_theme_manager: MagicMock) -> None:
    """Verifica lo stato iniziale della pagina Installatore (stato 'initial')."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = InstallerPage(manager=mock_theme_manager)
    assert page.page_id == "installer"
    assert page.title == "Installatore temi"
    assert page.widget.get_visible_child_name() == "initial"
    assert page.select_folder_button.get_sensitive() is True
    assert page.select_archive_button.get_sensitive() is True


def test_installer_page_select_source_archive_success(mock_theme_manager: MagicMock) -> None:
    """Verifica l'analisi e il passaggio a stato 'ready' per un archivio valido."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [
        ("Nordic-Theme", ThemeType.GTK),
        ("Nordic-Theme", ThemeType.SHELL),
    ]

    page = InstallerPage(manager=mock_theme_manager)
    archive_path = Path("/tmp/Nordic-Theme.tar.xz")
    page.select_source(archive_path, sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert page.source_type_row.get_subtitle() == "Archivio compresso"
    assert page.detected_theme_name_row.get_subtitle() == "Nordic-Theme"
    assert "Applicazioni (GTK)" in page.detected_components_row.get_subtitle()
    assert "GNOME Shell" in page.detected_components_row.get_subtitle()
    assert page.install_button.get_sensitive() is True
    assert page.install_apply_button.get_sensitive() is True


def test_installer_page_select_source_directory_success(mock_theme_manager: MagicMock) -> None:
    """Verifica l'analisi e il passaggio a stato 'ready' per una cartella valida."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [
        ("Papirus-Icons", ThemeType.ICON),
    ]

    page = InstallerPage(manager=mock_theme_manager)
    folder_path = Path("/home/user/Papirus-Icons")
    page.select_source(folder_path, sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert page.detected_theme_name_row.get_subtitle() == "Papirus-Icons"
    assert "Icone" in page.detected_components_row.get_subtitle()


def test_installer_page_select_source_not_found(mock_theme_manager: MagicMock) -> None:
    """Verifica che una sorgente inesistente mostri lo stato 'error'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.side_effect = FileNotFoundError("Sorgente non trovata")

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/non/existent/theme.zip"), sync=True)

    assert page.widget.get_visible_child_name() == "error"
    desc = page.error_status_page.get_description()
    assert "Sorgente non trovata" in desc


def test_installer_page_select_source_corrupt_archive(mock_theme_manager: MagicMock) -> None:
    """Verifica che un archivio corrotto o non supportato mostri lo stato 'error'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.side_effect = ArchiveExtractionError(
        "Archivio non valido o corrotto"
    )

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/corrupt.zip"), sync=True)

    assert page.widget.get_visible_child_name() == "error"
    desc = page.error_status_page.get_description()
    assert "Archivio non valido" in desc or "corrotto" in desc


def test_installer_page_select_source_invalid_structure(mock_theme_manager: MagicMock) -> None:
    """Verifica che una cartella senza struttura di tema valida mostri errore."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.side_effect = ThemeValidationError(
        "Nessun tema riconosciuto"
    )

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/empty_folder"), sync=True)

    assert page.widget.get_visible_child_name() == "error"
    desc = page.error_status_page.get_description()
    assert "Struttura del tema non riconosciuta" in desc or "Nessun tema" in desc


def test_installer_page_reset_to_initial(mock_theme_manager: MagicMock) -> None:
    """Verifica che il pulsante 'Cambia sorgente' ripristini la vista allo stato iniziale."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [("Theme", ThemeType.GTK)]
    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/theme.zip"), sync=True)
    assert page.widget.get_visible_child_name() == "ready"

    page._on_reset_to_initial()
    assert page.widget.get_visible_child_name() == "initial"
    assert page._selected_source is None


def test_installer_page_install_success(mock_theme_manager: MagicMock) -> None:
    """Verifica l'installazione riuscita (senza applicazione automatica)."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [("MyTheme", ThemeType.GTK)]
    mock_theme_manager.install_theme.return_value = [
        Theme("MyTheme", ThemeType.GTK, Path("/dest/MyTheme"), True)
    ]

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/mytheme.zip"), sync=True)

    installed_notified = False

    def on_installed() -> None:
        nonlocal installed_notified
        installed_notified = True

    page.on_theme_installed = on_installed

    toasts: list[str] = []
    with patch.object(page, "_show_toast", side_effect=lambda msg, **kw: toasts.append(msg)):
        page._run_install(apply_after=False, sync=True)

    mock_theme_manager.install_theme.assert_called_once_with(
        source_path=Path("/tmp/mytheme.zip"),
        overwrite=False,
        target_dir="xdg",
    )
    assert page.widget.get_visible_child_name() == "success"
    assert installed_notified is True
    assert len(toasts) == 1
    assert "installato" in toasts[0].lower()


def test_installer_page_install_and_apply_success(mock_theme_manager: MagicMock) -> None:
    """Verifica 'Installa e Applica' con successo."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [("UnifiedTheme", ThemeType.GTK)]
    mock_theme_manager.install_theme.return_value = [
        Theme("UnifiedTheme", ThemeType.GTK, Path("/dest/UnifiedTheme"), True)
    ]
    mock_theme_manager.apply_themes.return_value = ApplyResult(gtk_theme="UnifiedTheme")

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/unified.zip"), sync=True)

    applied_notified = False

    def on_applied() -> None:
        nonlocal applied_notified
        applied_notified = True

    page.on_theme_applied = on_applied

    toasts: list[str] = []
    with patch.object(page, "_show_toast", side_effect=lambda msg, **kw: toasts.append(msg)):
        page._run_install(apply_after=True, sync=True)

    mock_theme_manager.install_theme.assert_called_once()
    mock_theme_manager.apply_themes.assert_called_once()
    assert page.widget.get_visible_child_name() == "success"
    assert applied_notified is True
    assert len(toasts) == 1
    assert "applicato" in toasts[0].lower()


def test_installer_page_install_and_apply_partial_warning(mock_theme_manager: MagicMock) -> None:
    """Verifica gestione di 'Installa e Applica' con risultato parziale (warning)."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [
        ("PartialTheme", ThemeType.GTK),
        ("PartialTheme", ThemeType.SHELL),
    ]
    mock_theme_manager.install_theme.return_value = [
        Theme("PartialTheme", ThemeType.GTK, Path("/dest/PartialTheme"), True),
        Theme("PartialTheme", ThemeType.SHELL, Path("/dest/PartialTheme"), True),
    ]
    mock_theme_manager.apply_themes.return_value = ApplyResult(
        gtk_theme="PartialTheme",
        warnings=["Estensione User Themes non attiva"],
    )

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/partial.zip"), sync=True)

    toasts: list[str] = []
    with patch.object(page, "_show_toast", side_effect=lambda msg, **kw: toasts.append(msg)):
        page._run_install(apply_after=True, sync=True)

    assert page.widget.get_visible_child_name() == "success"
    desc = page.success_status_page.get_description()
    assert "Alcuni componenti non sono stati applicati" in desc
    assert len(toasts) == 1
    assert "parziale" in toasts[0].lower()


def test_installer_page_install_conflict_prompts_overwrite(mock_theme_manager: MagicMock) -> None:
    """Verifica che FileExistsError apra il dialogo di conferma sovrascrittura."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [("ExistingTheme", ThemeType.GTK)]
    mock_theme_manager.install_theme.side_effect = FileExistsError("Tema già presente")

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/existing.zip"), sync=True)

    with patch.object(page, "_open_overwrite_confirm_dialog") as mock_dialog:
        page._run_install(apply_after=False, sync=True)
        mock_dialog.assert_called_once_with(apply_after=False, sync=True)


def test_installer_page_overwrite_confirmed_calls_backend_with_overwrite_true(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che confermando la sovrascrittura il backend venga chiamato con overwrite=True."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [("ExistingTheme", ThemeType.GTK)]
    mock_theme_manager.install_theme.return_value = [
        Theme("ExistingTheme", ThemeType.GTK, Path("/dest/ExistingTheme"), True)
    ]

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/existing.zip"), sync=True)

    # Simula la conferma di sovrascrittura chiamando _run_install con overwrite=True
    page._run_install(apply_after=False, overwrite=True, sync=True)

    mock_theme_manager.install_theme.assert_called_with(
        source_path=Path("/tmp/existing.zip"),
        overwrite=True,
        target_dir="xdg",
    )
    assert page.widget.get_visible_child_name() == "success"
    # La sorgente selezionata deve essere azzerata dopo il completamento
    assert page._selected_source is None
    assert page.install_button.get_sensitive() is False
    assert page.install_apply_button.get_sensitive() is False


def test_installer_page_button_labels_and_icons(mock_theme_manager: MagicMock) -> None:
    """Verifica che tutti i pulsanti dell'installer abbiano etichette di testo visibili e icone."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = InstallerPage(manager=mock_theme_manager)

    buttons = [
        (page.select_folder_button, "Seleziona cartella", "folder-open-symbolic"),
        (page.select_archive_button, "Seleziona archivio", "package-x-generic-symbolic"),
        (page.change_source_button, "Cambia sorgente", "edit-undo-symbolic"),
        (page.install_button, "Installa", "system-software-install-symbolic"),
        (page.install_apply_button, "Installa e Applica", "emblem-ok-symbolic"),
        (page.success_new_source_button, "Seleziona un'altra sorgente", "document-open-symbolic"),
        (page.error_retry_button, "Riprova", "view-refresh-symbolic"),
        (page.error_new_source_button, "Seleziona un'altra sorgente", "document-open-symbolic"),
    ]

    for btn, expected_label, expected_icon in buttons:
        assert btn.get_label() == expected_label, (
            f"Etichetta errata per il pulsante: {expected_label}"
        )
        assert btn.get_icon_name() == expected_icon, (
            f"Icona errata per il pulsante: {expected_icon}"
        )


def test_installer_page_install_error_state(mock_theme_manager: MagicMock) -> None:
    """Verifica che errori generici durante l'installazione passino allo stato 'error'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.return_value = [("ErrorTheme", ThemeType.GTK)]
    mock_theme_manager.install_theme.side_effect = OSError("Spazio su disco esaurito")

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/error.zip"), sync=True)

    page._run_install(apply_after=False, sync=True)

    assert page.widget.get_visible_child_name() == "error"
    desc = page.error_status_page.get_description()
    assert "Spazio su disco esaurito" in desc


def test_installer_page_window_wiring(mock_theme_manager: MagicMock) -> None:
    """Verifica che in GnomeThemeWindow i callback di InstallerPage rinfreschino le altre viste."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    with (
        patch.object(win.themes_page, "refresh") as mock_themes_refresh,
        patch.object(win.status_page, "refresh") as mock_status_refresh,
    ):
        win.installer_page.on_theme_installed()
        mock_themes_refresh.assert_called_once()
        mock_status_refresh.assert_not_called()

        mock_themes_refresh.reset_mock()
        mock_status_refresh.reset_mock()

        win.installer_page.on_theme_applied()
        mock_themes_refresh.assert_called_once()
        mock_status_refresh.assert_called_once()
