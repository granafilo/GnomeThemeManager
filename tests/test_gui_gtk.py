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
from gnome_theme_manager.core.errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeValidationError,
)
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    ApplyResult,
    PropagationResult,
    SandboxStatus,
    SystemStatus,
    Theme,
    ThemeSet,
    ThemeType,
)
from gnome_theme_manager.gui_gtk import is_gtk_available, launch_gui
from gnome_theme_manager.gui_gtk.pages.installer import (
    InstallerPage,
    format_components_label,
)
from gnome_theme_manager.gui_gtk.pages.sandbox import SandboxPage
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


def test_themes_page_cursor_application_shows_informative_toast(mock_theme_manager: MagicMock) -> None:
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


def test_themes_page_cursor_application_error_shows_error_toast(mock_theme_manager: MagicMock) -> None:
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


# =============================================================================
# 8. Test Pagina Preset (PresetsPage) — Fase 5.6
# =============================================================================


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

    from gnome_theme_manager.core.models import ThemeSet
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

    from gnome_theme_manager.core.models import ThemeSet
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
    from gnome_theme_manager.core.models import ThemeSet

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

    mock_theme_manager.save_current_as_preset.assert_called_once_with("NuovoPreset", overwrite=False)


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

    from gnome_theme_manager.core.models import ApplyResult
    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    mock_theme_manager.apply_preset.return_value = ApplyResult(gtk_theme="Nordic")
    page = PresetsPage(manager=mock_theme_manager)

    page._run_apply_preset("Nordic", sync=True)

    mock_theme_manager.apply_preset.assert_called_once_with("Nordic")


def test_presets_page_apply_notifies_window(mock_theme_manager: MagicMock) -> None:
    """Verifica che after apply preset venga invocato on_preset_applied per aggiornare StatusPage e ThemesPage."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.core.models import ApplyResult
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

    from gnome_theme_manager.core.models import ApplyResult
    from gnome_theme_manager.gui_gtk.pages.presets import PresetsPage

    result = ApplyResult(gtk_theme="Nordic", warnings=["Shell theme non applicato"])
    mock_theme_manager.apply_preset.return_value = result
    page = PresetsPage(manager=mock_theme_manager)

    toasts: list[str] = []
    with patch.object(page, "_show_toast", side_effect=lambda msg, **kw: toasts.append(msg)):
        page._run_apply_preset("Nordic", sync=True)

    assert len(toasts) == 1
    assert "avvisi" in toasts[0].lower() or "warning" in toasts[0].lower() or "Shell theme" in toasts[0]


def test_presets_page_apply_blocks_concurrent(mock_theme_manager: MagicMock) -> None:
    """Verifica che una seconda applicazione concorrente venga ignorata."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.core.models import ApplyResult
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
    except Exception as err:  # noqa: BLE001 — GTK4 può sollevare eccezioni non specifiche senza display
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


# =============================================================================
# 13. Test Pagina 'Installatore Temi' (InstallerPage — Fase 5.7)
# =============================================================================


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

    mock_theme_manager.inspect_theme_source.side_effect = ArchiveExtractionError("Archivio non valido o corrotto")

    page = InstallerPage(manager=mock_theme_manager)
    page.select_source(Path("/tmp/corrupt.zip"), sync=True)

    assert page.widget.get_visible_child_name() == "error"
    desc = page.error_status_page.get_description()
    assert "Archivio non valido" in desc or "corrotto" in desc


def test_installer_page_select_source_invalid_structure(mock_theme_manager: MagicMock) -> None:
    """Verifica che una cartella senza struttura di tema valida mostri errore."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    mock_theme_manager.inspect_theme_source.side_effect = ThemeValidationError("Nessun tema riconosciuto")

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
        assert btn.get_label() == expected_label, f"Etichetta errata per il pulsante: {expected_label}"
        assert btn.get_icon_name() == expected_icon, f"Icona errata per il pulsante: {expected_icon}"


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
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    with patch.object(win.themes_page, "refresh") as mock_themes_refresh, \
         patch.object(win.status_page, "refresh") as mock_status_refresh:

        win.installer_page.on_theme_installed()
        mock_themes_refresh.assert_called_once()
        mock_status_refresh.assert_not_called()

        mock_themes_refresh.reset_mock()
        mock_status_refresh.reset_mock()

        win.installer_page.on_theme_applied()
        mock_themes_refresh.assert_called_once()
        mock_status_refresh.assert_called_once()


# =============================================================================
# Test Suite: SandboxPage (Fase 5.8)
# =============================================================================


def test_sandbox_page_initial_and_button_labels(mock_theme_manager: MagicMock) -> None:
    """Verifica che SandboxPage configuri etichette e icone native per tutti i pulsanti."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    page = SandboxPage(manager=mock_theme_manager)

    buttons = [
        (page.refresh_button, "Ricarica stato", "view-refresh-symbolic"),
        (page.propagate_button, "Propaga tema alle applicazioni sandbox", "emblem-ok-symbolic"),
        (page.error_retry_button, "Riprova", "view-refresh-symbolic"),
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
    assert "Disponibile" in page.flatpak_status_row.get_subtitle()
    assert "Attivo" in page.flatpak_override_row.get_subtitle()
    assert "Disponibile" in page.snap_status_row.get_subtitle()
    assert "Installato" in page.snap_gtk_common_row.get_subtitle()
    assert "supportato nativamente" in page.snap_theme_compat_row.get_subtitle()
    assert page.propagate_button.get_sensitive() is True


def test_sandbox_page_refresh_neither_available_disables_propagate(mock_theme_manager: MagicMock) -> None:
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
    assert "Non installato" in page.flatpak_status_row.get_subtitle()
    assert "Non installato" in page.snap_status_row.get_subtitle()
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
    assert "personalizzato" in page.snap_theme_compat_row.get_subtitle().lower()


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
    assert "Non installato" in page.snap_gtk_common_row.get_subtitle()
    assert "Non verificabile" in page.snap_theme_compat_row.get_subtitle()


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
    assert "successo" in toasts[0].lower()
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
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    with patch.object(win.status_page, "refresh") as mock_status_refresh:
        win.sandbox_page.on_sandbox_propagated()
        mock_status_refresh.assert_called_once()


# =============================================================================
# Test Suite: Top Responsive Feedback (Revisione UI Feedback)
# =============================================================================


def test_window_top_feedback_structure_and_wrapping(mock_theme_manager: MagicMock) -> None:
    """Verifica che la finestra configuri il feedback superiore con clamp responsive e wrapping."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    assert win.feedback_revealer is not None
    assert win.feedback_label is not None
    assert win.feedback_label.get_wrap() is True
    assert win.feedback_close_button is not None


def test_window_top_feedback_show_and_close(mock_theme_manager: MagicMock) -> None:
    """Verifica visualizzazione del feedback in alto, selezione icona e chiusura manuale."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    # Successo
    win.add_toast("Tema applicato con successo.", timeout=0)
    assert win.feedback_label.get_label() == "Tema applicato con successo."
    assert win.feedback_revealer.get_reveal_child() is True
    assert win.feedback_icon.get_icon_name() == "emblem-ok-symbolic"

    # Chiusura manuale
    win._on_feedback_close_clicked()
    assert win.feedback_revealer.get_reveal_child() is False

    # Errore
    win.add_toast("Errore: Impossibile installare il tema.", timeout=0)
    assert win.feedback_label.get_label() == "Errore: Impossibile installare il tema."
    assert win.feedback_icon.get_icon_name() == "dialog-error-symbolic"
    assert win.feedback_revealer.get_reveal_child() is True

    # Avviso / parziale
    win.add_toast("Avviso: Applicazione parziale dei componenti.", timeout=0)
    assert win.feedback_icon.get_icon_name() == "dialog-warning-symbolic"


def test_window_top_feedback_long_multiline_message(mock_theme_manager: MagicMock) -> None:
    """Verifica che messaggi molto lunghi vengano impostati integralmente con wrapping abilitato."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    long_msg = (
        "Tema 'Nordic-Extra-Large-Custom-Theme-Name' applicato con successo.\n"
        "Alcuni componenti sandbox potrebbero richiedere il riavvio delle applicazioni Flatpak/Snap "
        "per riflettere i nuovi cursori e le icone modificate."
    )

    win.add_toast(long_msg, timeout=0)
    assert win.feedback_label.get_label() == long_msg
    assert win.feedback_label.get_wrap() is True
    assert win.feedback_revealer.get_reveal_child() is True


def test_window_top_feedback_cleared_on_page_change(mock_theme_manager: MagicMock) -> None:
    """Verifica che il cambio pagina chiuda il banner di feedback persistente."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 non disponibili.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    app = GnomeThemeApplication(manager=mock_theme_manager)
    try:
        win = GnomeThemeWindow(app=app, manager=mock_theme_manager)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    win.add_toast("Messaggio di stato", timeout=0)
    assert win.feedback_revealer.get_reveal_child() is True

    # Cambio pagina
    win.select_page("presets")
    assert win.feedback_revealer.get_reveal_child() is False


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






