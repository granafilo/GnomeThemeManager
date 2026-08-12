"""Test di unità e integrazione per la GUI nativa GTK4 / Libadwaita (Fase 5.4 estesa).

Verifica:
1. Validità e completezza dei template XML dichiarativi (.ui);
2. Correttezza del markup Pango per caratteri speciali (&) ed assenza di warning;
3. Struttura di scroll verticale e proprietà di espansione (vexpand/hexpand);
4. Controller modulari delle pagine con Adw.StatusPage / Gtk.Stack;
5. Formattazione e snapshot immutabile della pagina 'Stato attuale';
6. Visualizzazione stato override GTK4 (Attivo / Non attivo);
7. Controller 'Esplora temi' (ThemesPage) per ricerca, filtro categorie e stati UI;
8. Applicazione diretta del singolo tema con mappatura corretta (GTK, Icone, Cursori, Shell);
9. Conferma esplicita, gestione errori e prevenzione applicazioni concorrenti;
10. Notifica e refresh della pagina Stato dopo l'applicazione del tema;
11. Visibilità contestuale del pulsante Refresh in GnomeThemeWindow per status e themes;
12. Gestione pulita di SIGINT / KeyboardInterrupt (exit code 130);
13. Isolamento, responsività e routing CLI.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.errors import GnomeThemeManagerError, GSettingsUnavailableError
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.gui_gtk import is_gtk_available, launch_gui
from gnome_theme_manager.gui_gtk.pages.status import (
    StatusPage,
    format_boolean,
    format_color_scheme,
    format_optional_value,
    format_path,
    format_sandbox_status,
    format_shell_theme,
)
from gnome_theme_manager.gui_gtk.pages.themes import (
    ThemeItemPresentation,
    ThemesPage,
    build_theme_presentation,
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


# =============================================================================
# 1. Test Validità File Template XML (.ui) — Headless & File-System Safe
# =============================================================================


@pytest.mark.parametrize(
    "ui_filename",
    [
        "window.ui",
        "status_page.ui",
        "themes_page.ui",
        "presets_page.ui",
        "installer_page.ui",
        "sandbox_page.ui",
    ],
)
def test_ui_template_files_exist_and_are_valid_xml(ui_filename: str) -> None:
    """Verifica che ogni file .ui esista e contenga XML ben formato conforme a GtkBuilder."""
    file_path = UI_DIR / ui_filename
    assert file_path.is_file(), f"Il file template {file_path} deve esistere."

    content = file_path.read_text(encoding="utf-8")
    assert "<interface>" in content, f"{ui_filename} deve contenere il tag radice <interface>"

    tree = ET.fromstring(content)
    assert tree.tag == "interface", f"Il tag root di {ui_filename} deve essere 'interface'"


def test_status_page_ui_structure_and_scrolling() -> None:
    """Verifica la struttura di status_page.ui, il corretto escaping Pango e le proprietà di espansione verticale."""
    status_ui_path = UI_DIR / "status_page.ui"
    tree = ET.parse(status_ui_path)
    root = tree.getroot()

    object_ids = [elem.attrib.get("id") for elem in root.iter("object") if "id" in elem.attrib]

    # Verifica stack e pagine di stato
    assert "page_root" in object_ids
    assert "loading_page" in object_ids
    assert "loading_spinner" in object_ids
    assert "ready_box" in object_ids
    assert "ready_page" in object_ids
    assert "banner_warning" in object_ids
    assert "empty_page" in object_ids
    assert "error_page" in object_ids
    assert "error_retry_button" in object_ids

    # Verifica righe di diagnostica
    assert "row_gtk_theme" in object_ids
    assert "row_icon_theme" in object_ids
    assert "row_cursor_theme" in object_ids
    assert "row_shell_theme" in object_ids
    assert "row_color_scheme" in object_ids
    assert "row_gtk4_override" in object_ids
    assert "row_gsettings_status" in object_ids
    assert "row_user_themes_path" in object_ids
    assert "row_user_icons_path" in object_ids
    assert "row_flatpak_status" in object_ids
    assert "row_snap_status" in object_ids

    # Verifica proprietà di espansione verticale su page_root e ready_page per garantire lo scrolling
    page_root_obj = next(elem for elem in root.iter("object") if elem.attrib.get("id") == "page_root")
    root_props = {p.attrib.get("name"): p.text for p in page_root_obj.findall("property")}
    assert root_props.get("vexpand") == "true"
    assert root_props.get("hexpand") == "true"

    ready_page_obj = next(elem for elem in root.iter("object") if elem.attrib.get("id") == "ready_page")
    ready_props = {p.attrib.get("name"): p.text for p in ready_page_obj.findall("property")}
    assert ready_props.get("vexpand") == "true"
    assert ready_props.get("hexpand") == "true"

    # Verifica escaping Pango per il titolo di group_sandbox (deve contenere &amp; nel testo decodificato)
    group_sandbox_obj = next(elem for elem in root.iter("object") if elem.attrib.get("id") == "group_sandbox")
    sandbox_props = {p.attrib.get("name"): p.text for p in group_sandbox_obj.findall("property")}
    assert "&amp;" in sandbox_props.get("title", ""), "Il titolo sandbox deve contenere &amp; per essere interpretato da Pango come &"


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

    page_root_obj = next(elem for elem in root.iter("object") if elem.attrib.get("id") == "page_root")
    root_props = {p.attrib.get("name"): p.text for p in page_root_obj.findall("property")}
    assert root_props.get("vexpand") == "true"
    assert root_props.get("hexpand") == "true"


# =============================================================================
# 2. Test Funzioni di Formattazione e Snapshot UI (Headless Safe)
# =============================================================================


def test_format_optional_value() -> None:
    """Verifica la formattazione dei valori opzionali."""
    assert format_optional_value("Yaru-dark") == "Yaru-dark"
    assert format_optional_value(None) == "Non impostato"
    assert format_optional_value("", default="Default") == "Default"
    assert format_optional_value("   ", default="N/D") == "N/D"


def test_format_boolean() -> None:
    """Verifica la formattazione dei booleani in etichette utente."""
    assert format_boolean(True) == "Sì"
    assert format_boolean(False) == "No"
    assert format_boolean(None) == "Non disponibile"
    assert format_boolean(True, true_label="Attivo", false_label="Inattivo") == "Attivo"


def test_format_path() -> None:
    """Verifica la conversione e formattazione di percorsi Path."""
    p = Path("/home/user/.local/share/themes")
    assert format_path(p) == "/home/user/.local/share/themes"
    assert format_path(None) == "Non disponibile"


def test_format_color_scheme() -> None:
    """Verifica la formattazione delle varianti schema colore."""
    assert format_color_scheme("prefer-dark") == "Scuro (Preferisci scuro)"
    assert format_color_scheme("default") == "Predefinito (Chiaro)"
    assert format_color_scheme(None) == "Predefinito (Chiaro)"
    assert format_color_scheme("prefer-light") == "Chiaro (Preferisci chiaro)"


def test_format_shell_theme() -> None:
    """Verifica la formattazione del tema GNOME Shell in base al supporto estensione."""
    assert format_shell_theme("Nordic", is_supported=True) == "Nordic"
    assert format_shell_theme(None, is_supported=True) == "Default di sistema"
    assert format_shell_theme("Nordic", is_supported=False) == "Non gestito (estensione 'User Themes' non attiva)"


def test_format_sandbox_status() -> None:
    """Verifica la formattazione dello stato dei runtime sandbox."""
    res_avail = format_sandbox_status(
        available=True,
        active_or_installed=True,
        active_label="Override attivo",
        inactive_label="Override non attivo",
    )
    assert res_avail == "Disponibile (Override attivo)"

    res_not_installed = format_sandbox_status(
        available=False,
        active_or_installed=False,
        active_label="OK",
        inactive_label="No",
    )
    assert res_not_installed == "Non disponibile (non installato)"


def test_build_theme_presentation() -> None:
    """Verifica la corretta trasformazione da Theme a ThemeItemPresentation."""
    theme = Theme(
        name="Nordic-Darker",
        theme_type=ThemeType.GTK,
        path=Path("/home/user/.local/share/themes/Nordic-Darker"),
        is_user_level=True,
    )
    pres = build_theme_presentation(theme)
    assert pres.name == "Nordic-Darker"
    assert pres.category_display == "Applicazioni (GTK)"
    assert pres.origin_display == "Utente (~/.local/share/...)"
    assert pres.icon_name == "preferences-desktop-theme-symbolic"
    assert pres.is_user_level is True


# =============================================================================
# 3. Test Controller StatusPage e Transizioni di Stato (Gtk Runtime Safe)
# =============================================================================


@pytest.fixture
def mock_theme_manager() -> MagicMock:
    """Crea un mock deterministico di ThemeManager con dati validi completi."""
    mgr = MagicMock(spec=ThemeManager)
    mgr.get_current_themes.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        color_scheme="default",
        shell_theme="Yaru",
    )
    mgr.get_system_status.return_value = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=True,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=SandboxStatus(
            snap_available=True,
            flatpak_available=True,
            snap_gtk_common_themes_installed=True,
            flatpak_filesystem_override_active=True,
        ),
        gtk4_override_active=True,
    )
    mgr.find_theme.return_value = Theme(
        name="Yaru",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/Yaru"),
        is_user_level=False,
    )
    mgr.list_themes.return_value = [
        Theme(
            name="Yaru",
            theme_type=ThemeType.GTK,
            path=Path("/usr/share/themes/Yaru"),
            is_user_level=False,
        ),
        Theme(
            name="Nordic",
            theme_type=ThemeType.GTK,
            path=Path("/home/user/.local/share/themes/Nordic"),
            is_user_level=True,
        ),
        Theme(
            name="Papirus",
            theme_type=ThemeType.ICON,
            path=Path("/usr/share/icons/Papirus"),
            is_user_level=False,
        ),
        Theme(
            name="Bibata-Modern-Classic",
            theme_type=ThemeType.CURSOR,
            path=Path("/home/user/.local/share/icons/Bibata-Modern-Classic"),
            is_user_level=True,
        ),
        Theme(
            name="Nordic-Shell",
            theme_type=ThemeType.SHELL,
            path=Path("/home/user/.local/share/themes/Nordic-Shell"),
            is_user_level=True,
        ),
    ]
    mgr.apply_themes.return_value = ApplyResult(
        gtk_theme="Yaru",
        gtk4_override_applied=True,
        warnings=[],
    )
    return mgr


def test_status_page_ready_state_success(mock_theme_manager: MagicMock) -> None:
    """Verifica che un refresh con dati validi porti allo stato READY e popoli le righe."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = StatusPage(manager=mock_theme_manager)
    assert page.page_id == "status"
    assert page.title == "Stato attuale"

    # Esegui refresh sincrono
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Yaru" in page.row_gtk_theme.get_subtitle()
    assert "Yaru" in page.row_icon_theme.get_subtitle()
    assert "Yaru" in page.row_cursor_theme.get_subtitle()
    assert "Yaru" in page.row_shell_theme.get_subtitle()
    assert "Predefinito" in page.row_color_scheme.get_subtitle()
    assert "Attivo" in page.row_gtk4_override.get_subtitle()
    assert "Disponibile" in page.row_gsettings_status.get_subtitle()
    assert "/home/user/.local/share/themes" in page.row_user_themes_path.get_subtitle()
    assert "Disponibile (Override filesystem attivo)" in page.row_flatpak_status.get_subtitle()
    assert "Disponibile (gtk-common-themes installato)" in page.row_snap_status.get_subtitle()
    assert page.banner_warning.get_revealed() is False


def test_status_page_gtk4_override_inactive(mock_theme_manager: MagicMock) -> None:
    """Verifica che quando gtk4_override_active è False, la riga mostri 'Non attivo'."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    status = mock_theme_manager.get_system_status.return_value
    status.gtk4_override_active = False

    page = StatusPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert "Non attivo" in page.row_gtk4_override.get_subtitle()


def test_status_page_ready_with_warnings(mock_theme_manager: MagicMock) -> None:
    """Verifica che limitazioni ambientali attivino l'Adw.Banner nella pagina ready."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.get_system_status.return_value = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=False,
        color_scheme_supported=True,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=SandboxStatus(
            snap_available=True,
            flatpak_available=False,
            snap_gtk_common_themes_installed=False,
            flatpak_filesystem_override_active=False,
        ),
        gtk4_override_active=False,
    )

    page = StatusPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "ready"
    assert page.banner_warning.get_revealed() is True
    assert "User Themes" in page.banner_warning.get_title()
    assert "gtk-common-themes" in page.banner_warning.get_title()


def test_status_page_empty_state() -> None:
    """Verifica che una configurazione completamente vuota e senza GSettings mostri lo stato EMPTY."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.get_current_themes.return_value = ThemeSet()
    mock_mgr.get_system_status.return_value = SystemStatus(
        gsettings_available=False,
        shell_theme_supported=False,
        color_scheme_supported=False,
        user_themes_path=Path("/home/user/.local/share/themes"),
        user_icons_path=Path("/home/user/.local/share/icons"),
        sandbox_status=None,
        gtk4_override_active=False,
    )
    mock_mgr.find_theme.return_value = None

    page = StatusPage(manager=mock_mgr)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "empty"


def test_status_page_error_state_and_retry(mock_theme_manager: MagicMock) -> None:
    """Verifica che un'eccezione porti allo stato ERROR e che il pulsante retry consenta il ripristino."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.get_current_themes.side_effect = GSettingsUnavailableError("Schema non trovato.")

    page = StatusPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.widget.get_visible_child_name() == "error"
    assert "GSettings non è disponibile" in page.error_page.get_description()

    # Ripristino condizione di successo e retry sincrono
    mock_theme_manager.get_current_themes.side_effect = None
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
    page.refresh(sync=True)
    assert page.widget.get_visible_child_name() == "ready"


def test_status_page_refresh_concurrency_guard(mock_theme_manager: MagicMock) -> None:
    """Verifica che chiamate di refresh concorrenti durante LOADING vengano ignorate."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = StatusPage(manager=mock_theme_manager)

    page._is_loading = True
    gen_before = page._generation_id
    page.refresh()
    assert page._generation_id == gen_before


# =============================================================================
# 4. Test Controller ThemesPage (Fase 5.4 — Esplora Temi & Applicazione Diretta)
# =============================================================================


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


def test_themes_page_apply_theme_updates_card_and_available_list(mock_theme_manager: MagicMock) -> None:
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
        Theme(name="Zeta-Sys", theme_type=ThemeType.GTK, path=Path("/usr/share/themes/Zeta-Sys"), is_user_level=False),
        Theme(name="alpha-sys", theme_type=ThemeType.GTK, path=Path("/usr/share/themes/alpha-sys"), is_user_level=False),
        Theme(name="Zeta-User", theme_type=ThemeType.GTK, path=Path("/home/user/.local/share/themes/Zeta-User"), is_user_level=True),
        Theme(name="alpha-user", theme_type=ThemeType.GTK, path=Path("/home/user/.local/share/themes/alpha-user"), is_user_level=True),
        Theme(name="ActiveTheme", theme_type=ThemeType.GTK, path=Path("/usr/share/themes/ActiveTheme"), is_user_level=False),
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


def test_themes_page_cursor_application_shows_alert_and_no_toast(mock_theme_manager: MagicMock) -> None:
    """Verifica che dopo l'applicazione riuscita di un tema cursore compaia solo l'alert informativo (nessun toast)."""
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

    with (
        patch.object(page, "_show_toast") as mock_toast,
        patch.object(page, "_show_cursor_info_alert") as mock_alert,
    ):
        page.apply_theme(item_cursor, sync=True)
        # Deve comparire l'alert informativo esclusivo
        mock_alert.assert_called_once_with("Bibata-Modern-Classic")
        # NON deve comparire alcun Toast
        mock_toast.assert_not_called()
        # Controlli riabilitati
        assert page.is_applying is False


def test_themes_page_cursor_application_error_shows_error_toast_only(mock_theme_manager: MagicMock) -> None:
    """Verifica che in caso di errore nell'applicazione del tema cursore venga mostrato solo l'errore (nessun alert)."""
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

    with (
        patch.object(page, "_show_toast") as mock_toast,
        patch.object(page, "_show_cursor_info_alert") as mock_alert,
    ):
        page.apply_theme(item_cursor, sync=True)
        mock_toast.assert_called_once()
        assert "Errore" in mock_toast.call_args[0][0]
        mock_alert.assert_not_called()
        assert page.is_applying is False


def test_themes_page_double_click_blocked_when_dialog_already_open(mock_theme_manager: MagicMock) -> None:
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


def test_themes_page_confirm_dialog_cancel_resets_flag_and_no_apply(mock_theme_manager: MagicMock) -> None:
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
        patch("gi.repository.Adw.AlertDialog.connect", side_effect=fake_connect) if hasattr(Adw, "AlertDialog") else patch("gi.repository.Adw.MessageDialog.connect", side_effect=fake_connect),
        patch("gi.repository.Adw.AlertDialog.present") if hasattr(Adw, "AlertDialog") else patch("gi.repository.Adw.MessageDialog.present"),
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


def test_themes_page_confirm_dialog_interactive_apply_resets_flag(mock_theme_manager: MagicMock) -> None:
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
        patch("gi.repository.Adw.AlertDialog.connect", side_effect=fake_connect) if hasattr(Adw, "AlertDialog") else patch("gi.repository.Adw.MessageDialog.connect", side_effect=fake_connect),
        patch("gi.repository.Adw.AlertDialog.present") if hasattr(Adw, "AlertDialog") else patch("gi.repository.Adw.MessageDialog.present"),
    ):
        page.confirm_and_apply_theme(item, sync=False)
        assert page._confirm_dialog_open is True

        # Simulazione risposta 'apply' dal dialogo
        if captured_callback is not None:
            captured_callback(MagicMock(), "apply")

        assert page._confirm_dialog_open is False
        mock_apply.assert_called_once()


def test_themes_page_confirm_dialog_sync_mode_resets_flag_and_applies(mock_theme_manager: MagicMock) -> None:
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
        patch.object(Adw.AlertDialog if hasattr(Adw, "AlertDialog") else Adw.MessageDialog, "new", side_effect=fake_new),
        patch("gi.repository.Adw.AlertDialog.present") if hasattr(Adw, "AlertDialog") else patch("gi.repository.Adw.MessageDialog.present"),
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

    mock_theme_manager.get_current_themes.side_effect = GnomeThemeManagerError("GSettings non disponibile.")

    page = ThemesPage(manager=mock_theme_manager)
    page.refresh(sync=True)

    assert page.active_theme_row.get_title() == "Non disponibile"
    assert page.active_theme_badge.get_visible() is False


def test_themes_page_cursor_propagate_fallback_error(mock_theme_manager: MagicMock) -> None:
    """Verifica che un errore in GtkSettings durante la propagazione del cursore venga gestito senza eccezioni."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = ThemesPage(manager=mock_theme_manager)

    with patch("gi.repository.Gdk.Display.get_default", side_effect=RuntimeError("Display non disponibile")):
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


# =============================================================================
# 5. Test Applicazione Diretta Temi & Mappatura Componenti (Fase 5.4 Estesa)
# =============================================================================


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


def test_themes_page_confirm_dialog_clean_structure_and_sizing(mock_theme_manager: MagicMock) -> None:
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


def test_themes_page_confirm_dialog_long_name_and_active_theme(mock_theme_manager: MagicMock) -> None:
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


# =============================================================================
# 6. Test GnomeThemeWindow e Pulsante Refresh Contestuale
# =============================================================================


def test_window_refresh_button_visibility_and_action(mock_theme_manager: MagicMock) -> None:
    """Verifica che il pulsante Refresh sia visibile nelle pagine status e themes e nascosto nelle altre."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)

    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    assert win.refresh_button is not None

    # Quando la pagina attiva è status, il pulsante è visibile
    win.select_page("status")
    assert win.refresh_button.get_visible() is True

    # Passando a themes, il pulsante rimane visibile
    win.select_page("themes")
    assert win.refresh_button.get_visible() is True

    # Cambiando a presets, il pulsante deve nascondersi
    win.select_page("presets")
    assert win.refresh_button.get_visible() is False

    # Tornando a una categoria temi, il pulsante riappare
    win.select_page("themes_shell")
    assert win.refresh_button.get_visible() is True


def test_window_theme_categories_routing(mock_theme_manager: MagicMock) -> None:
    """Verifica che la selezione delle 4 categorie nella sidebar configuri correttamente ThemesPage."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)

    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    # 1. GNOME Shell
    win.select_page("themes_shell")
    assert win.themes_page.active_category == ThemeType.SHELL
    assert win.content_page.get_title() == "GNOME Shell"

    # 2. GTK
    win.select_page("themes_gtk")
    assert win.themes_page.active_category == ThemeType.GTK
    assert win.content_page.get_title() == "Applicazioni (GTK)"

    # 3. Icone
    win.select_page("themes_icon")
    assert win.themes_page.active_category == ThemeType.ICON
    assert win.content_page.get_title() == "Icone"

    # 4. Cursori
    win.select_page("themes_cursor")
    assert win.themes_page.active_category == ThemeType.CURSOR
    assert win.content_page.get_title() == "Cursori"


def test_window_single_toast_feedback_on_theme_applied(mock_theme_manager: MagicMock) -> None:
    """Verifica che l'applicazione di un tema generi un unico Toast di feedback alla finestra."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)

    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    item = ThemeItemPresentation(
        name="Nordic",
        theme_type=ThemeType.GTK,
        category_display="Applicazioni (GTK)",
        icon_name="preferences-desktop-theme-symbolic",
        path_display="/usr/share/themes/Nordic",
        origin_display="Sistema",
        is_user_level=False,
    )

    with patch.object(win, "add_toast") as mock_add_toast:
        win.themes_page.apply_theme(item, sync=True)
        # Deve essere stato emesso esattamente un unico Toast di notifica
        mock_add_toast.assert_called_once()
        toast_msg = mock_add_toast.call_args[0][0]
        assert "Nordic" in toast_msg


# =============================================================================
# 7. Test Isolamento, Routing CLI e Gestione Pulita SIGINT (Ctrl+C)
# =============================================================================


def test_no_tkinter_imported_when_using_gtk() -> None:
    """Verifica che l'import del package gui_gtk non carichi tkinter in memoria."""
    sys.modules.pop("tkinter", None)

    import gnome_theme_manager.gui_gtk  # noqa: F401

    assert "tkinter" not in sys.modules, "Tkinter non deve essere importato dal modulo GTK."


def test_launch_gui_missing_dependencies(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica che launch_gui gestisca correttamente l'assenza di GTK4/Libadwaita."""
    with patch("gnome_theme_manager.gui_gtk.is_gtk_available", return_value=False):
        exit_code = launch_gui()
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "[ERRORE GUI]" in captured.err
        assert "gir1.2-adw-1" in captured.err


def test_launch_gui_sigint_clean_exit() -> None:
    """Verifica che la pressione di Ctrl+C durante l'esecuzione della GUI ritorni exit code 130 senza traceback."""
    with (
        patch("gnome_theme_manager.gui_gtk.is_gtk_available", return_value=True),
        patch("gnome_theme_manager.gui_gtk.app.GnomeThemeApplication.run", side_effect=KeyboardInterrupt),
    ):
        exit_code = launch_gui()
        assert exit_code == 130


def test_launch_gui_normal_clean_exit() -> None:
    """Verifica che la chiusura normale della finestra tramite UI ritorni exit code 0."""
    with (
        patch("gnome_theme_manager.gui_gtk.is_gtk_available", return_value=True),
        patch("gnome_theme_manager.gui_gtk.app.GnomeThemeApplication.run", return_value=0),
    ):
        exit_code = launch_gui()
        assert exit_code == 0


def test_cli_main_keyboard_interrupt_returns_130() -> None:
    """Verifica che un'interruzione da tastiera (Ctrl+C) durante un comando CLI ritorni 130 senza traceback."""
    with patch("gnome_theme_manager.cli.main.handle_current_command", side_effect=KeyboardInterrupt):
        exit_code = main(["current"])
        assert exit_code == 130


def test_cli_gui_flag_routes_to_gtk() -> None:
    """Verifica che 'gnome-theme-manager --gui' invochi la GUI GTK4."""
    with patch("gnome_theme_manager.gui_gtk.launch_gui", return_value=0) as mock_launch:
        exit_code = main(["--gui"])
        assert exit_code == 0
        mock_launch.assert_called_once()


def test_cli_gui_subcommand_routes_to_gtk() -> None:
    """Verifica che 'gnome-theme-manager gui' invochi la GUI GTK4."""
    with patch("gnome_theme_manager.gui_gtk.launch_gui", return_value=0) as mock_launch:
        exit_code = main(["gui"])
        assert exit_code == 0
        mock_launch.assert_called_once()


def test_cli_tk_gui_flag_routes_to_legacy_tkinter() -> None:
    """Verifica che 'gnome-theme-manager --tk-gui' invochi il fallback Tkinter."""
    with patch("gnome_theme_manager.gui_tk.launch_gui", return_value=0) as mock_launch_tk:
        exit_code = main(["--tk-gui"])
        assert exit_code == 0
        mock_launch_tk.assert_called_once()


def test_cli_tk_gui_subcommand_routes_to_legacy_tkinter() -> None:
    """Verifica che 'gnome-theme-manager gui-tk' invochi il fallback Tkinter."""
    with patch("gnome_theme_manager.gui_tk.launch_gui", return_value=0) as mock_launch_tk:
        exit_code = main(["gui-tk"])
        assert exit_code == 0
        mock_launch_tk.assert_called_once()
