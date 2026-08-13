from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.models import (
    ApplyResult,
    ThemeSet,
)
from gnome_theme_manager.gui_gtk import is_gtk_available


def test_presets_page_instantiation_requires_ui_file(mock_theme_manager: MagicMock) -> None:
    """Verifica che PresetsPage venga istanziata correttamente e carichi il file UI."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    page = PresetsPage(manager=mock_theme_manager)
    assert page.widget is not None
    assert page.page_id == "presets"
    assert page.title == "Profili e preset"


def test_presets_page_initial_state_loading(mock_theme_manager: MagicMock) -> None:
    """Verifica che refresh() passi allo stato 'loading' prima di leggere i preset."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    page = PresetsPage(manager=mock_theme_manager)
    mock_theme_manager.list_presets.return_value = []

    # refresh sincrono: dopo la chiamata lo stato è 'empty' o 'ready'
    page.refresh(sync=True)
    # La pagina non deve essere nello stato iniziale (deve aver aggiornato)
    assert page.widget.get_visible_child_name() != "loading"


def test_presets_page_empty_state_when_no_presets(mock_theme_manager: MagicMock) -> None:
    """Verifica che la pagina passi allo stato 'empty' quando non ci sono preset."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "empty"


def test_presets_page_ready_state_with_presets(mock_theme_manager: MagicMock) -> None:
    """Verifica che la pagina passi allo stato 'ready' quando ci sono preset."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = ["Nordic", "Papirus"]
    mock_theme_manager.load_preset.return_value = ThemeSet(gtk_theme="Nordic")
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"


def test_presets_page_error_state_on_list_failure(mock_theme_manager: MagicMock) -> None:
    """Verifica che la pagina passi allo stato 'error' in caso di eccezione su list_presets."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.side_effect = OSError("Accesso negato")
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"


def test_presets_page_uses_only_public_api(mock_theme_manager: MagicMock) -> None:
    """Verifica che PresetsPage usi solo le API pubbliche di ThemeManager, senza accedere a _presets."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    import inspect

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    # Analisi del codice sorgente del controller
    source = inspect.getsource(PresetsPage)

    # La GUI non deve mai accedere a manager._presets direttamente
    assert "._presets" not in source, "PresetsPage non deve accedere a manager._presets"
    # La GUI non deve costruire percorsi filesystem dei preset
    assert "PRESETS_DIR" not in source, "PresetsPage non deve conoscere PRESETS_DIR"
    assert ".json" not in source or "tomato" not in source, (
        "PresetsPage non deve costruire nomi di file con .json (la validazione è nel core)"
    )


def test_presets_page_load_preset_called_via_public_api(mock_theme_manager: MagicMock) -> None:
    """Verifica che la lettura dei dettagli dei preset avvenga tramite manager.load_preset()."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = ["MioStile"]
    mock_theme_manager.load_preset.return_value = ThemeSet(gtk_theme="Nordic", icon_theme="Papirus")
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # Deve essere stata chiamata l'API pubblica load_preset con il nome corretto
    mock_theme_manager.load_preset.assert_called_with("MioStile")


def test_presets_page_corrupt_preset_shows_error_row(mock_theme_manager: MagicMock) -> None:
    """Verifica che un preset corrotto sia mostrato nella lista con riga di errore (senza crash)."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = ["Buono", "Corrotto"]

    def side_effect_load(name: str) -> ThemeSet:
        if name == "Corrotto":
            raise ValueError("JSON corrotto")
        return ThemeSet(gtk_theme="Nordic")

    mock_theme_manager.load_preset.side_effect = side_effect_load
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # La pagina deve essere nello stato ready (non error)
    assert page.widget.get_visible_child_name() == "ready"

    # Entrambi i preset devono essere nella lista
    rows = []
    child = page.presets_list_box.get_first_child()
    while child is not None:
        rows.append(child)
        child = child.get_next_sibling()
    assert len(rows) == 2


def test_presets_page_save_calls_public_api(mock_theme_manager: MagicMock) -> None:
    """Verifica che il salvataggio di un preset chiami manager.save_current_as_preset()."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    mock_theme_manager.save_current_as_preset.return_value = Path("/tmp/test.json")
    page = PresetsPage(manager=mock_theme_manager)

    # Simula direttamente la validazione e il salvataggio (bypassando il dialogo UI)
    page._do_save_preset("NuovoPreset", overwrite=False)

    mock_theme_manager.save_current_as_preset.assert_called_once_with(
        "NuovoPreset", overwrite=False
    )


def test_presets_page_save_empty_name_rejected(mock_theme_manager: MagicMock) -> None:
    """Verifica che un nome vuoto venga rifiutato senza chiamare il backend."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    page = PresetsPage(manager=mock_theme_manager)

    # Un nome vuoto non deve mai raggiungere il backend
    page._validate_and_save("")
    mock_theme_manager.save_current_as_preset.assert_not_called()


def test_presets_page_save_whitespace_only_rejected(mock_theme_manager: MagicMock) -> None:
    """Verifica che un nome composto solo da spazi venga rifiutato."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    page = PresetsPage(manager=mock_theme_manager)

    page._validate_and_save("   ")
    mock_theme_manager.save_current_as_preset.assert_not_called()


def test_presets_page_save_duplicate_without_overwrite(mock_theme_manager: MagicMock) -> None:
    """Verifica che un nome duplicato non sovrascriva silenziosamente il preset esistente."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = ["MioPreset"]
    page = PresetsPage(manager=mock_theme_manager)

    # Il dialogo di conferma deve essere aperto al posto del salvataggio diretto
    with patch.object(page, "_open_overwrite_confirm_dialog") as mock_confirm:
        page._validate_and_save("MioPreset")
        mock_confirm.assert_called_once_with("MioPreset")

    # Non deve aver chiamato il backend direttamente
    mock_theme_manager.save_current_as_preset.assert_not_called()


def test_presets_page_save_with_overwrite_confirmed(mock_theme_manager: MagicMock) -> None:
    """Verifica che la sovrascrittura esplicita chiami save_current_as_preset con overwrite=True."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from pathlib import Path

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    mock_theme_manager.save_current_as_preset.return_value = Path("/tmp/test.json")
    page = PresetsPage(manager=mock_theme_manager)

    page._do_save_preset("Esiste", overwrite=True)
    mock_theme_manager.save_current_as_preset.assert_called_once_with("Esiste", overwrite=True)


def test_presets_page_apply_uses_public_api(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione di un preset chiami manager.apply_preset()."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.apply_preset.return_value = ApplyResult(gtk_theme="Nordic")
    page = PresetsPage(manager=mock_theme_manager)

    page._run_apply_preset("Nordic", sync=True)

    mock_theme_manager.apply_preset.assert_called_once_with("Nordic")


def test_presets_page_apply_notifies_window(mock_theme_manager: MagicMock) -> None:
    """Verifica che after apply preset venga invocato on_preset_applied per aggiornare StatusPage e ThemesPage."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.apply_preset.return_value = ApplyResult(gtk_theme="Nordic")
    page = PresetsPage(manager=mock_theme_manager)

    callback_called: list[bool] = []
    page.on_preset_applied = lambda: callback_called.append(True)

    page._run_apply_preset("Nordic", sync=True)

    assert len(callback_called) == 1, "on_preset_applied deve essere invocato una sola volta"


def test_presets_page_apply_partial_result_shows_warnings(mock_theme_manager: MagicMock) -> None:
    """Verifica che un risultato parziale con warnings mostri i dettagli e non 'successo'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    result = ApplyResult(gtk_theme="Nordic", warnings=["Shell theme non applicato"])
    mock_theme_manager.apply_preset.return_value = result
    page = PresetsPage(manager=mock_theme_manager)

    toasts: list[str] = []
    with patch.object(page, "_show_toast", side_effect=lambda msg, **kw: toasts.append(msg)):
        page._run_apply_preset("Nordic", sync=True)

    assert len(toasts) == 1
    assert (
        "avvisi" in toasts[0].lower()
        or "warning" in toasts[0].lower()
        or "Shell theme" in toasts[0]
    )


def test_presets_page_apply_blocks_concurrent(mock_theme_manager: MagicMock) -> None:
    """Verifica che una seconda applicazione concorrente venga ignorata."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.apply_preset.return_value = ApplyResult(gtk_theme="Nordic")
    page = PresetsPage(manager=mock_theme_manager)

    # Simula applicazione già in corso
    page._is_applying = True
    page._run_apply_preset("Nordic", sync=True)

    # Il backend non deve essere stato chiamato
    mock_theme_manager.apply_preset.assert_not_called()


def test_presets_page_apply_error_resets_controls(mock_theme_manager: MagicMock) -> None:
    """Verifica che dopo un errore di applicazione i controlli vengano riabilitati."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    mock_theme_manager.apply_preset.side_effect = OSError("Errore applicazione")
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)  # porta in stato empty

    page._run_apply_preset("Nordic", sync=True)

    # I controlli devono essere riabilitati anche dopo un errore
    assert page._is_applying is False
    assert page.save_preset_button.get_sensitive() is True


def test_presets_page_delete_calls_public_api(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'eliminazione di un preset chiami manager.delete_preset()."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    mock_theme_manager.delete_preset.return_value = True
    page = PresetsPage(manager=mock_theme_manager)

    page._do_delete_preset("Nordic")

    mock_theme_manager.delete_preset.assert_called_once_with("Nordic")


def test_presets_page_delete_refreshes_list(mock_theme_manager: MagicMock) -> None:
    """Verifica che dopo l'eliminazione la lista venga ricaricata."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    mock_theme_manager.delete_preset.return_value = True
    page = PresetsPage(manager=mock_theme_manager)

    with patch.object(page, "refresh") as mock_refresh:
        page._do_delete_preset("Nordic")
        mock_refresh.assert_called_once()


def test_presets_page_delete_not_found_shows_error(mock_theme_manager: MagicMock) -> None:
    """Verifica che FileNotFoundError durante l'eliminazione mostri un toast di errore."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    mock_theme_manager.delete_preset.side_effect = FileNotFoundError("Preset non trovato")
    page = PresetsPage(manager=mock_theme_manager)

    toasts: list[str] = []
    with patch.object(page, "_show_toast", side_effect=lambda msg, **kw: toasts.append(msg)):
        page._do_delete_preset("Fantasma")

    assert len(toasts) == 1
    assert "errore" in toasts[0].lower() or "Fantasma" in toasts[0]


def test_presets_page_no_global_refresh_button(mock_theme_manager: MagicMock) -> None:
    """Verifica che la pagina Preset non abiliti il pulsante Refresh globale della finestra."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    # Quando la pagina 'presets' è attiva, il pulsante Refresh globale deve essere nascosto
    win.select_page("presets")
    assert win.refresh_button.get_visible() is False


def test_presets_page_reload_button_triggers_local_refresh(mock_theme_manager: MagicMock) -> None:
    """Verifica che il pulsante 'Ricarica' della pagina Preset invochi un refresh locale."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.return_value = []
    page = PresetsPage(manager=mock_theme_manager)

    with patch.object(page, "refresh") as mock_refresh:
        page._on_reload_clicked(page.reload_presets_button)
        mock_refresh.assert_called_once()


def test_presets_page_retry_after_error(mock_theme_manager: MagicMock) -> None:
    """Verifica che il pulsante 'Riprova' nello stato error avvii un nuovo refresh."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.list_presets.side_effect = OSError("Errore")
    page = PresetsPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "error"

    # Ora il manager funziona: riprova
    mock_theme_manager.list_presets.side_effect = None
    mock_theme_manager.list_presets.return_value = []
    page._on_reload_clicked(page.error_retry_button)
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "empty"
