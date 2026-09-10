# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for the ThemeManager Facade class."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gnome_theme_manager.core.errors import GSettingsUnavailableError, ThemeNotFoundError
from gnome_theme_manager.core.gtk4_linker import GTK4ThemeLinker
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
    """Mock for ThemeScanner."""
    scanner = MagicMock()
    return scanner


@pytest.fixture
def mock_gsettings() -> MagicMock:
    """Mock for GSettingsClient."""
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
    """Mock for GTK4ThemeLinker."""
    linker = MagicMock()
    linker.apply_override.return_value = True
    return linker


@pytest.fixture
def mock_installer(tmp_path: Path) -> MagicMock:
    """Mock for ThemeInstaller."""
    installer = MagicMock()
    installer.user_themes_dir = tmp_path / "themes"
    installer.user_icons_dir = tmp_path / "icons"
    return installer


@pytest.fixture
def mock_presets() -> MagicMock:
    """Mock for PresetManager."""
    presets = MagicMock()
    return presets


@pytest.fixture
def mock_sandbox() -> MagicMock:
    """Mock for SandboxBridge."""
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
def mock_validator() -> MagicMock:
    """Mock for ThemeValidator."""
    validator = MagicMock()
    validator.validate.return_value = MagicMock(valid=True, warnings=[], missing_files=[])
    return validator


@pytest.fixture
def mock_extensions() -> MagicMock:
    """Mock for ExtensionsManager."""
    ext = MagicMock()
    ext.is_user_theme_enabled.return_value = False
    return ext


@pytest.fixture
def manager(
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    mock_gtk4_linker: MagicMock,
    mock_installer: MagicMock,
    mock_presets: MagicMock,
    mock_sandbox: MagicMock,
    mock_validator: MagicMock,
    mock_extensions: MagicMock,
) -> ThemeManager:
    """ThemeManager instance with injected mock components."""
    return ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        gtk4_linker=mock_gtk4_linker,
        installer=mock_installer,
        presets=mock_presets,
        sandbox_bridge=mock_sandbox,
        validator=mock_validator,
        extensions=mock_extensions,
    )


# -----------------------------------------------------------------------------
# System Status and Initialization Tests
# -----------------------------------------------------------------------------


def test_manager_properties(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    mock_sandbox: MagicMock,
) -> None:
    """Verify that components are accessible via relative properties."""
    assert manager.scanner == mock_scanner
    assert manager.gsettings == mock_gsettings
    assert manager.gtk4_linker is not None
    assert manager.installer is not None
    assert manager.presets is not None
    assert manager.sandbox == mock_sandbox


def test_manager_get_system_status(manager: ThemeManager, mock_installer: MagicMock) -> None:
    """Verify diagnostic report returned by get_system_status()."""
    status: SystemStatus = manager.get_system_status()
    assert status.gsettings_available is True
    assert status.shell_theme_supported is True
    assert status.user_themes_path == mock_installer.user_themes_dir
    assert status.user_icons_path == mock_installer.user_icons_dir


def test_manager_get_current_themes(manager: ThemeManager, mock_gsettings: MagicMock) -> None:
    """Verify retrieval of active themes from get_current_themes()."""
    current = manager.get_current_themes()
    assert current.gtk_theme == "Nordic"
    mock_gsettings.get_current.assert_called_once()


def test_manager_gsettings_unavailable() -> None:
    """Verify that missing GSettings raises GSettingsUnavailableError."""
    # Initialize without mock gsettings and forcing _gsettings = None
    mgr = ThemeManager(gsettings=None)
    mgr._gsettings = None

    with pytest.raises(GSettingsUnavailableError):
        mgr.get_current_themes()

    status = mgr.get_system_status()
    assert status.gsettings_available is False
    assert status.shell_theme_supported is False


# -----------------------------------------------------------------------------
# Theme Listing and Search Tests
# -----------------------------------------------------------------------------


def test_manager_list_themes_by_type(
    manager: ThemeManager, mock_scanner: MagicMock, tmp_path: Path
) -> None:
    """Verify that list_themes delegates correctly to scanner for each type."""
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
    """Verify that find_theme delegates to scanner."""
    t = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    mock_scanner.find_theme.return_value = t

    found = manager.find_theme("Nordic", ThemeType.GTK)
    assert found == t
    mock_scanner.find_theme.assert_called_once_with(name="Nordic", theme_type=ThemeType.GTK)


# -----------------------------------------------------------------------------
# Theme Application Tests
# -----------------------------------------------------------------------------


def test_manager_apply_themes_success(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    mock_gtk4_linker: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify complete application of a valid ThemeSet."""
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


def test_manager_apply_themes_gtk4_override_stale_cleanup(tmp_path: Path) -> None:
    """Verify end-to-end that applying a GTK4 theme then a non-GTK4 theme removes override from ~/.config/gtk-4.0/."""
    config_dir = tmp_path / "config" / "gtk-4.0"
    user_themes = tmp_path / "user_themes"

    # Theme A with GTK4
    theme_a_dir = user_themes / "ThemeWithGTK4"
    gtk4_a = theme_a_dir / "gtk-4.0"
    gtk4_a.mkdir(parents=True)
    (gtk4_a / "gtk.css").write_text("/* theme A css */")

    # Theme B valid as generic GTK but without CSS
    theme_b_dir = user_themes / "ThemeWithoutGTK4"
    theme_b_dir.mkdir(parents=True)
    (theme_b_dir / "index.theme").write_text("[Desktop Entry]\nName=ThemeWithoutGTK4\n")

    theme_a = Theme("ThemeWithGTK4", ThemeType.GTK, theme_a_dir, True)
    theme_b = Theme("ThemeWithoutGTK4", ThemeType.GTK, theme_b_dir, True)

    mock_scanner = MagicMock()
    mock_scanner.find_theme.side_effect = lambda name, t_type: {
        "ThemeWithGTK4": theme_a,
        "ThemeWithoutGTK4": theme_b,
    }.get(name)

    mock_gsettings = MagicMock()
    linker = GTK4ThemeLinker(config_dir=config_dir)
    mock_val = MagicMock()
    mock_val.validate.return_value = MagicMock(valid=True, warnings=[], missing_files=[])

    mgr = ThemeManager(
        scanner=mock_scanner,
        gsettings=mock_gsettings,
        gtk4_linker=linker,
        validator=mock_val,
    )

    # 1. Apply Theme A -> override active
    res_a = mgr.apply_themes(ThemeSet(gtk_theme="ThemeWithGTK4"))
    assert res_a.gtk4_override_applied is True
    assert (config_dir / "gtk.css").exists()
    assert linker.is_override_active() is True

    # 2. Apply Theme B -> override removed
    res_b = mgr.apply_themes(ThemeSet(gtk_theme="ThemeWithoutGTK4"))
    assert res_b.gtk4_override_applied is False
    assert not (config_dir / "gtk.css").exists()
    assert linker.is_override_active() is False


def test_manager_apply_themes_sandbox_propagation_filtering(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_sandbox: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify that sandbox propagation occurs only if gtk_theme or icon_theme is present."""
    cursor_theme = Theme("Adwaita", ThemeType.CURSOR, tmp_path / "Adwaita", False)
    shell_theme = Theme("Nordic", ThemeType.SHELL, tmp_path / "Nordic", True)
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)

    mock_scanner.find_theme.side_effect = lambda name, t_type: {
        (ThemeType.CURSOR, "Adwaita"): cursor_theme,
        (ThemeType.SHELL, "Nordic"): shell_theme,
        (ThemeType.GTK, "Nordic"): gtk_theme,
    }.get((t_type, name))

    # 1. Cursor only -> sandbox not called
    res_cursor = manager.apply_themes(ThemeSet(cursor_theme="Adwaita"), propagate_sandbox=True)
    assert res_cursor.sandbox_propagation is None
    mock_sandbox.propagate_all.assert_not_called()

    # 2. Shell only -> sandbox not called
    res_shell = manager.apply_themes(ThemeSet(shell_theme="Nordic"), propagate_sandbox=True)
    assert res_shell.sandbox_propagation is None
    mock_sandbox.propagate_all.assert_not_called()

    # 3. GTK or Icon theme -> sandbox called
    manager.apply_themes(ThemeSet(gtk_theme="Nordic"), propagate_sandbox=True)
    mock_sandbox.propagate_all.assert_called_once_with(gtk_theme="Nordic", icon_theme=None)


def test_manager_apply_themes_sandbox_failure_produces_warnings(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_sandbox: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify that sandbox propagation error returns ApplyResult with warning without raising exceptions."""
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    mock_scanner.find_theme.return_value = gtk_theme

    mock_sandbox.propagate_all.return_value = PropagationResult(
        flatpak_success=False,
        snap_success=False,
        warnings=["Timeout durante l'esecuzione del comando Flatpak."],
    )

    result = manager.apply_themes(ThemeSet(gtk_theme="Nordic"), propagate_sandbox=True)

    assert result.gtk_theme == "Nordic"
    assert result.warnings == ["Timeout durante l'esecuzione del comando Flatpak."]
    assert result.sandbox_propagation is not None
    assert result.sandbox_propagation.flatpak_success is False


def test_manager_apply_themes_missing_theme_fallback_and_raises(
    manager: ThemeManager, mock_scanner: MagicMock
) -> None:
    """Verify that missing theme applies fallback or raises if use_fallback=False."""
    mock_scanner.find_theme.return_value = None

    # When use_fallback=True (default), does not raise exceptions but uses fallback with warning
    res = manager.apply_themes(ThemeSet(gtk_theme="NonExistent"))
    assert res.gtk_theme is not None
    assert any("fallback in use" in w for w in res.warnings)

    # When use_fallback=False, raises ThemeNotFoundError
    with pytest.raises(ThemeNotFoundError, match="GTK theme 'NonExistent' was not found"):
        manager.apply_themes(ThemeSet(gtk_theme="NonExistent"), use_fallback=False)


def test_manager_apply_themes_invalid_color_scheme(manager: ThemeManager) -> None:
    """Verify that unsupported color scheme raises ValueError."""
    with pytest.raises(ValueError, match="Invalid color scheme 'neon-dark'"):
        manager.apply_themes(ThemeSet(color_scheme="neon-dark"))


def test_manager_apply_themes_shell_unsupported_adds_warning(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_gsettings: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify that absence of Shell support adds a warning to ApplyResult."""
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
    """Verify that apply_gtk4_override=False disables GTK4 linker."""
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
    """Verify unified application for GTK and Shell."""
    gtk_theme = Theme("Nordic", ThemeType.GTK, tmp_path / "Nordic", True)
    shell_theme = Theme("Nordic", ThemeType.SHELL, tmp_path / "Nordic", True)

    mock_scanner.find_theme.side_effect = lambda name, t_type: (
        gtk_theme if t_type == ThemeType.GTK else shell_theme
    )

    result = manager.apply_unified_theme("Nordic", color_scheme="prefer-dark")
    assert result.gtk_theme == "Nordic"
    assert result.shell_theme == "Nordic"
    assert result.color_scheme == "prefer-dark"


def test_manager_apply_unified_theme_not_found(
    manager: ThemeManager, mock_scanner: MagicMock
) -> None:
    """Verify that non-existent unified theme raises ThemeNotFoundError."""
    mock_scanner.find_theme.return_value = None

    with pytest.raises(ThemeNotFoundError, match="was not found as GTK or GNOME Shell"):
        manager.apply_unified_theme("InexistentTheme")


# -----------------------------------------------------------------------------
# Presets and File Management Tests
# -----------------------------------------------------------------------------


def test_manager_preset_workflow(
    manager: ThemeManager,
    mock_presets: MagicMock,
    mock_gsettings: MagicMock,
    mock_scanner: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify complete workflow of saving, listing, applying, and deleting presets."""
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
    mock_scanner.find_theme.side_effect = lambda name, t_type: Theme(
        name, t_type, tmp_path / name, True
    )
    res = manager.apply_preset("MyPreset")
    assert res.gtk_theme == "Nordic"

    # Delete
    mock_presets.delete_preset.return_value = True
    assert manager.delete_preset("MyPreset") is True
    mock_presets.delete_preset.assert_called_once_with("MyPreset")


def test_manager_install_and_uninstall(
    manager: ThemeManager, mock_installer: MagicMock, tmp_path: Path
) -> None:
    """Verify delegation of install and uninstall methods to ThemeInstaller."""
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
        target_dir=None,
    )

    uninstalled = manager.uninstall_theme("Installed", ThemeType.GTK)
    assert uninstalled is True
    mock_installer.uninstall.assert_called_once_with(
        theme_name="Installed", theme_type=ThemeType.GTK
    )


def test_manager_inspect_theme_source(
    manager: ThemeManager, mock_installer: MagicMock, tmp_path: Path
) -> None:
    """Verify that inspect_theme_source delegates to ThemeInstaller.inspect_source."""
    source = tmp_path / "SomeSource"
    mock_installer.inspect_source.return_value = [("MyTheme", source, ThemeType.GTK)]

    results = manager.inspect_theme_source(source)
    assert results == [("MyTheme", ThemeType.GTK)]
    mock_installer.inspect_source.assert_called_once_with(source_path=source)


def test_manager_install_theme_directory(
    manager: ThemeManager, mock_installer: MagicMock, tmp_path: Path
) -> None:
    """Verify that install_theme_directory delegates to ThemeInstaller.install_directory."""
    source_dir = tmp_path / "MyDir"
    installed_theme = Theme("MyDir", ThemeType.GTK, tmp_path / "MyDir", True)
    mock_installer.install_directory.return_value = [installed_theme]

    res = manager.install_theme_directory(source_dir, overwrite=True)
    assert res == [installed_theme]
    mock_installer.install_directory.assert_called_once_with(
        directory_path=source_dir,
        theme_type=None,
        custom_name=None,
        overwrite=True,
        target_dir=None,
    )


def test_manager_install_theme_polymorphic(
    manager: ThemeManager, mock_installer: MagicMock, tmp_path: Path
) -> None:
    """Verify that install_theme accepts both archives and directories delegating to ThemeInstaller.install."""
    source = tmp_path / "generic_source"
    installed_theme = Theme("GenTheme", ThemeType.GTK, tmp_path / "GenTheme", True)
    mock_installer.install.return_value = [installed_theme]

    res = manager.install_theme(source, overwrite=False)
    assert res == [installed_theme]
    mock_installer.install.assert_called_once_with(
        archive_path=source,
        theme_type=None,
        custom_name=None,
        overwrite=False,
        target_dir=None,
    )


def test_manager_get_sandbox_status(manager: ThemeManager, mock_sandbox: MagicMock) -> None:
    """Verify that get_sandbox_status delegates to SandboxBridge.get_sandbox_status."""
    expected = SandboxStatus(snap_available=True, flatpak_available=True)
    mock_sandbox.get_sandbox_status.return_value = expected

    res = manager.get_sandbox_status()
    assert res == expected
    mock_sandbox.get_sandbox_status.assert_called_once()


def test_manager_propagate_sandbox_with_explicit_themes(
    manager: ThemeManager, mock_sandbox: MagicMock
) -> None:
    """Verify that propagate_sandbox delegates to SandboxBridge.propagate_all with specified themes."""
    expected = PropagationResult(flatpak_success=True, snap_success=True)
    mock_sandbox.propagate_all.return_value = expected

    res = manager.propagate_sandbox(gtk_theme="MyGTK", icon_theme="MyIcons")
    assert res == expected
    mock_sandbox.propagate_all.assert_called_once_with(gtk_theme="MyGTK", icon_theme="MyIcons")


def test_manager_propagate_sandbox_with_active_themes(
    manager: ThemeManager,
    mock_gsettings: MagicMock,
    mock_sandbox: MagicMock,
) -> None:
    """Verify that propagate_sandbox uses current themes if not specified."""
    mock_gsettings.get_current.return_value = ThemeSet(
        gtk_theme="ActiveGTK", icon_theme="ActiveIcons"
    )
    expected = PropagationResult(flatpak_success=True, snap_success=True)
    mock_sandbox.propagate_all.return_value = expected

    res = manager.propagate_sandbox()
    assert res == expected
    mock_sandbox.propagate_all.assert_called_once_with(
        gtk_theme="ActiveGTK", icon_theme="ActiveIcons"
    )


def test_manager_apply_themes_invalid_structure_raises(
    manager: ThemeManager,
    mock_scanner: MagicMock,
    mock_validator: MagicMock,
) -> None:
    """Verify that applying a theme with invalid structure raises ThemeValidationError."""
    from gnome_theme_manager.core.errors import ThemeValidationError

    mock_scanner.find_theme.return_value = Theme(
        name="BrokenTheme",
        theme_type=ThemeType.GTK,
        path=Path("/usr/share/themes/BrokenTheme"),
        is_user_level=False,
    )
    mock_validator.validate.return_value = MagicMock(
        valid=False,
        warnings=["No modern GTK stylesheet (gtk-3.0 or gtk-4.0) detected."],
        missing_files=["gtk-3.0/gtk.css or gtk-4.0/gtk.css"],
    )

    with pytest.raises(ThemeValidationError) as exc_info:
        manager.apply_themes(ThemeSet(gtk_theme="BrokenTheme"))

    assert "invalid" in str(exc_info.value).lower()
    assert "gtk" in str(exc_info.value).lower()
