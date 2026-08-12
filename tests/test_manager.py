"""Test di unità per la classe Facade ThemeManager."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.errors import GSettingsUnavailableError, ThemeNotFoundError
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


@pytest.fixture
def mock_scanner() -> MagicMock:
    """Mock per ThemeScanner."""
    scanner = MagicMock()
    return scanner


@pytest.fixture
def mock_gsettings() -> MagicMock:
    """Mock per GSettingsClient."""
    gsettings = MagicMock()
    gsettings.is_shell_theme_supported = True
    gsettings.get_current.return_value = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )
    return gsettings


@pytest.fixture
def mock_gtk4_linker() -> MagicMock:
    """Mock per GTK4ThemeLinker."""
    linker = MagicMock()
    linker.apply_override.return_value = True
    return linker


@pytest.fixture
def mock_installer(tmp_path: Path) -> MagicMock:
    """Mock per ThemeInstaller."""
    installer = MagicMock()
    installer.user_themes_dir = tmp_path / "themes"
    installer.user_icons_dir = tmp_path / "icons"
    return installer


@pytest.fixture
def mock_presets() -> MagicMock:
    """Mock per PresetManager."""
    presets = MagicMock()
    return presets


@pytest.fixture
def mock_sandbox() -> MagicMock:
    """Mock per SandboxBridge."""
    sandbox = MagicMock()
    sandbox.get_sandbox_status.return_value = SandboxStatus(
        snap_available=True,
        flatpak_available=True,
        snap_gtk_common_themes_installed=True,
        flatpak_filesystem_override_active=True,
    )
    sandbox.propagate_all.return_value = PropagationResult(
        flatpak_success=True,
        snap_success=True,
        flatpak_messages=["Flatpak OK"],
        snap_messages=["Snap OK"],
        warnings=[],
    )
    return sandbox


@pytest.fixture
def manager(
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    mock_gtk4_linker: MagicMock,
    mock_installer: MagicMock,
    mock_presets: MagicMock,
    mock_sandbox: MagicMock,
) -> ThemeManager:
    """Istanza di ThemeManager con componenti iniettati (mock)."""
    return ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        gtk4_linker=mock_gtk4_linker,
        installer=mock_installer,
        presets=mock_presets,
        sandbox_bridge=mock_sandbox,
    )


# -----------------------------------------------------------------------------
# Test Inizializzazione e Stato di Sistema
# -----------------------------------------------------------------------------


def test_manager_properties(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    mock_sandbox: MagicMock,
) -> None:
    """Verifica che i componenti siano accessibili tramite le relative proprietà."""
    assert manager.scanner == mock_scanner
    assert manager.gsettings == mock_gsettings
    assert manager.gtk4_linker is not None
    assert manager.installer is not None
    assert manager.presets is not None
    assert manager.sandbox == mock_sandbox


def test_manager_get_system_status(manager: ThemeManager, mock_installer: MagicMock) -> None:
    """Verifica il report diagnostico restituito da get_system_status()."""
    status: SystemStatus = manager.get_system_status()
    assert status.gsettings_available is True
    assert status.shell_theme_supported is True
    assert status.user_themes_path == mock_installer.user_themes_dir
    assert status.user_icons_path == mock_installer.user_icons_dir


def test_manager_get_current_themes(manager: ThemeManager, mock_gsettings: MagicMock) -> None:
    """Verifica il recupero dei temi attivi da get_current_themes()."""
    current = manager.get_current_themes()
    assert current.gtk_theme == "Nordic"
    mock_gsettings.get_current.assert_called_once()


def test_manager_gsettings_unavailable() -> None:
    """Verifica che l'assenza di GSettings sollevi GSettingsUnavailableError."""
    # Inizializziamo senza passare gsettings mock e forzando _gsettings = None
    mgr = ThemeManager(gsettings=None)
    mgr._gsettings = None

    with pytest.raises(GSettingsUnavailableError):
        mgr.get_current_themes()

    status = mgr.get_system_status()
    assert status.gsettings_available is False
    assert status.shell_theme_supported is False


# -----------------------------------------------------------------------------
# Test Elenco e Ricerca Temi
# -----------------------------------------------------------------------------


def test_manager_list_themes_by_type(manager: ThemeManager, mock_scanner: MagicMock, tmp_path: Path) -> None:
    """Verifica che list_themes deleghi correttamente a scanner per i vari tipi."""
    t_gtk = Theme("ThemeGTK", ThemeType.GTK, tmp_path / "1", True)
    t_icon = Theme("ThemeIcon", ThemeType.ICON, tmp_path / "2", True)
    t_cursor = Theme("ThemeCursor", ThemeType.CURSOR, tmp_path / "3", True)
    t_shell = Theme("ThemeShell", ThemeType.SHELL, tmp_path / "4", True)

    mock_scanner.scan_gtk_themes.return_value = [t_gtk]
    mock_scanner.scan_icon_themes.return_value = [t_icon]
    mock_scanner.scan_cursor_themes.return_value = [t_cursor]
    mock_scanner.scan_shell_themes.return_value = [t_shell]
    mock_scanner.scan_all.return_value = [t_gtk, t_icon, t_cursor, t_shell]

    assert manager.list_themes(ThemeType.GTK) == [t_gtk]
    mock_scanner.scan_gtk_themes.assert_called_with(user_only=False)

    assert manager.list_themes(ThemeType.ICON, user_only=True) == [t_icon]
    mock_scanner.scan_icon_themes.assert_called_with(user_only=True)

    assert manager.list_themes(ThemeType.CURSOR) == [t_cursor]
    assert manager.list_themes(ThemeType.SHELL) == [t_shell]
    assert len(manager.list_themes()) == 4


def test_manager_find_theme(manager: ThemeManager, mock_scanner: MagicMock, tmp_path: Path) -> None:
    """Verifica che find_theme deleghi a scanner."""
    t = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    mock_scanner.find_theme.return_value = t

    found = manager.find_theme("Nordic", ThemeType.GTK)
    assert found == t
    mock_scanner.find_theme.assert_called_once_with(name="Nordic", theme_type=ThemeType.GTK)


# -----------------------------------------------------------------------------
# Test Applicazione Temi
# -----------------------------------------------------------------------------


def test_manager_apply_themes_success(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    mock_gtk4_linker: MagicMock,
    tmp_path: Path,
) -> None:
    """Verifica l'applicazione completa di un ThemeSet valido."""
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    icon_theme = Theme("Papirus", ThemeType.ICON, tmp_path / "Papirus", True)
    cursor_theme = Theme("Adwaita", ThemeType.CURSOR, tmp_path / "Adwaita", False)
    shell_theme = Theme("Nordic", ThemeType.SHELL, tmp_path / "Nordic", True)

    mock_scanner.find_theme.side_effect = lambda name, t_type: {
        (ThemeType.GTK, "Nordic"): gtk_theme,
        (ThemeType.ICON, "Papirus"): icon_theme,
        (ThemeType.CURSOR, "Adwaita"): cursor_theme,
        (ThemeType.SHELL, "Nordic"): shell_theme,
    }.get((t_type, name))

    theme_set = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus",
        cursor_theme="Adwaita",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )

    result: ApplyResult = manager.apply_themes(theme_set, apply_gtk4_override=True)

    assert result.gtk_theme == "Nordic"
    assert result.icon_theme == "Papirus"
    assert result.cursor_theme == "Adwaita"
    assert result.color_scheme == "prefer-dark"
    assert result.shell_theme == "Nordic"
    assert result.gtk4_override_applied is True
    assert result.warnings == []

    mock_gsettings.apply.assert_called_once()
    mock_gtk4_linker.apply_override.assert_called_once_with(gtk_theme.path)


def test_manager_apply_themes_missing_theme_raises(manager: ThemeManager, mock_scanner: MagicMock) -> None:
    """Verifica che la mancanza di un tema sul filesystem sollevi ThemeNotFoundError."""
    mock_scanner.find_theme.return_value = None

    with pytest.raises(ThemeNotFoundError, match="GTK 'NonExistent'"):
        manager.apply_themes(ThemeSet(gtk_theme="NonExistent"))


def test_manager_apply_themes_invalid_color_scheme(manager: ThemeManager) -> None:
    """Verifica che uno schema colore non supportato sollevi ValueError."""
    with pytest.raises(ValueError, match="Schema colore 'neon-dark' non valido"):
        manager.apply_themes(ThemeSet(color_scheme="neon-dark"))


def test_manager_apply_themes_shell_unsupported_adds_warning(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    tmp_path: Path,
) -> None:
    """Verifica che l'assenza del supporto Shell aggiunga un warning a ApplyResult."""
    shell_theme = Theme("Nordic", ThemeType.SHELL, tmp_path / "Nordic", True)
    mock_scanner.find_theme.return_value = shell_theme
    mock_gsettings.is_shell_theme_supported = False

    result = manager.apply_themes(ThemeSet(shell_theme="Nordic"))

    assert len(result.warnings) == 1
    assert "User Themes" in result.warnings[0]
    assert result.shell_theme is None


def test_manager_apply_themes_no_gtk4_override(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gtk4_linker: MagicMock,
    tmp_path: Path,
) -> None:
    """Verifica che apply_gtk4_override=False disabiliti il linker GTK4."""
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    mock_scanner.find_theme.return_value = gtk_theme

    result = manager.apply_themes(ThemeSet(gtk_theme="Nordic"), apply_gtk4_override=False)

    assert result.gtk4_override_applied is False
    mock_gtk4_linker.apply_override.assert_not_called()


def test_manager_apply_unified_theme(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    tmp_path: Path,
) -> None:
    """Verifica l'applicazione unificata per GTK e Shell."""
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    shell_theme = Theme("Nordic", ThemeType.SHELL, tmp_path / "Nordic", True)

    mock_scanner.find_theme.side_effect = lambda name, t_type: (
        gtk_theme if t_type == ThemeType.GTK else shell_theme
    )

    result = manager.apply_unified_theme("Nordic", color_scheme="prefer-dark")
    assert result.gtk_theme == "Nordic"
    assert result.shell_theme == "Nordic"
    assert result.color_scheme == "prefer-dark"


def test_manager_apply_unified_theme_not_found(manager: ThemeManager, mock_scanner: MagicMock) -> None:
    """Verifica che un tema unificato inesistente sollevi ThemeNotFoundError."""
    mock_scanner.find_theme.return_value = None

    with pytest.raises(ThemeNotFoundError, match="non è stato trovato come GTK o GNOME Shell"):
        manager.apply_unified_theme("InexistentTheme")


# -----------------------------------------------------------------------------
# Test Preset e Gestione File
# -----------------------------------------------------------------------------


def test_manager_preset_workflow(
    manager: ThemeManager,
    mock_presets: MagicMock,
    mock_gsettings: MagicMock,
    mock_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Verifica il flusso completo di salvataggio, lista, applicazione ed eliminazione preset."""
    current_set = ThemeSet(gtk_theme="Nordic", icon_theme="Papirus")
    mock_gsettings.get_current.return_value = current_set

    # Save
    mock_presets.save_preset.return_value = tmp_path / "MyPreset.json"
    saved = manager.save_current_as_preset("MyPreset")
    assert saved.name == "MyPreset.json"
    mock_presets.save_preset.assert_called_once_with("MyPreset", current_set, overwrite=False)

    # List
    mock_presets.list_presets.return_value = ["MyPreset", "WorkPreset"]
    assert manager.list_presets() == ["MyPreset", "WorkPreset"]

    # Load
    mock_presets.load_preset.return_value = current_set
    loaded = manager.load_preset("MyPreset")
    assert loaded == current_set
    mock_presets.load_preset.assert_called_with("MyPreset")

    # Apply
    mock_presets.load_preset.return_value = current_set
    mock_scanner.find_theme.side_effect = lambda name, t_type: Theme(name, t_type, tmp_path / name, True)
    res = manager.apply_preset("MyPreset")
    assert res.gtk_theme == "Nordic"

    # Delete
    mock_presets.delete_preset.return_value = True
    assert manager.delete_preset("MyPreset") is True
    mock_presets.delete_preset.assert_called_once_with("MyPreset")


def test_manager_install_and_uninstall(manager: ThemeManager, mock_installer: MagicMock, tmp_path: Path) -> None:
    """Verifica la delega dei metodi di installazione e disinstallazione a ThemeInstaller."""
    archive = tmp_path / "theme.zip"
    installed_theme = Theme("Installed", ThemeType.GTK, tmp_path / "Installed", True)
    mock_installer.install.return_value = [installed_theme]
    mock_installer.uninstall.return_value = True

    res = manager.install_theme_archive(archive, theme_type=ThemeType.GTK, overwrite=True)
    assert res == [installed_theme]
    mock_installer.install.assert_called_once_with(
        archive_path=archive,
        theme_type=ThemeType.GTK,
        custom_name=None,
        overwrite=True,
    )

    uninstalled = manager.uninstall_theme("Installed", ThemeType.GTK)
    assert uninstalled is True
    mock_installer.uninstall.assert_called_once_with(theme_name="Installed", theme_type=ThemeType.GTK)
