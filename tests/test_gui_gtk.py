"""Test di unità e integrazione per la GUI nativa GTK4 / Libadwaita (Fase 5.2.1).

Verifica:
1. Validità e completezza dei template XML dichiarativi (.ui);
2. Controller modulari delle 5 pagine (status, themes, presets, installer, sandbox) con Adw.StatusPage;
3. Shell principale GnomeThemeWindow con Adw.NavigationSplitView e Gtk.Stack router;
4. Invarianza di split_view.get_content() durante la navigazione (zero set_content post-init);
5. Dimensionamento minimo (width-request / height-request) per eliminare i warning Adwaita;
6. Comportamento responsive (modalità normale e compatta / collapsed);
7. Isolamento e routing CLI.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.gui_gtk import is_gtk_available, launch_gui

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


def test_window_ui_structure_and_sizing() -> None:
    """Verifica che window.ui contenga AdwToastOverlay con dimensionamento, GtkStack e le 5 righe."""
    window_ui_path = UI_DIR / "window.ui"
    tree = ET.parse(window_ui_path)
    root = tree.getroot()

    object_classes = [elem.attrib.get("class") for elem in root.iter("object")]
    object_ids = [elem.attrib.get("id") for elem in root.iter("object") if "id" in elem.attrib]

    assert "AdwToastOverlay" in object_classes
    assert "AdwNavigationSplitView" in object_classes
    assert "GtkListBox" in object_classes
    assert "GtkStack" in object_classes

    assert "toast_overlay" in object_ids
    assert "split_view" in object_ids
    assert "sidebar_list_box" in object_ids
    assert "content_page" in object_ids
    assert "content_stack" in object_ids
    assert "row_status" in object_ids
    assert "row_themes" in object_ids
    assert "row_presets" in object_ids
    assert "row_installer" in object_ids
    assert "row_sandbox" in object_ids

    # Verifica presenza width-request e height-request su toast_overlay
    toast_obj = next(elem for elem in root.iter("object") if elem.attrib.get("id") == "toast_overlay")
    props = {p.attrib.get("name"): p.text for p in toast_obj.findall("property")}
    assert int(props.get("width-request", 0)) >= 760
    assert int(props.get("height-request", 0)) >= 520


@pytest.mark.parametrize(
    ("page_filename", "expected_title"),
    [
        ("status_page.ui", "Stato attuale"),
        ("themes_page.ui", "Esplora temi"),
        ("presets_page.ui", "Profili e preset"),
        ("installer_page.ui", "Installatore temi"),
        ("sandbox_page.ui", "Strumenti sandbox"),
    ],
)
def test_page_ui_templates_structure(
    page_filename: str,
    expected_title: str,
) -> None:
    """Verifica la presenza di AdwStatusPage e titolo nei template di pagina."""
    page_path = UI_DIR / page_filename
    tree = ET.parse(page_path)
    root = tree.getroot()

    classes = [elem.attrib.get("class") for elem in root.iter("object")]
    assert "AdwStatusPage" in classes, f"{page_filename} deve contenere AdwStatusPage"

    status_obj = next(elem for elem in root.iter("object") if elem.attrib.get("class") == "AdwStatusPage")
    props = {p.attrib.get("name"): p.text for p in status_obj.findall("property")}
    assert props.get("title") == expected_title


# =============================================================================
# 2. Test Disponibilità GTK e Controller Pagine (Gtk4 / Libadwaita Runtime)
# =============================================================================


def test_is_gtk_available_detection() -> None:
    """Verifica che is_gtk_available() ritorni un valore booleano coerente."""
    res = is_gtk_available()
    assert isinstance(res, bool)


@pytest.mark.parametrize(
    ("controller_module", "controller_class", "expected_id", "expected_title"),
    [
        ("status", "StatusPage", "status", "Stato attuale"),
        ("themes", "ThemesPage", "themes", "Esplora temi"),
        ("presets", "PresetsPage", "presets", "Profili e preset"),
        ("installer", "InstallerPage", "installer", "Installatore temi"),
        ("sandbox", "SandboxPage", "sandbox", "Strumenti sandbox"),
    ],
)
def test_page_controllers_initialization(
    controller_module: str,
    controller_class: str,
    expected_id: str,
    expected_title: str,
) -> None:
    """Verifica l'istanziazione e i metadati dei singoli controller delle pagine."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 / Libadwaita non disponibili in questo ambiente.")

    import importlib
    mod = importlib.import_module(f"gnome_theme_manager.gui_gtk.pages.{controller_module}")
    cls = getattr(mod, controller_class)

    mock_mgr = MagicMock(spec=ThemeManager)
    instance = cls(manager=mock_mgr)

    assert instance.page_id == expected_id
    assert instance.title == expected_title
    assert instance.get_widget() is not None

    widget = instance.get_widget()
    assert widget.get_title() == expected_title


# =============================================================================
# 3. Test Shell GnomeThemeWindow, Router GtkStack e Dimensionamento (Fase 5.2.1)
# =============================================================================


def test_window_initialization_and_stack_router() -> None:
    """Verifica l'inizializzazione della finestra, il router basato su GtkStack e il dimensionamento minimo."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 / Libadwaita non disponibili in questo ambiente.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    mock_mgr = MagicMock(spec=ThemeManager)
    app = GnomeThemeApplication(manager=mock_mgr)

    try:
        win = GnomeThemeWindow(app=app, manager=mock_mgr)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    # Verifica componenti principali
    assert win.toast_overlay is not None
    assert win.split_view is not None
    assert win.sidebar_list_box is not None
    assert win.content_page is not None
    assert win.content_stack is not None

    # Verifica dimensionamento minimo
    min_width, min_height = win.get_size_request()
    assert min_width >= 760
    assert min_height >= 520

    # Verifica che split_view.get_content() sia content_page
    assert win.split_view.get_content() == win.content_page

    # Verifica registrazione delle 5 pagine nel router
    assert set(win.pages.keys()) == {"status", "themes", "presets", "installer", "sandbox"}

    # Verifica che tutti i widget siano figli dello stesso Gtk.Stack
    for page_id, controller in win.pages.items():
        child = win.content_stack.get_child_by_name(page_id)
        assert child == controller.get_widget()

    # Verifica che la pagina iniziale sia 'status'
    assert win.current_page_id == "status"
    assert win.content_stack.get_visible_child_name() == "status"
    assert win.content_page.get_title() == "Stato attuale"

    # Test toast non bloccante
    win.add_toast("Notifica di test")


def test_window_page_navigation_invariance() -> None:
    """Verifica che split_view.get_content() rimanga invariato e la navigazione usi GtkStack."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 / Libadwaita non disponibili in questo ambiente.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    mock_mgr = MagicMock(spec=ThemeManager)
    app = GnomeThemeApplication(manager=mock_mgr)

    try:
        win = GnomeThemeWindow(app=app, manager=mock_mgr)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    initial_content = win.split_view.get_content()

    # Patch su set_content per assicurarsi che NON venga chiamato durante la navigazione
    with patch.object(win.split_view, "set_content") as mock_set_content:
        for page_id in ["themes", "presets", "installer", "sandbox", "status"]:
            win.select_page(page_id)
            assert win.current_page_id == page_id
            assert win.content_stack.get_visible_child_name() == page_id
            assert win.content_page.get_title() == win.pages[page_id].title
            # split_view.get_content() deve rimanere sempre lo stesso oggetto
            assert win.split_view.get_content() == initial_content

        # Verifica che set_content non sia mai stato invocato
        mock_set_content.assert_not_called()

    # Test resilienza con page_id sconosciuto
    current_before = win.current_page_id
    win.select_page("pagina_inesistente")
    assert win.current_page_id == current_before


def test_responsive_collapsed_behavior() -> None:
    """Verifica il comportamento in modalità compatta (collapsed=True) e show_content."""
    if not is_gtk_available():
        pytest.skip("PyGObject / GTK4 / Libadwaita non disponibili in questo ambiente.")

    from gnome_theme_manager.gui_gtk.app import GnomeThemeApplication
    from gnome_theme_manager.gui_gtk.window import GnomeThemeWindow

    mock_mgr = MagicMock(spec=ThemeManager)
    app = GnomeThemeApplication(manager=mock_mgr)

    try:
        win = GnomeThemeWindow(app=app, manager=mock_mgr)
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"Display non disponibile in ambiente headless: {err}")

    # Simulazione modalità compatta
    win.split_view.set_collapsed(True)
    assert win.split_view.get_collapsed() is True

    # Selezionando una pagina in modalità collapsed, show_content deve diventare True
    win.select_page("themes")
    assert win.split_view.get_show_content() is True
    assert win.content_stack.get_visible_child_name() == "themes"

    # Simulazione del ritorno alla sidebar
    win.split_view.set_show_content(False)
    assert win.split_view.get_show_content() is False

    # Ripristino modalità larga
    win.split_view.set_collapsed(False)
    assert win.split_view.get_collapsed() is False


# =============================================================================
# 4. Test Isolamento e Routing CLI
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
