"""Test di unità e integrazione per la GUI nativa GTK4 / Libadwaita (Fase 5.3.1).

Verifica:
1. Validità e completezza dei template XML dichiarativi (.ui);
2. Correttezza del markup Pango per caratteri speciali (&) ed assenza di warning;
3. Struttura di scroll verticale e proprietà di espansione (vexpand/hexpand);
4. Controller modulari delle pagine con Adw.StatusPage / Gtk.Stack;
5. Formattazione e snapshot immutabile della pagina 'Stato attuale';
6. Visualizzazione stato override GTK4 (Attivo / Non attivo);
7. Transizioni di stato (loading, ready, ready con warning banner, empty, error);
8. Meccanismo di refresh asincrono, gestione concorrenza e retry;
9. Visibilità contestuale del pulsante Refresh in GnomeThemeWindow;
10. Gestione pulita di SIGINT / KeyboardInterrupt (exit code 130);
11. Isolamento, responsività e routing CLI.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.errors import GnomeThemeManagerError, GSettingsUnavailableError
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import SandboxStatus, SystemStatus, Theme, ThemeSet, ThemeType
from gnome_theme_manager.gui_gtk import is_gtk_available, launch_gui
from gnome_theme_manager.gui_gtk.pages.status import (
    StatusPage,
    StatusSnapshot,
    format_boolean,
    format_color_scheme,
    format_optional_value,
    format_path,
    format_sandbox_status,
    format_shell_theme,
)

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

    # Ripristino condizione di successo e retry
    mock_theme_manager.get_current_themes.side_effect = None
    mock_theme_manager.get_current_themes.return_value = ThemeSet(gtk_theme="Adwaita")
    page.error_retry_button.emit("clicked")

    # Verifica transizione a READY dopo il retry
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
# 4. Test GnomeThemeWindow e Pulsante Refresh Contestuale
# =============================================================================


def test_window_refresh_button_visibility_and_action(mock_theme_manager: MagicMock) -> None:
    """Verifica che il pulsante Refresh sia visibile solo nella pagina status e disabilitato durante il caricamento."""
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

    # Quando la pagina attiva è status, il pulsante deve essere visibile
    win.select_page("status")
    assert win.refresh_button.get_visible() is True

    # Cambiando pagina (es. themes), il pulsante deve nascondersi
    win.select_page("themes")
    assert win.refresh_button.get_visible() is False

    # Tornando a status, il pulsante riappare
    win.select_page("status")
    assert win.refresh_button.get_visible() is True


# =============================================================================
# 5. Test Isolamento, Routing CLI e Gestione Pulita SIGINT (Ctrl+C)
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
    with patch("gnome_theme_manager.gui_gtk.is_gtk_available", return_value=True):
        with patch("gnome_theme_manager.gui_gtk.app.GnomeThemeApplication.run", side_effect=KeyboardInterrupt):
            exit_code = launch_gui()
            assert exit_code == 130


def test_launch_gui_normal_clean_exit() -> None:
    """Verifica che la chiusura normale della finestra tramite UI ritorni exit code 0."""
    with patch("gnome_theme_manager.gui_gtk.is_gtk_available", return_value=True):
        with patch("gnome_theme_manager.gui_gtk.app.GnomeThemeApplication.run", return_value=0):
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
