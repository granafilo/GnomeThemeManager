# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Fallback Themes and Availability Checking (Task 3.1)."""

from pathlib import Path
from unittest.mock import MagicMock

from gnome_theme_manager.core.fallback import (
    FallbackConfig,
    FallbackManager,
    ThemeAvailabilityChecker,
)
from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.models import (
    Theme,
    ThemeSet,
    ThemeType,
)

# -----------------------------------------------------------------------------
# Tests for ThemeAvailabilityChecker and FallbackManager
# -----------------------------------------------------------------------------


def test_theme_availability_checker_host(tmp_path: Path) -> None:
    """Verifica che ThemeAvailabilityChecker rilevi la presenza su host per ciascun tipo di tema."""
    user_themes = tmp_path / "user_themes"
    user_themes.mkdir(parents=True)
    theme_dir = user_themes / "Nordic"
    theme_dir.mkdir()
    (theme_dir / "gtk-3.0").mkdir()

    scanner = MagicMock()
    scanner.find_theme.side_effect = lambda name, t_type: (
        Theme(name=name, theme_type=t_type, path=theme_dir, is_user_level=True)
        if name == "Nordic"
        else None
    )

    checker = ThemeAvailabilityChecker(scanner=scanner)
    assert checker.check("Nordic", ThemeType.GTK, target="host") is True
    assert checker.check("NonExistent", ThemeType.GTK, target="host") is False


def test_theme_availability_checker_snap_and_flatpak(tmp_path: Path) -> None:
    """Verifica il check disponibilità per target snap e flatpak."""
    scanner = MagicMock()
    checker = ThemeAvailabilityChecker(scanner=scanner)

    # Snap: i temi in KNOWN_SNAP_COMMON_THEMES (es. yaru, adwaita) sono disponibili
    assert checker.check("Yaru", ThemeType.GTK, target="snap") is True
    assert checker.check("Adwaita", ThemeType.GTK, target="snap") is True
    assert checker.check("CustomExoticTheme", ThemeType.GTK, target="snap") is False

    # Flatpak: i temi presenti sul filesystem host (accessibili via override filesystem) sono disponibili se trovati
    (tmp_path / "Nordic").mkdir(parents=True, exist_ok=True)
    scanner.find_theme.side_effect = lambda name, t_type: (
        Theme(name=name, theme_type=t_type, path=tmp_path / name, is_user_level=True)
        if name == "Nordic"
        else None
    )
    assert checker.check("Nordic", ThemeType.GTK, target="flatpak") is True
    assert checker.check("NonExistent", ThemeType.GTK, target="flatpak") is False


def test_theme_availability_checker_check_all_targets(tmp_path: Path) -> None:
    """Verifica che check_all_targets ritorni True solo se il tema è disponibile su tutti i target (host, snap, flatpak)."""
    scanner = MagicMock()
    checker = ThemeAvailabilityChecker(scanner=scanner)

    # Yaru esiste su host e snap e flatpak
    (tmp_path / "Yaru").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Nordic").mkdir(parents=True, exist_ok=True)
    scanner.find_theme.side_effect = lambda name, t_type: (
        Theme(name=name, theme_type=t_type, path=tmp_path / name, is_user_level=False)
        if name in ("Yaru", "Nordic")
        else None
    )

    assert checker.check_all_targets("Yaru", ThemeType.GTK) is True
    # Nordic non è in snap known common themes
    assert checker.check_all_targets("Nordic", ThemeType.GTK) is False


def test_fallback_config_roundtrip(tmp_path: Path) -> None:
    """Verifica salvataggio e caricamento della configurazione fallbacks.json."""
    config_file = tmp_path / "fallbacks.json"
    fm = FallbackManager(config_file=config_file)

    default_cfg = fm.get_config()
    assert default_cfg.gtk3 is not None
    assert default_cfg.gtk4 is not None

    custom_cfg = FallbackConfig(
        gtk3="Adwaita",
        gtk4="Adwaita",
        shell="Adwaita",
        icons="Adwaita",
        cursors="Adwaita",
    )
    fm.save_config(custom_cfg)

    loaded_cfg = fm.get_config()
    assert loaded_cfg.gtk3 == "Adwaita"
    assert loaded_cfg.icons == "Adwaita"
    assert loaded_cfg.cursors == "Adwaita"
    assert loaded_cfg.shell == "Adwaita"


def test_fallback_manager_first_run_defaults(tmp_path: Path) -> None:
    """Verifica che al primo avvio (file inesistente), FallbackManager rilevi i default dai temi di sistema."""
    config_file = tmp_path / "fallbacks.json"
    gsettings_mock = MagicMock()
    gsettings_mock.get_current.return_value = ThemeSet(
        gtk_theme="Yaru",
        icon_theme="Yaru",
        cursor_theme="Yaru",
        shell_theme="Yaru",
    )

    fm = FallbackManager(config_file=config_file, gsettings_client=gsettings_mock)
    cfg = fm.get_config()
    assert cfg.gtk3 == "Yaru"
    assert cfg.gtk4 == "Yaru"
    assert cfg.icons == "Yaru"
    assert cfg.cursors == "Yaru"
    assert cfg.shell == "Yaru"


# -----------------------------------------------------------------------------
# Manager apply with fallback tests (Task 3.1 core requirements)
# -----------------------------------------------------------------------------


def test_manager_apply_missing_theme_uses_fallback(tmp_path: Path) -> None:
    """Verifica che se un tema non è presente sul filesystem per un target o in generale,
    venga applicato il fallback configurato dell'utente senza sollevare alert bloccanti
    e restituendo un info banner/warning 'fallback in use'.
    """
    scanner = MagicMock()
    # "MissingTheme" non esiste sul filesystem; "Adwaita" è il fallback ed esiste
    fallback_gtk = Theme(
        name="Adwaita",
        theme_type=ThemeType.GTK,
        path=tmp_path / "Adwaita",
        is_user_level=False,
    )
    scanner.find_theme.side_effect = lambda name, t_type: (
        fallback_gtk if name == "Adwaita" else None
    )

    gsettings = MagicMock()
    gsettings.is_shell_theme_supported = True
    gsettings.get_current.return_value = ThemeSet()

    gtk4_linker = MagicMock()
    installer = MagicMock()
    presets = MagicMock()
    sandbox = MagicMock()
    validator = MagicMock()
    validator.validate.return_value = MagicMock(valid=True, warnings=[])

    config_file = tmp_path / "fallbacks.json"
    fallback_mgr = FallbackManager(config_file=config_file)
    fallback_mgr.save_config(
        FallbackConfig(
            gtk3="Adwaita",
            gtk4="Adwaita",
            shell="Adwaita",
            icons="Adwaita",
            cursors="Adwaita",
        )
    )

    mgr = ThemeManager(
        scanner=scanner,
        gsettings=gsettings,
        gtk4_linker=gtk4_linker,
        installer=installer,
        presets=presets,
        sandbox_bridge=sandbox,
        validator=validator,
        fallback_manager=fallback_mgr,
    )

    # Applicazione di un tema inesistente
    result = mgr.apply_themes(ThemeSet(gtk_theme="MissingTheme"))

    assert result.gtk_theme == "Adwaita"
    assert any("fallback in use" in w.lower() or "fallback" in w.lower() for w in result.warnings)
    gsettings.apply.assert_called_once()
    applied_set = gsettings.apply.call_args[0][0]
    assert applied_set.gtk_theme == "Adwaita"


def test_manager_get_available_fallback_options(tmp_path: Path) -> None:
    """Verifica che la lista delle opzioni fallback listi SOLO i temi disponibili su tutti i target."""
    scanner = MagicMock()
    # Scanner trova Yaru (universalmente disponibile) e CustomTheme (solo host)
    theme_yaru_gtk = Theme("Yaru", ThemeType.GTK, tmp_path / "Yaru", False)
    theme_custom_gtk = Theme("CustomTheme", ThemeType.GTK, tmp_path / "CustomTheme", True)
    theme_yaru_icon = Theme("Yaru", ThemeType.ICON, tmp_path / "Yaru", False)

    scanner.scan_gtk_themes.return_value = [theme_yaru_gtk, theme_custom_gtk]
    scanner.scan_icon_themes.return_value = [theme_yaru_icon]
    scanner.scan_cursor_themes.return_value = [theme_yaru_icon]
    scanner.scan_shell_themes.return_value = [theme_yaru_gtk]
    scanner.find_theme.side_effect = lambda name, t_type: {
        ("Yaru", ThemeType.GTK): theme_yaru_gtk,
        ("CustomTheme", ThemeType.GTK): theme_custom_gtk,
        ("Yaru", ThemeType.ICON): theme_yaru_icon,
        ("Yaru", ThemeType.CURSOR): theme_yaru_icon,
        ("Yaru", ThemeType.SHELL): theme_yaru_gtk,
    }.get((name, t_type))

    fm = FallbackManager(config_file=tmp_path / "fallbacks.json", scanner=scanner)
    opts = fm.get_available_fallback_themes(ThemeType.GTK)

    # Yaru deve essere presente, CustomTheme (non presente su snap) non deve essere tra le opzioni fallback universali
    assert "Yaru" in opts
    assert "CustomTheme" not in opts


def test_derive_available_theme_dynamic_discovery(tmp_path: Path) -> None:
    """Verifica che derive_available_theme scopra dinamicamente temi alternativi disponibili."""
    scanner = MagicMock()
    theme_yaru_dark = Theme("Yaru-dark", ThemeType.GTK, tmp_path / "Yaru-dark", False)
    scanner.scan_all.return_value = [theme_yaru_dark]
    scanner.find_theme.side_effect = lambda name, t_type: (
        theme_yaru_dark if name == "Yaru-dark" else None
    )

    checker = ThemeAvailabilityChecker(scanner=scanner)
    # Tema custom sconosciuto scuro deve risolvere verso Yaru-dark
    derived = checker.derive_available_theme(
        "NonExistent-Dark-Custom", ThemeType.GTK, target="snap"
    )
    assert derived == "Yaru-dark"


def test_fallback_manager_dynamic_resolution_missing_configured(tmp_path: Path) -> None:
    """Verifica che FallbackManager risolva verso un tema valido se il configurato non esiste sul disco."""
    scanner = MagicMock()
    theme_system = Theme("SystemDefault", ThemeType.GTK, tmp_path / "SystemDefault", False)
    scanner.find_theme.return_value = None
    scanner.scan_gtk_themes.return_value = [theme_system]
    scanner._scan_themes_by_type.return_value = [theme_system]

    fm = FallbackManager(config_file=tmp_path / "fallbacks.json", scanner=scanner)
    resolved = fm.resolve_fallback_for_component(ThemeType.GTK)
    assert resolved == "SystemDefault"
