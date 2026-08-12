"""Test di unità e integrazione per l'interfaccia grafica Tkinter (Fase 4).

Verifica il corretto funzionamento di:
- Finestra principale `ThemeManagerWindow` e ciclo `launch_gui`
- Scheda `CurrentStatusView` (aggiornamento stato e diagnostica)
- Scheda `AvailableThemesView` (popolamento Treeview, filtri, applicazione, disinstallazione)
- Scheda `PresetManagerView` (elenco, anteprima, salvataggio, applicazione, rimozione)
- Scheda `ThemeInstallerView` (selezione archivio, installazione, gestione sovrascrittura)
- Routing da riga di comando CLI con flag `--gui` e comando `gui`
"""

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

# Salta l'intero file di test se tkinter non è installato nell'ambiente (richiede python3-tk)
pytest.importorskip(
    "tkinter",
    reason="Modulo standard tkinter non installato nel sistema (installa con: sudo apt install python3-tk)",
)

import tkinter as tk
from tkinter import ttk

from gnome_theme_manager.cli.main import main
from gnome_theme_manager.core.errors import GSettingsUnavailableError, ThemeNotFoundError
from gnome_theme_manager.core.models import ApplyResult, SystemStatus, Theme, ThemeSet, ThemeType
from gnome_theme_manager.gui_tk.app import ThemeManagerWindow, launch_gui
from gnome_theme_manager.gui_tk.views import (
    AvailableThemesView,
    CurrentStatusView,
    PresetManagerView,
    ThemeInstallerView,
)

# Verifica se un display grafico X11/Wayland è disponibile per istanziare finestre Tk reali
_TK_DISPLAY_AVAILABLE = False
try:
    _test_tk = tk.Tk()
    _test_tk.withdraw()
    _test_tk.destroy()
    _TK_DISPLAY_AVAILABLE = True
except Exception:
    _TK_DISPLAY_AVAILABLE = False


@pytest.fixture
def mock_manager(tmp_path: Path) -> MagicMock:
    """Crea un mock completo del Facade ThemeManager."""
    manager = MagicMock()

    # Configurazione get_current_themes
    manager.get_current_themes.return_value = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        shell_theme="Nordic",
        color_scheme="prefer-dark",
    )

    # Configurazione get_system_status
    manager.get_system_status.return_value = SystemStatus(
        gsettings_available=True,
        shell_theme_supported=True,
        color_scheme_supported=True,
        user_themes_path=tmp_path / "themes",
        user_icons_path=tmp_path / "icons",
    )

    # Configurazione list_themes
    manager.list_themes.return_value = [
        Theme(name="Nordic", theme_type=ThemeType.GTK, path=tmp_path / "themes" / "Nordic", is_user_level=True),
        Theme(name="Adwaita", theme_type=ThemeType.GTK, path=Path("/usr/share/themes/Adwaita"), is_user_level=False),
        Theme(name="Papirus", theme_type=ThemeType.ICON, path=tmp_path / "icons" / "Papirus", is_user_level=True),
    ]

    # Configurazione apply_themes e apply_unified_theme
    apply_res = ApplyResult(
        gtk_theme="Nordic",
        gtk4_override_applied=True,
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        shell_theme="Nordic",
        color_scheme="prefer-dark",
        warnings=[],
    )
    manager.apply_themes.return_value = apply_res
    manager.apply_unified_theme.return_value = apply_res

    # Configurazione presets
    manager.list_presets.return_value = ["Dark-Nordic", "Default-Light"]
    manager.presets.load_preset.return_value = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        shell_theme="Nordic",
        color_scheme="prefer-dark",
    )
    manager.save_current_as_preset.return_value = tmp_path / "presets" / "Dark-Nordic.json"
    manager.delete_preset.return_value = True

    # Configurazione installer
    manager.install_theme_archive.return_value = [
        Theme(name="Nordic", theme_type=ThemeType.GTK, path=tmp_path / "themes" / "Nordic", is_user_level=True)
    ]
    manager.uninstall_theme.return_value = True

    return manager


@pytest.fixture
def tk_root():
    """Fixture che fornisce una root window Tkinter nascosta o skippa se headless."""
    if not _TK_DISPLAY_AVAILABLE:
        pytest.skip("Ambiente headless: nessun display X11/Wayland disponibile per istanziare Tkinter.")
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


# =============================================================================
# 1. Test CLI Routing (--gui / gui)
# =============================================================================


def test_cli_gui_flag_routing() -> None:
    """Verifica che il flag -g / --gui invochi launch_gui."""
    with patch("gnome_theme_manager.gui_tk.launch_gui", return_value=0) as mock_launch:
        exit_code = main(["--gui"])
        assert exit_code == 0
        mock_launch.assert_called_once()


def test_cli_gui_subcommand_routing() -> None:
    """Verifica che il subcomando 'gui' invochi launch_gui."""
    with patch("gnome_theme_manager.gui_tk.launch_gui", return_value=0) as mock_launch:
        exit_code = main(["gui"])
        assert exit_code == 0
        mock_launch.assert_called_once()


def test_launch_gui_entrypoint(mock_manager: MagicMock) -> None:
    """Verifica che launch_gui istanzi la finestra e avvii mainloop."""
    with patch("gnome_theme_manager.gui_tk.app.ThemeManagerWindow") as mock_window_cls:
        mock_win = MagicMock()
        mock_window_cls.return_value = mock_win

        code = launch_gui(manager=mock_manager)
        assert code == 0
        mock_window_cls.assert_called_once_with(manager=mock_manager)
        mock_win.mainloop.assert_called_once()


# =============================================================================
# 2. Test Finestra Principale ThemeManagerWindow
# =============================================================================


def test_theme_manager_window_init(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica l'inizializzazione corretta della finestra principale e del Notebook."""
    app = ThemeManagerWindow(manager=mock_manager)
    assert app.manager == mock_manager
    assert "Gnome Theme Manager" in app.title()
    assert len(app.notebook.tabs()) == 4

    # Verifica presenza delle 4 schede
    assert isinstance(app.status_view, CurrentStatusView)
    assert isinstance(app.themes_view, AvailableThemesView)
    assert isinstance(app.preset_view, PresetManagerView)
    assert isinstance(app.installer_view, ThemeInstallerView)

    # Test refresh globale
    app.refresh_all_views()
    assert "Dati aggiornati" in app.var_status_bar.get()
    app.destroy()


# =============================================================================
# 3. Test Scheda Stato Attuale (CurrentStatusView)
# =============================================================================


def test_current_status_view_refresh(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica che la vista dello stato attuale popoli correttamente le variabili Tkinter."""
    notebook = ttk.Notebook(tk_root)
    view = CurrentStatusView(notebook, manager=mock_manager)

    assert view.var_gtk.get() == "Nordic"
    assert view.var_icon.get() == "Papirus"
    assert view.var_cursor.get() == "Adwaita"
    assert view.var_shell.get() == "Nordic"
    assert view.var_color_scheme.get() == "prefer-dark"
    assert "✅" in view.var_gsettings_status.get()
    assert "Disponibile" in view.var_snap_status.get() or "Non" in view.var_snap_status.get()


def test_current_status_view_gsettings_unavailable(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica la gestione corretta quando GSettings non è disponibile."""
    mock_manager.get_current_themes.side_effect = GSettingsUnavailableError("GSettings assente")
    notebook = ttk.Notebook(tk_root)
    view = CurrentStatusView(notebook, manager=mock_manager)

    assert "Non disponibile" in view.var_gtk.get()


# =============================================================================
# 4. Test Scheda Temi Disponibili (AvailableThemesView)
# =============================================================================


def test_available_themes_view_population_and_filter(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica il popolamento della tabella e il filtraggio per tipologia e nome."""
    notebook = ttk.Notebook(tk_root)
    view = AvailableThemesView(notebook, manager=mock_manager)

    # Tabella inizialmente popolata con tutti i 3 temi
    children = view.tree.get_children()
    assert len(children) == 3

    # Filtro tipologia: solo ICON
    view.var_type_filter.set("Icone")
    view._apply_ui_filter()
    children = view.tree.get_children()
    assert len(children) == 1
    values = view.tree.item(children[0])["values"]
    assert values[0] == "Papirus"

    # Filtro ricerca per nome: "Nord"
    view.var_type_filter.set("Tutti i tipi")
    view.var_search_query.set("Nord")
    view._apply_ui_filter()
    children = view.tree.get_children()
    assert len(children) == 1
    assert view.tree.item(children[0])["values"][0] == "Nordic"


def test_available_themes_view_apply_and_uninstall(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica l'applicazione e la disinstallazione di un tema selezionato."""
    notebook = ttk.Notebook(tk_root)
    callback_mock = MagicMock()
    view = AvailableThemesView(notebook, manager=mock_manager, on_theme_applied=callback_mock)

    children = view.tree.get_children()
    # Seleziona il primo tema (Nordic, utente)
    view.tree.selection_set(children[0])
    view._on_tree_select(None)

    assert str(view.btn_apply["state"]) == tk.NORMAL
    assert str(view.btn_uninstall["state"]) == tk.NORMAL

    # Test applicazione tema
    with patch("tkinter.messagebox.showinfo") as mock_info:
        view._on_apply_selected()
        mock_manager.apply_themes.assert_called()
        mock_info.assert_called_once()
        callback_mock.assert_called_once()

    # Test disinstallazione tema con conferma positiva
    with patch("tkinter.messagebox.askyesno", return_value=True), patch("tkinter.messagebox.showinfo"):
        view._on_uninstall_selected()
        mock_manager.uninstall_theme.assert_called_with(name="Nordic", theme_type=ThemeType.GTK)


def test_available_themes_view_apply_unified(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica l'applicazione globale in 1 clic del tema a tutto il sistema (GTK + Shell)."""
    notebook = ttk.Notebook(tk_root)
    callback_mock = MagicMock()
    view = AvailableThemesView(notebook, manager=mock_manager, on_theme_applied=callback_mock)

    children = view.tree.get_children()
    # Seleziona il primo tema (Nordic, GTK)
    view.tree.selection_set(children[0])
    view._on_tree_select(None)

    assert str(view.btn_apply_unified["state"]) == tk.NORMAL

    # Test applicazione tema globale in un solo clic
    with patch("tkinter.messagebox.showinfo") as mock_info:
        view._on_apply_unified()
        mock_manager.apply_unified_theme.assert_called_with(
            theme_name="Nordic",
            apply_gtk4_override=True,
            propagate_sandbox=True,
        )
        mock_info.assert_called_once()
        callback_mock.assert_called_once()


# =============================================================================
# 5. Test Scheda Preset (PresetManagerView)
# =============================================================================


def test_preset_manager_view_operations(tk_root: tk.Tk, mock_manager: MagicMock) -> None:
    """Verifica le operazioni di salvataggio, anteprima, applicazione ed eliminazione preset."""
    notebook = ttk.Notebook(tk_root)
    callback_mock = MagicMock()
    view = PresetManagerView(notebook, manager=mock_manager, on_preset_applied=callback_mock)

    children = view.tree_presets.get_children()
    assert len(children) == 2

    # Seleziona il primo preset
    view.tree_presets.selection_set(children[0])
    view._on_preset_select(None)
    assert view.var_preview_gtk.get() == "Nordic"

    # Test applicazione preset
    with patch("tkinter.messagebox.showinfo") as mock_info:
        view._on_apply_preset()
        mock_manager.apply_preset.assert_called_with(
            "Dark-Nordic",
            apply_gtk4_override=True,
            propagate_sandbox=True,
        )
        mock_info.assert_called_once()
        callback_mock.assert_called_once()

    # Test salvataggio nuovo preset
    view.var_new_preset_name.set("Custom-Preset")
    with patch("tkinter.messagebox.showinfo") as mock_info:
        view._on_save_preset()
        mock_manager.save_current_as_preset.assert_called_with("Custom-Preset", overwrite=False)
        mock_info.assert_called()

    # Test eliminazione preset con conferma (riseleziona il preset dopo il refresh della tabella)
    children = view.tree_presets.get_children()
    view.tree_presets.selection_set(children[0])
    with patch("tkinter.messagebox.askyesno", return_value=True), patch("tkinter.messagebox.showinfo"):
        view._on_delete_preset()
        mock_manager.delete_preset.assert_called_with("Dark-Nordic")


# =============================================================================
# 6. Test Scheda Installer (ThemeInstallerView)
# =============================================================================


def test_theme_installer_view_flow(tk_root: tk.Tk, mock_manager: MagicMock, tmp_path: Path) -> None:
    """Verifica la selezione del file archivio e l'avvio dell'installazione."""
    archive_file = tmp_path / "theme.zip"
    archive_file.write_text("dummy archive")

    notebook = ttk.Notebook(tk_root)
    callback_mock = MagicMock()
    view = ThemeInstallerView(notebook, manager=mock_manager, on_installation_success=callback_mock)

    # Test selezione file
    with patch("tkinter.filedialog.askopenfilename", return_value=str(archive_file)):
        view._on_browse_file()
        assert view.var_archive_path.get() == str(archive_file)

    # Test installazione
    with patch("tkinter.messagebox.showinfo") as mock_info:
        view._on_install_click()
        mock_manager.install_theme_archive.assert_called_with(
            archive_path=archive_file,
            theme_type=None,
            custom_name=None,
            overwrite=False,
        )
        mock_info.assert_called_once()
        callback_mock.assert_called_once()
