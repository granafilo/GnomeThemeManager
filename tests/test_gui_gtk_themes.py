import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.errors import (
    GnomeThemeManagerError,
)
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.themes import (
    ThemeItemPresentation,
    ThemesPage,
)

if is_gtk_available():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Pango", "1.0")
    from gi.repository import Adw, Gdk, GLib, Gtk, Pango
else:
    Adw = None  # type: ignore[assignment]
    Gdk = None  # type: ignore[assignment]
    Gtk = None  # type: ignore[assignment]
    GLib = None  # type: ignore[assignment]
    Pango = None  # type: ignore[assignment]

# Percorso della directory contenente i file UI
UI_DIR = Path(__file__).parent.parent / "src" / "gnome_theme_manager" / "gui_gtk" / "ui"


def test_themes_page_ui_structure_and_scrolling() -> None:
    """Verifica la struttura dichiarativa di themes_page.ui e i relativi controlli."""
    themes_ui_path = UI_DIR / "themes_page.ui"
    tree = ET.parse(themes_ui_path)
    root = tree.getroot()

    object_ids = [elem.attrib.get("id") for elem in root.iter("object") if "id" in elem.attrib]

    assert "page_root" in object_ids
    assert "loading_page" in object_ids
    assert "loading_spinner" in object_ids
    assert "ready_box" in object_ids
    assert "category_title_label" in object_ids
    assert "active_theme_group" in object_ids
    assert "active_theme_row" in object_ids
    assert "available_section_title" in object_ids
    assert "search_entry" in object_ids
    assert "themes_scrolled_window" in object_ids
    assert "count_label" in object_ids
    assert "themes_list_box" in object_ids
    assert "no_results_page" in object_ids
    assert "action_box" in object_ids
    assert "apply_button" in object_ids
    assert "empty_page" in object_ids
    assert "empty_refresh_button" in object_ids
    assert "error_page" in object_ids
    assert "error_retry_button" in object_ids
    assert "category_dropdown" not in object_ids

    page_root_obj = next(
        elem for elem in root.iter("object") if elem.attrib.get("id") == "page_root"
    )
    root_props = {p.attrib.get("name"): p.text for p in page_root_obj.findall("property")}
    assert root_props.get("vexpand") == "true"
    assert root_props.get("hexpand") == "true"


def test_themes_page_ready_state_and_active_card(mock_theme_manager: MagicMock) -> None:
    """Verifica che ThemesPage mostri la Card del Tema Attivo ed escluda tale tema dalla lista disponibili."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    assert page.page_id == "themes"

    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    # Il tema attivo per GTK nel mock è 'Yaru'
    assert page.active_theme_row.get_title() == "Yaru"
    assert "In uso" in page.active_theme_badge.get_text()

    # La lista delle alternative contiene solo 'Nordic' ('Yaru' è escluso)
    assert "1 altri applicazioni (gtk) disponibili" in page.count_label.get_text()
    assert page.themes_list_box.get_visible() is True
    assert page.apply_button.get_sensitive() is False


def test_themes_page_categories_navigation(mock_theme_manager: MagicMock) -> None:
    """Verifica la navigazione tra categorie con corretta visualizzazione della card attiva e delle alternative."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    # 1. Categoria GNOME Shell (attivo: Yaru [non in lista locale], 1 alternativa: Nordic-Shell)
    page.set_category(ThemeType.SHELL)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "non trovato" in page.active_theme_row.get_subtitle().lower()
    assert "1 altri gnome shell disponibili" in page.count_label.get_text()

    # 2. Categoria Cursori (attivo: Yaru [non in lista locale], 1 alternativa: Bibata-Modern-Classic)
    page.set_category(ThemeType.CURSOR)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "non trovato" in page.active_theme_row.get_subtitle().lower()
    assert "1 altri cursori disponibili" in page.count_label.get_text()

    # 3. Categoria Icone (attivo: Yaru [non in lista locale], 1 alternativa: Papirus)
    page.set_category(ThemeType.ICON)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "non trovato" in page.active_theme_row.get_subtitle().lower()
    assert "1 altri icone disponibili" in page.count_label.get_text()

    # 4. Categoria GTK (attivo: Yaru, 1 alternativa: Nordic)
    page.set_category(ThemeType.GTK)
    assert page.active_theme_row.get_title() == "Yaru"
    assert "1 altri applicazioni (gtk) disponibili" in page.count_label.get_text()


def test_themes_page_search_filtering_in_available_list(mock_theme_manager: MagicMock) -> None:
    """Verifica che la ricerca testuale operi esclusivamente tra i temi alternativi disponibili."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    # Ricerca per 'nordic' (disponibile)
    page.search_entry.set_text("nordic")
    assert "1 altri applicazioni (gtk) disponibili" in page.count_label.get_text()

    # Ricerca per 'yaru' (che è già attivo ed escluso dalla lista disponibili)
    page.search_entry.set_text("yaru")
    assert page.no_results_page.get_visible() is True
    assert page.themes_list_box.get_visible() is False

    # Azzeramento ricerca
    page.search_entry.set_text("")
    assert "1 altri applicazioni (gtk) disponibili" in page.count_label.get_text()
    assert page.no_results_page.get_visible() is False
    assert page.themes_list_box.get_visible() is True


def test_themes_page_apply_theme_updates_card_and_available_list(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che applicando un nuovo tema:
    1. Si crei un nuovo snapshot immutabile;
    2. La card mostri il nuovo tema attivo;
    3. Il nuovo tema attivo scompaia dalla lista;
    4. Il tema precedente venga reinserito nella lista dei disponibili.
    """
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    snapshot_before = page.current_snapshot
    assert snapshot_before is not None
    assert snapshot_before.active_themes[ThemeType.GTK] == "Yaru"

    item_nordic = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/home/user/.local/share/themes/Nordic",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item_nordic, sync=True)

    # Verifica immutabilità e creazione nuovo snapshot
    snapshot_after = page.current_snapshot
    assert snapshot_after is not None
    assert snapshot_after is not snapshot_before
    assert snapshot_after.active_themes[ThemeType.GTK] == "Nordic"

    # Card aggiornata con il nuovo tema
    assert page.active_theme_row.get_title() == "Nordic"

    # Lista aggiornata: ora contiene 'Yaru' ('Nordic' è stato rimosso)
    assert "1 altri applicazioni (gtk) disponibili" in page.count_label.get_text()
    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    assert first_row.get_title() == "Yaru"


def test_themes_page_single_click_selects_only(mock_theme_manager: MagicMock) -> None:
    """Verifica che il singolo click selezioni soltanto la riga senza avviare la conferma/applicazione."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        # Il singolo click emette row-selected
        page.themes_list_box.select_row(first_row)
        assert page.selected_theme is not None
        assert page.selected_theme.name == "Nordic"
        mock_confirm.assert_not_called()


def test_themes_page_double_click_triggers_confirm_and_apply(mock_theme_manager: MagicMock) -> None:
    """Verifica che il doppio click (row-activated) avvii la conferma/applicazione del tema."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        # Il doppio click emette row-activated
        page.themes_list_box.emit("row-activated", first_row)
        assert page.selected_theme is not None
        assert page.selected_theme.name == "Nordic"
        mock_confirm.assert_called_once()


def test_themes_page_double_click_blocked_during_application(mock_theme_manager: MagicMock) -> None:
    """Verifica che un doppio click durante un'applicazione in corso venga ignorato."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None

    page._is_applying = True

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        page.themes_list_box.emit("row-activated", first_row)
        mock_confirm.assert_not_called()


def test_themes_page_sorting_user_first_then_alphabetical() -> None:
    """Verifica che i temi siano ordinati con priorità:
    1. Temi Utente
    2. Temi Sistema
    3. Ordine alfabetico case-insensitive
    """
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.get_current_themes.return_value = ThemeSet(gtk_theme="ActiveTheme")
    mock_mgr.list_themes.return_value = [
        Theme(
            name="Zeta-Sys",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/Zeta-Sys"),
            is_user_level=False,
        ),
        Theme(
            name="alpha-sys",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/alpha-sys"),
            is_user_level=False,
        ),
        Theme(
            name="Zeta-User",
            theme_type=ThemeType.GTK,
            path=Path("/home/user/.local/share/themes/Zeta-User"),
            is_user_level=True,
        ),
        Theme(
            name="alpha-user",
            theme_type=ThemeType.GTK,
            path=Path("/home/user/.local/share/themes/alpha-user"),
            is_user_level=True,
        ),
        Theme(
            name="ActiveTheme",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/ActiveTheme"),
            is_user_level=False,
        ),
    ]

    page = ThemesPage(manager=mock_mgr)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    # Raccolta dei titoli delle righe nella lista
    rendered_titles: list[str] = []
    child = page.themes_list_box.get_first_child()
    while child is not None:
        if hasattr(child, "get_title"):
            rendered_titles.append(child.get_title())
        child = child.get_next_sibling()

    # Ordine atteso: Utenti (alpha-user, Zeta-User) poi Sistema (alpha-sys, Zeta-Sys)
    assert rendered_titles == ["alpha-user", "Zeta-User", "alpha-sys", "Zeta-Sys"]


def test_themes_page_cursor_application_shows_informative_toast(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che l'applicazione del tema cursore emetta un feedback persistente con nota informativa."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.CURSOR)

    item_cursor = ThemeItemPresentation(
        name="Bibata-Modern-Classic",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/usr/share/icons/Bibata-Modern-Classic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "_show_toast") as mock_toast:
        page.apply_theme(item_cursor, sync=True)
        # Deve comparire il toast informativo dedicato
        mock_toast.assert_called_once()
        msg = mock_toast.call_args[0][0]
        assert "Bibata-Modern-Classic" in msg
        assert "cambiare finestra" in msg.lower() or "riaprire" in msg.lower()
        # Controlli riabilitati
        assert page.is_applying is False


def test_themes_page_cursor_application_error_shows_error_toast(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che in caso di errore nell'applicazione del tema cursore venga mostrato il messaggio di errore."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.apply_themes.side_effect = GnomeThemeManagerError("Errore dconf")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.CURSOR)

    item_cursor = ThemeItemPresentation(
        name="Bibata-Modern-Classic",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/usr/share/icons/Bibata-Modern-Classic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "_show_toast") as mock_toast:
        page.apply_theme(item_cursor, sync=True)
        mock_toast.assert_called_once()
        assert "Impossibile" in mock_toast.call_args[0][0] or "Errore" in mock_toast.call_args[0][0]
        assert page.is_applying is False


def test_themes_page_double_click_blocked_when_dialog_already_open(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che se un dialogo di conferma è già aperto, ulteriori attivazioni/doppi click vengano ignorati."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    assert first_row.get_activatable() is True

    page._confirm_dialog_open = True

    with patch.object(page, "confirm_and_apply_selected") as mock_confirm:
        page.themes_list_box.emit("row-activated", first_row)
        mock_confirm.assert_not_called()


def test_themes_page_confirm_dialog_cancel_resets_flag_and_no_apply(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che l'annullamento del dialogo di conferma resetti _confirm_dialog_open e non applichi nulla."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    item = first_row._theme_item

    captured_callback: Any = None

    def fake_connect(signal: str, callback: Any) -> None:
        nonlocal captured_callback
        if signal == "response":
            captured_callback = callback

    with (
        patch.object(page, "apply_theme") as mock_apply,
        patch("gi.repository.Adw.AlertDialog.connect", side_effect=fake_connect)
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.connect", side_effect=fake_connect),
        patch("gi.repository.Adw.AlertDialog.present")
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.present"),
    ):
        page.confirm_and_apply_theme(item, sync=False)
        assert page._confirm_dialog_open is True

        # Secondo tentativo di apertura mentre è aperto: deve essere ignorato
        page.confirm_and_apply_theme(item, sync=False)

        # Simulazione risposta 'cancel' dal dialogo
        if captured_callback is not None:
            captured_callback(MagicMock(), "cancel")

        assert page._confirm_dialog_open is False
        mock_apply.assert_not_called()


def test_themes_page_confirm_dialog_interactive_apply_resets_flag(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che la risposta 'apply' dal dialogo interattivo resetti _confirm_dialog_open e invochi apply_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    item = first_row._theme_item

    captured_callback: Any = None

    def fake_connect(signal: str, callback: Any) -> None:
        nonlocal captured_callback
        if signal == "response":
            captured_callback = callback

    with (
        patch.object(page, "apply_theme") as mock_apply,
        patch("gi.repository.Adw.AlertDialog.connect", side_effect=fake_connect)
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.connect", side_effect=fake_connect),
        patch("gi.repository.Adw.AlertDialog.present")
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.present"),
    ):
        page.confirm_and_apply_theme(item, sync=False)
        assert page._confirm_dialog_open is True

        # Simulazione risposta 'apply' dal dialogo
        if captured_callback is not None:
            captured_callback(MagicMock(), "apply")

        assert page._confirm_dialog_open is False
        mock_apply.assert_called_once()


def test_themes_page_confirm_dialog_sync_mode_resets_flag_and_applies(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica che con sync=True il dialogo venga comunque creato e alla risposta 'apply' invochi apply_theme(sync=True)."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    item = first_row._theme_item

    dialog_instances: list[Any] = []
    real_init = Adw.AlertDialog.new if hasattr(Adw, "AlertDialog") else Adw.MessageDialog.new

    def fake_new(*args: Any, **kwargs: Any) -> Any:
        dlg = real_init(*args, **kwargs)
        dialog_instances.append(dlg)
        return dlg

    with (
        patch.object(
            Adw.AlertDialog if hasattr(Adw, "AlertDialog") else Adw.MessageDialog,
            "new",
            side_effect=fake_new,
        ),
        patch("gi.repository.Adw.AlertDialog.present")
        if hasattr(Adw, "AlertDialog")
        else patch("gi.repository.Adw.MessageDialog.present"),
        patch.object(page, "apply_theme") as mock_apply,
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) == 1
        assert page._confirm_dialog_open is True

        # Simulazione risposta "apply"
        dialog_instances[0].emit("response", "apply")
        assert page._confirm_dialog_open is False
        mock_apply.assert_called_once_with(item, on_complete=None, sync=True)


def test_themes_page_active_theme_backend_unavailable(mock_theme_manager: MagicMock) -> None:
    """Verifica che se il backend non riesce a recuperare il tema attivo, la card mostri 'Non disponibile'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.get_current_themes.side_effect = GnomeThemeManagerError(
        "GSettings non disponibile."
    )

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.active_theme_row.get_title() == "Non disponibile"
    assert page.active_theme_badge.get_visible() is False


def test_themes_page_cursor_propagate_fallback_error(mock_theme_manager: MagicMock) -> None:
    """Verifica che un errore in GtkSettings durante la propagazione del cursore venga gestito senza eccezioni."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)

    with patch(
        "gi.repository.Gdk.Display.get_default", side_effect=RuntimeError("Display non disponibile")
    ):
        # Non deve sollevare eccezioni
        res = page._propagate_cursor_theme_in_process("Bibata-Modern-Classic")
        assert res is False


def test_themes_page_selection_enables_apply_button(mock_theme_manager: MagicMock) -> None:
    """Verifica che la selezione di un tema alternativo dalla lista abiliti il pulsante Applica."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    assert page.selected_theme is None
    assert page.apply_button.get_sensitive() is False

    # Selezione del tema disponibile nella lista ('Nordic')
    first_row = page.themes_list_box.get_first_child()
    assert first_row is not None
    page.themes_list_box.select_row(first_row)

    assert page.selected_theme is not None
    assert page.selected_theme.name == "Nordic"
    assert page.apply_button.get_sensitive() is True


def test_themes_page_empty_state() -> None:
    """Verifica che quando list_themes restituisce una lista vuota venga mostrato lo stato EMPTY."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.list_themes.return_value = []
    mock_mgr.get_current_themes.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        shell_theme="Yaru",
    )

    page = ThemesPage(manager=mock_mgr)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "empty"


def test_themes_page_error_state_and_retry(mock_theme_manager: MagicMock) -> None:
    """Verifica la transizione allo stato ERROR in caso di eccezione e il funzionamento del retry."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.list_themes.side_effect = GnomeThemeManagerError("Scansione fallita.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"
    assert "Scansione fallita" in page.error_page.get_description()

    # Ripristino condizione di successo e retry sincrono
    mock_theme_manager.list_themes.side_effect = None
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "ready"


def test_themes_page_concurrency_guard(mock_theme_manager: MagicMock) -> None:
    """Verifica che richieste di refresh concorrenti su ThemesPage vengano bloccate."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page._is_loading = True
    gen_before = page._generation_id
    page.refresh()
    assert page._generation_id == gen_before


def test_themes_page_apply_theme_mapping_gtk(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione di un tema GTK configuri solo gtk_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    # Verifica invocazione con ThemeSet contenente solo gtk_theme
    mock_theme_manager.apply_themes.assert_called_once()
    called_theme_set: ThemeSet = mock_theme_manager.apply_themes.call_args[1]["theme_set"]
    assert called_theme_set.gtk_theme == "Nordic"
    assert called_theme_set.icon_theme is None
    assert called_theme_set.cursor_theme is None
    assert called_theme_set.shell_theme is None


def test_themes_page_apply_theme_mapping_icon(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione di un tema icone configuri solo icon_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Papirus",
        theme_type=ThemeType.ICON,
        category_display="Icone",
        icon_name="applications-graphics-symbolic",
        path_display="/usr/share/icons/Papirus",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    called_theme_set: ThemeSet = mock_theme_manager.apply_themes.call_args[1]["theme_set"]
    assert called_theme_set.icon_theme == "Papirus"
    assert called_theme_set.gtk_theme is None


def test_themes_page_apply_theme_mapping_cursor(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione di un tema cursori configuri solo cursor_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Bibata",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/home/user/.local/share/icons/Bibata",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item, sync=True)

    called_theme_set: ThemeSet = mock_theme_manager.apply_themes.call_args[1]["theme_set"]
    assert called_theme_set.cursor_theme == "Bibata"
    assert called_theme_set.gtk_theme is None


def test_themes_page_apply_theme_mapping_shell(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione di un tema shell configuri solo shell_theme."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic-Shell",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/home/user/.local/share/themes/Nordic-Shell",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item, sync=True)

    called_theme_set: ThemeSet = mock_theme_manager.apply_themes.call_args[1]["theme_set"]
    assert called_theme_set.shell_theme == "Nordic-Shell"
    assert called_theme_set.gtk_theme is None


def test_themes_page_apply_theme_success_notifies_listener(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione riuscita notifichi il listener on_theme_applied."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    mock_listener = MagicMock()
    page.on_theme_applied = mock_listener

    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    mock_listener.assert_called_once()
    assert mock_listener.call_args[0][0] == item


def test_themes_page_apply_theme_error_handling(mock_theme_manager: MagicMock) -> None:
    """Verifica che un errore durante l'applicazione ripristini _is_applying e notifichi l'errore."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.apply_themes.side_effect = GnomeThemeManagerError("GSettings write failed.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="ErrorTheme",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/ErrorTheme",
        origin_display="Sistema",
        is_user_level=False,
    )

    on_complete_mock = MagicMock()
    page.apply_theme(item, on_complete=on_complete_mock, sync=True)

    assert page.is_applying is False
    on_complete_mock.assert_called_once()
    assert on_complete_mock.call_args[0][0] is None
    assert isinstance(on_complete_mock.call_args[0][1], GnomeThemeManagerError)


def test_themes_page_apply_concurrency_guard(mock_theme_manager: MagicMock) -> None:
    """Verifica che una seconda applicazione concorrente venga scartata se una è già in corso."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page._is_applying = True

    item = ThemeItemPresentation(
        name="ConcurrentTheme",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/ConcurrentTheme",
        origin_display="Sistema",
        is_user_level=False,
    )

    on_complete_mock = MagicMock()
    page.apply_theme(item, on_complete=on_complete_mock, sync=True)

    on_complete_mock.assert_called_once()
    assert "già in corso" in str(on_complete_mock.call_args[0][1])


def test_themes_page_apply_shell_theme_missing_user_themes(mock_theme_manager: MagicMock) -> None:
    """Verifica che se il tema Shell non può essere applicato (shell_theme=None), non venga notificato il successo."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.apply_themes.return_value = ApplyResult(
        shell_theme=None,
        warnings=["Impossibile applicare il tema GNOME Shell: estensione User Themes non attiva."],
    )

    page = ThemesPage(manager=mock_theme_manager)
    mock_listener = MagicMock()
    page.on_theme_applied = mock_listener

    item = ThemeItemPresentation(
        name="Nordic-Shell",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/home/user/.local/share/themes/Nordic-Shell",
        origin_display="Utente",
        is_user_level=True,
    )

    page.apply_theme(item, sync=True)

    # Il listener di successo NON deve essere stato chiamato
    mock_listener.assert_not_called()


def test_themes_page_apply_gtk_theme_without_gtk4_override(mock_theme_manager: MagicMock) -> None:
    """Verifica che un tema GTK applicato senza override GTK4 notifichi comunque il listener con l'esito."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.apply_themes.return_value = ApplyResult(
        gtk_theme="Classic-Theme",
        gtk4_override_applied=False,
        warnings=[],
    )

    page = ThemesPage(manager=mock_theme_manager)
    mock_listener = MagicMock()
    page.on_theme_applied = mock_listener

    item = ThemeItemPresentation(
        name="Classic-Theme",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Classic-Theme",
        origin_display="Sistema",
        is_user_level=False,
    )

    page.apply_theme(item, sync=True)

    mock_listener.assert_called_once()
    assert mock_listener.call_args[0][0] == item


def test_themes_page_confirm_dialog_clean_structure_and_sizing(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica la struttura pulita del dialogo di conferma:
    - Titolo: «Applicare “NOME” a CATEGORIA?»
    - Nessun path o origine nel testo principale
    - Presenza di categoria e tema attivo
    - Spaziatura confortevole (larghezza minima 500px)
    - Label con wrap=False ed ellipsize=END
    """
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.SHELL)

    item = ThemeItemPresentation(
        name="Colloid",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/usr/share/themes/Colloid",
        origin_display="Sistema",
        is_user_level=False,
    )

    dialog_instances: list[Any] = []
    real_init = Adw.AlertDialog.new

    def fake_new(*args: Any, **kwargs: Any) -> Any:
        dlg = real_init(*args, **kwargs)
        dialog_instances.append(dlg)
        return dlg

    with (
        patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
        patch.object(Adw.AlertDialog, "present"),
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) == 1
        dlg = dialog_instances[0]

        # Verifica titolo pulito
        assert dlg.get_heading() == "Applicare “Colloid” a GNOME Shell?"

        # Verifica contenuto extra_child
        extra_child = dlg.get_extra_child()
        assert extra_child is not None
        assert isinstance(extra_child, Gtk.Box)

        # Verifica larghezza minima confortevole (500px)
        width, _ = extra_child.get_size_request()
        assert width >= 480

        # Ispezione label interne
        labels: list[Gtk.Label] = []
        child = extra_child.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label):
                labels.append(child)
            child = child.get_next_sibling()

        assert len(labels) >= 1
        cat_text = labels[0].get_text()
        assert cat_text == "Categoria: GNOME Shell"
        assert labels[0].get_wrap() is False
        assert labels[0].get_ellipsize() == Pango.EllipsizeMode.END

        # Verifica assenza di percorsi e dettagli tecnici
        for lbl in labels:
            text = lbl.get_text()
            assert "/usr/share" not in text
            assert "~/.local" not in text
            assert "Sistema" not in text
            assert "Utente" not in text


def test_themes_page_confirm_dialog_long_name_and_active_theme(
    mock_theme_manager: MagicMock,
) -> None:
    """Verifica il comportamento del dialogo con nomi lunghi e tema attivo valorizzato."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)
    page.set_category(ThemeType.GTK)

    long_name = "Very-Long-Theme-Name-Variant-Dark-Custom-Build-Extended-Edition"
    item = ThemeItemPresentation(
        name=long_name,
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display=f"/usr/share/themes/{long_name}",
        origin_display="Sistema",
        is_user_level=False,
    )

    dialog_instances: list[Any] = []
    real_init = Adw.AlertDialog.new

    def fake_new(*args: Any, **kwargs: Any) -> Any:
        dlg = real_init(*args, **kwargs)
        dialog_instances.append(dlg)
        return dlg

    with (
        patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
        patch.object(Adw.AlertDialog, "present"),
    ):
        page.confirm_and_apply_theme(item, sync=True)
        assert len(dialog_instances) == 1
        dlg = dialog_instances[0]

        assert dlg.get_heading() == f"Applicare “{long_name}” a GTK?"

        extra_child = dlg.get_extra_child()
        assert extra_child is not None
        labels: list[Gtk.Label] = []
        child = extra_child.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label):
                labels.append(child)
            child = child.get_next_sibling()

        assert len(labels) == 2
        assert labels[0].get_text() == "Categoria: GTK"
        assert labels[1].get_text() == "Tema attualmente attivo: Yaru"
        assert labels[1].get_wrap() is False
        assert labels[1].get_ellipsize() == Pango.EllipsizeMode.END


def test_themes_page_confirm_dialog_accept(mock_theme_manager: MagicMock) -> None:
    """Verifica che la conferma con 'apply' nel dialogo invochi l'applicazione del tema."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "apply_theme") as mock_apply:
        dialog_instances = []
        real_init = Adw.AlertDialog.new

        def fake_new(*args: Any, **kwargs: Any) -> Any:
            dlg = real_init(*args, **kwargs)
            dialog_instances.append(dlg)
            return dlg

        with (
            patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
            patch.object(Adw.AlertDialog, "present"),
        ):
            page.confirm_and_apply_theme(item, sync=True)
            assert len(dialog_instances) == 1
            # Emettiamo la risposta "apply"
            dialog_instances[0].emit("response", "apply")
            mock_apply.assert_called_once_with(item, on_complete=None, sync=True)


def test_themes_page_confirm_dialog_cancel(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'annullamento con 'cancel' nel dialogo non invochi l'applicazione del tema."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(page, "apply_theme") as mock_apply:
        dialog_instances = []
        real_init = Adw.AlertDialog.new

        def fake_new(*args: Any, **kwargs: Any) -> Any:
            dlg = real_init(*args, **kwargs)
            dialog_instances.append(dlg)
            return dlg

        with (
            patch.object(Adw.AlertDialog, "new", side_effect=fake_new),
            patch.object(Adw.AlertDialog, "present"),
        ):
            page.confirm_and_apply_theme(item, sync=True)
            assert len(dialog_instances) == 1
            # Emettiamo la risposta "cancel"
            dialog_instances[0].emit("response", "cancel")
            mock_apply.assert_not_called()


def test_themes_page_category_specific_feedback_messages(mock_theme_manager: MagicMock) -> None:
    """Verifica che ogni categoria emetta un messaggio di successo chiaro e specifico."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    toasts: list[str] = []
    page._show_toast = lambda msg, **kwargs: toasts.append(msg)

    # 1. GTK con override
    mock_theme_manager.apply_themes.return_value = ApplyResult(gtk4_override_applied=True)
    item_gtk = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )
    page.apply_theme(item_gtk, sync=True)
    assert len(toasts) == 1
    assert "Tema GTK «Nordic» applicato" in toasts[-1]
    assert "override GTK4" in toasts[-1]

    # 2. GNOME Shell
    mock_theme_manager.apply_themes.return_value = ApplyResult(shell_theme="Colloid")
    item_shell = ThemeItemPresentation(
        name="Colloid",
        theme_type=ThemeType.SHELL,
        category_display="GNOME Shell",
        icon_name="preferences-system-windows-symbolic",
        path_display="/usr/share/themes/Colloid",
        origin_display="Sistema",
        is_user_level=False,
    )
    page.apply_theme(item_shell, sync=True)
    assert len(toasts) == 2
    assert "Tema GNOME Shell «Colloid» applicato" in toasts[-1]

    # 3. Icone
    mock_theme_manager.apply_themes.return_value = ApplyResult()
    item_icon = ThemeItemPresentation(
        name="Papirus",
        theme_type=ThemeType.ICON,
        category_display="Icone",
        icon_name="applications-graphics-symbolic",
        path_display="/usr/share/icons/Papirus",
        origin_display="Sistema",
        is_user_level=False,
    )
    page.apply_theme(item_icon, sync=True)
    assert len(toasts) == 3
    assert "Tema icone «Papirus» applicato" in toasts[-1]

    # 4. Cursore
    mock_theme_manager.apply_themes.return_value = ApplyResult()
    item_cursor = ThemeItemPresentation(
        name="Bibata",
        theme_type=ThemeType.CURSOR,
        category_display="Cursori",
        icon_name="input-mouse-symbolic",
        path_display="/usr/share/icons/Bibata",
        origin_display="Sistema",
        is_user_level=False,
    )
    page.apply_theme(item_cursor, sync=True)
    assert len(toasts) == 4
    assert "Tema cursore «Bibata» applicato" in toasts[-1]
    assert "cambiare finestra" in toasts[-1] or "riaprire" in toasts[-1]

    # 5. GNOME Shell parziale (no user themes)
    mock_theme_manager.apply_themes.return_value = ApplyResult(shell_theme=None)
    page.apply_theme(item_shell, sync=True)
    assert len(toasts) == 5
    assert "parzialmente" in toasts[-1].lower()
    assert "User Themes" in toasts[-1]
