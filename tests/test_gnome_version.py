"""Tests for GNOME version detection and GNOME 50+ theme structure support."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.gnome_version import (
    _parse_version_string,
    detect_gnome_version,
    detect_gnome_version_string,
    get_required_theme_structure,
    is_gnome_50_plus,
)
from gnome_theme_manager.core.gtk4_linker import GTK4ThemeLinker
from gnome_theme_manager.core.installer import detect_theme_types
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import ThemeType
from gnome_theme_manager.core.scanner import ThemeScanner
from gnome_theme_manager.core.theme_validator import ThemeValidator


def test_detect_gnome_version_env_override() -> None:
    """Check that GNOME_VERSION environment variable correctly overrides detection."""
    with patch.dict("os.environ", {"GNOME_VERSION": "50.1"}):
        ver = detect_gnome_version()
        assert ver == (50, 1)
        assert detect_gnome_version_string() == "50.1"
        assert is_gnome_50_plus() is True

    with patch.dict("os.environ", {"GNOME_VERSION": "50.alpha"}):
        ver = detect_gnome_version()
        assert ver == (50, 0)
        assert is_gnome_50_plus() is True

    with patch.dict("os.environ", {"GNOME_VERSION": "46.0"}):
        ver = detect_gnome_version()
        assert ver == (46, 0)
        assert is_gnome_50_plus() is False


def test_detect_gnome_version_subprocess() -> None:
    """Check version detection via gnome-shell --version command."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "GNOME Shell 50.beta"

    with patch.dict("os.environ", {"GNOME_VERSION": ""}):
        with patch("gi.repository.Gio.bus_get_sync", side_effect=Exception("No DBus")):
            with patch("subprocess.run", return_value=mock_run):
                ver = detect_gnome_version()
                assert ver == (50, 0)


def test_detect_gnome_version_xml_fallback() -> None:
    """Check version detection via gnome-version.xml fallback."""
    from unittest.mock import mock_open

    xml_content = "<gnome-version><platform>50</platform><minor>2</minor></gnome-version>"

    with patch.dict("os.environ", {"GNOME_VERSION": ""}):
        with patch("gi.repository.Gio.bus_get_sync", side_effect=Exception("No DBus")):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch(
                    "os.path.isfile",
                    side_effect=lambda p: str(p) == "/usr/share/gnome/gnome-version.xml",
                ):
                    with patch("builtins.open", mock_open(read_data=xml_content)):
                        ver = detect_gnome_version()
                        assert ver == (50, 2)


def test_detect_gnome_version_undetectable() -> None:
    """Check undetectable GNOME version returns None, unknown, and False."""
    with patch.dict("os.environ", {"GNOME_VERSION": ""}):
        with patch("gi.repository.Gio.bus_get_sync", side_effect=Exception("No DBus")):
            with patch("subprocess.run", side_effect=Exception("Not found")):
                with patch("os.path.isfile", return_value=False):
                    assert detect_gnome_version() is None
                    assert detect_gnome_version_string() == "unknown"
                    assert is_gnome_50_plus() is False


def test_parse_version_string_edge_cases() -> None:
    """Check parser with strange strings."""
    assert _parse_version_string("invalid") is None
    assert _parse_version_string("") is None
    assert _parse_version_string("GNOME 46") == (46, 0)
    assert _parse_version_string("50.rc1") == (50, 0)


def test_get_required_theme_structure() -> None:
    """Verify theme requirements for GNOME 50+, 42-49, and legacy GNOME."""
    struct_50 = get_required_theme_structure((50, 0))
    assert struct_50["is_gnome_50_plus"] is True
    assert "gtk-4.0/libadwaita.css" in struct_50["required_libadwaita_files"]
    assert "gtk-4.0" in struct_50["required_gtk_directories"]

    struct_46 = get_required_theme_structure((46, 0))
    assert struct_46["is_gnome_50_plus"] is False
    assert "gtk-4.0" in struct_46["required_gtk_directories"]

    struct_legacy = get_required_theme_structure((40, 0))
    assert struct_legacy["is_gnome_50_plus"] is False
    assert "gtk-3.0" in struct_legacy["required_gtk_directories"]

    # Test default detection
    with patch.dict("os.environ", {"GNOME_VERSION": "50.0"}):
        res = get_required_theme_structure(None)
        assert res["is_gnome_50_plus"] is True


def test_detect_theme_types_libadwaita_folder(tmp_path: Path) -> None:
    """Verify detect_theme_types recognizes themes structured with libadwaita/."""
    theme_dir = tmp_path / "ModernAdwaita"
    (theme_dir / "libadwaita").mkdir(parents=True)
    (theme_dir / "libadwaita" / "gtk.css").write_text("/* libadwaita */")

    types = detect_theme_types(theme_dir)
    assert ThemeType.GTK in types


def test_detect_theme_types_libadwaita_css_root(tmp_path: Path) -> None:
    """Verify detect_theme_types recognizes root libadwaita.css."""
    theme_dir = tmp_path / "LibadwaitaTheme"
    theme_dir.mkdir()
    (theme_dir / "libadwaita.css").write_text("/* root libadwaita */")

    types = detect_theme_types(theme_dir)
    assert ThemeType.GTK in types


def test_scanner_recognizes_libadwaita_theme(tmp_path: Path) -> None:
    """Verify ThemeScanner discovers themes containing libadwaita stylesheets."""
    theme_dir = tmp_path / "AdwaitaDarkMod"
    (theme_dir / "gtk-4.0").mkdir(parents=True)
    (theme_dir / "gtk-4.0" / "libadwaita.css").write_text("/* libadwaita css */")

    scanner = ThemeScanner(user_theme_dirs=[tmp_path], system_theme_dirs=[])
    themes = scanner.scan_gtk_themes()
    names = [t.name for t in themes]
    assert "AdwaitaDarkMod" in names


def test_theme_validator_gnome_50_warning(tmp_path: Path) -> None:
    """Verify ThemeValidator warns when running on GNOME 50+ and theme lacks libadwaita."""
    theme_dir = tmp_path / "GTK3OnlyTheme"
    (theme_dir / "gtk-3.0").mkdir(parents=True)
    (theme_dir / "gtk-3.0" / "gtk.css").write_text("/* gtk3 */")
    (theme_dir / "index.theme").write_text("[Desktop Entry]\nType=X-GNOME-Metatheme\n")

    validator = ThemeValidator()

    with patch.dict("os.environ", {"GNOME_VERSION": "50.0"}):
        result = validator.validate(theme_dir, ThemeType.GTK)
        assert result.valid is True
        assert any("GNOME 50+ detected" in w for w in result.warnings)


def test_theme_validator_gnome_50_has_gtk4_but_no_libadwaita_warning(tmp_path: Path) -> None:
    """Verify ThemeValidator warns when GTK4 exists but dedicated libadwaita.css is absent on GNOME 50+."""
    theme_dir = tmp_path / "GTK4OnlyTheme"
    (theme_dir / "gtk-4.0").mkdir(parents=True)
    (theme_dir / "gtk-4.0" / "gtk.css").write_text("/* gtk4 */")
    (theme_dir / "index.theme").write_text("[Desktop Entry]\nType=X-GNOME-Metatheme\n")

    validator = ThemeValidator()

    with patch.dict("os.environ", {"GNOME_VERSION": "50.0"}):
        result = validator.validate(theme_dir, ThemeType.GTK)
        assert result.valid is True
        assert any("lacks dedicated libadwaita.css" in w for w in result.warnings)


def test_gtk4_linker_links_libadwaita_css(tmp_path: Path) -> None:
    """Verify GTK4ThemeLinker links libadwaita.css into ~/.config/gtk-4.0/."""
    theme_dir = tmp_path / "AdwaitaNext"
    gtk4_dir = theme_dir / "gtk-4.0"
    gtk4_dir.mkdir(parents=True)
    (gtk4_dir / "gtk.css").write_text("/* gtk4 */")
    (gtk4_dir / "libadwaita.css").write_text("/* libadwaita */")

    config_dest = tmp_path / "config_gtk4"
    linker = GTK4ThemeLinker(config_dir=config_dest)

    success = linker.apply_override(theme_dir)
    assert success is True
    assert (config_dest / "gtk.css").is_symlink()
    assert (config_dest / "libadwaita.css").is_symlink()
    assert (config_dest / "libadwaita.css").resolve() == (gtk4_dir / "libadwaita.css").resolve()

    linker.remove_override()
    assert not (config_dest / "libadwaita.css").exists()


def test_theme_manager_gnome_version_integration(tmp_path: Path) -> None:
    """Verify ThemeManager exposes GNOME version detection methods and status."""
    manager = ThemeManager(
        scanner=MagicMock(),
        gsettings=MagicMock(),
        gtk4_linker=MagicMock(),
        installer=MagicMock(),
        presets=MagicMock(),
        sandbox_bridge=MagicMock(),
        validator=MagicMock(),
        extensions=MagicMock(),
    )

    with patch.dict("os.environ", {"GNOME_VERSION": "50.2"}):
        assert manager.get_gnome_version() == (50, 2)
        assert manager.get_gnome_version_string() == "50.2"
        assert manager.is_gnome_50_plus() is True
        struct = manager.get_required_theme_structure()
        assert struct["is_gnome_50_plus"] is True

        status = manager.get_system_status()
        assert status.gnome_version == "50.2"
        assert status.is_gnome_50_plus is True


def test_installer_symlinks_libadwaita_into_gtk4(tmp_path: Path) -> None:
    """Verify ThemeInstaller automatically creates gtk-4.0/ symlinks for Libadwaita stylesheets."""
    from gnome_theme_manager.core.installer import ThemeInstaller

    src_theme = tmp_path / "SourceTheme"
    src_theme.mkdir()
    (src_theme / "libadwaita.css").write_text("/* libadwaita */")
    (src_theme / "libadwaita-dark.css").write_text("/* libadwaita dark */")

    user_themes = tmp_path / "installed_themes"
    installer = ThemeInstaller(user_themes_dir=user_themes)

    with patch.dict("os.environ", {"GNOME_VERSION": "50.0"}):
        installed = installer.install_directory(src_theme)
        assert len(installed) >= 1
        dest = installed[0].path
        assert (dest / "gtk-4.0").is_dir()
        assert (dest / "gtk-4.0" / "libadwaita.css").is_symlink()
        assert (dest / "gtk-4.0" / "libadwaita-dark.css").is_symlink()
        assert (dest / "gtk-4.0" / "gtk.css").is_symlink()


def test_installer_symlinks_libadwaita_from_gtk4_css_on_gnome_50(tmp_path: Path) -> None:
    """Verify ThemeInstaller links libadwaita.css to gtk.css on GNOME 50+ if only gtk.css exists."""
    from gnome_theme_manager.core.installer import ThemeInstaller

    src_theme = tmp_path / "GTK4Theme"
    (src_theme / "gtk-4.0").mkdir(parents=True)
    (src_theme / "gtk-4.0" / "gtk.css").write_text("/* gtk4 */")

    user_themes = tmp_path / "installed_themes"
    installer = ThemeInstaller(user_themes_dir=user_themes)

    with patch.dict("os.environ", {"GNOME_VERSION": "50.0"}):
        installed = installer.install_directory(src_theme)
        dest = installed[0].path
        assert (dest / "gtk-4.0" / "libadwaita.css").is_symlink()
        assert (dest / "gtk-4.0" / "libadwaita.css").resolve() == (dest / "gtk-4.0" / "gtk.css").resolve()


def test_gtk4_linker_links_libadwaita_dark_css(tmp_path: Path) -> None:
    """Verify GTK4ThemeLinker symlinks libadwaita-dark.css into config directory."""
    theme_dir = tmp_path / "DarkAdwTheme"
    gtk4_dir = theme_dir / "gtk-4.0"
    gtk4_dir.mkdir(parents=True)
    (gtk4_dir / "gtk.css").write_text("/* gtk */")
    (gtk4_dir / "libadwaita-dark.css").write_text("/* libadw dark */")

    config_dest = tmp_path / "config_gtk4"
    linker = GTK4ThemeLinker(config_dir=config_dest)

    success = linker.apply_override(theme_dir)
    assert success is True
    assert (config_dest / "libadwaita-dark.css").is_symlink()
    assert (config_dest / "libadwaita-dark.css").resolve() == (gtk4_dir / "libadwaita-dark.css").resolve()

