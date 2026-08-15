# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per lo scanner del filesystem (ThemeScanner).

Verifica il corretto rilevamento di:
- Temi GTK (tramite cartelle gtk-X.0 o index.theme)
- Temi Icone (tramite cartelle risoluzioni/scalable o index.theme)
- Temi Cursori (tramite cartella cursors/)
- Temi GNOME Shell (tramite cartella gnome-shell/)
- Cartelle ibride (temi che contengono sia icone che cursori)
- Precedenze tra directory utente e di sistema (Utente > Sistema)
- Filtri come 'user_only' e ricerca mirata con 'find_theme'
"""

from pathlib import Path

import pytest

from gnome_theme_manager.core.models import ThemeType
from gnome_theme_manager.core.scanner import ThemeScanner


@pytest.fixture
def mock_filesystem_structure(tmp_path: Path):
    """Crea una gerarchia di directory e file temporanei simulando l'ambiente GNOME."""
    # 1. Directory Utente
    user_themes = tmp_path / "user" / "themes"
    user_icons = tmp_path / "user" / "icons"
    user_themes.mkdir(parents=True, exist_ok=True)
    user_icons.mkdir(parents=True, exist_ok=True)

    # Tema GTK + Shell Utente (es. "Nordic" con gtk-3.0 e gnome-shell/)
    nordic = user_themes / "Nordic"
    (nordic / "gtk-3.0").mkdir(parents=True, exist_ok=True)
    (nordic / "gtk-3.0" / "gtk.css").write_text("/* dummy */")
    (nordic / "gnome-shell").mkdir(parents=True, exist_ok=True)
    (nordic / "gnome-shell" / "gnome-shell.css").write_text("/* shell css */")

    # Tema Icone Utente (es. "Papirus-Dark" con index.theme)
    papirus_icon = user_icons / "Papirus-Dark"
    papirus_icon.mkdir(parents=True, exist_ok=True)
    (papirus_icon / "index.theme").write_text(
        "[Icon Theme]\nName=Papirus-Dark\nDirectories=48x48\n"
    )
    (papirus_icon / "48x48").mkdir(parents=True, exist_ok=True)

    # Tema Cursori Utente (es. "Capitaine" con cursors/)
    capitaine_cursor = user_icons / "Capitaine-Cursors"
    capitaine_cursor.mkdir(parents=True, exist_ok=True)
    (capitaine_cursor / "cursors").mkdir(parents=True, exist_ok=True)

    # 2. Directory di Sistema
    sys_themes = tmp_path / "sys" / "themes"
    sys_icons = tmp_path / "sys" / "icons"
    sys_themes.mkdir(parents=True, exist_ok=True)
    sys_icons.mkdir(parents=True, exist_ok=True)

    # Tema GTK Sistema (es. "Adwaita" con gtk-4.0)
    adwaita_gtk = sys_themes / "Adwaita" / "gtk-4.0"
    adwaita_gtk.mkdir(parents=True, exist_ok=True)

    # Tema GTK Sistema con lo stesso nome del tema Utente ("Nordic") per testare la precedenza
    nordic_sys = sys_themes / "Nordic"
    (nordic_sys / "gtk-3.0").mkdir(parents=True, exist_ok=True)
    (nordic_sys / "gnome-shell").mkdir(parents=True, exist_ok=True)

    # Tema Ibrido di Sistema (es. "Yaru" contenente sia icone che la cartella cursors/)
    yaru_hybrid = sys_icons / "Yaru"
    yaru_hybrid.mkdir(parents=True, exist_ok=True)
    (yaru_hybrid / "index.theme").write_text("[Icon Theme]\nName=Yaru\n")
    (yaru_hybrid / "scalable").mkdir(parents=True, exist_ok=True)
    (yaru_hybrid / "cursors").mkdir(parents=True, exist_ok=True)

    return {
        "user_themes": user_themes,
        "user_icons": user_icons,
        "sys_themes": sys_themes,
        "sys_icons": sys_icons,
    }


def test_scanner_initialization():
    """Verifica che ThemeScanner si istanzi correttamente con percorsi personalizzati o di default."""
    scanner = ThemeScanner()
    assert len(scanner.user_theme_dirs) >= 1
    assert len(scanner.system_theme_dirs) >= 1

    custom_dir = [Path("/custom/themes")]
    scanner_custom = ThemeScanner(user_theme_dirs=custom_dir)
    assert scanner_custom.user_theme_dirs == custom_dir


def test_scan_gtk_themes(mock_filesystem_structure):
    """Verifica la scansione dei temi GTK e la corretta applicazione della precedenza."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    gtk_themes = scanner.scan_gtk_themes()
    names = [t.name for t in gtk_themes]

    assert "Nordic" in names
    assert "Adwaita" in names

    nordic_theme = next(t for t in gtk_themes if t.name == "Nordic")
    assert nordic_theme.is_user_level is True
    assert nordic_theme.path == fs["user_themes"] / "Nordic"

    adwaita_theme = next(t for t in gtk_themes if t.name == "Adwaita")
    assert adwaita_theme.is_user_level is False


def test_scan_shell_themes(mock_filesystem_structure):
    """Verifica la scansione dei temi per la GNOME Shell."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    shell_themes = scanner.scan_shell_themes()
    names = [t.name for t in shell_themes]

    assert "Nordic" in names
    nordic_shell = next(t for t in shell_themes if t.name == "Nordic")
    assert nordic_shell.is_user_level is True
    assert nordic_shell.theme_type == ThemeType.SHELL


def test_scan_icon_and_cursor_themes(mock_filesystem_structure):
    """Verifica la scansione separata di icone e cursori, inclusa la gestione di cartelle ibride."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    # Scansione Icone
    icon_themes = scanner.scan_icon_themes()
    icon_names = [t.name for t in icon_themes]
    assert "Papirus-Dark" in icon_names
    assert "Yaru" in icon_names
    assert "Capitaine-Cursors" not in icon_names

    # Scansione Cursori
    cursor_themes = scanner.scan_cursor_themes()
    cursor_names = [t.name for t in cursor_themes]
    assert "Capitaine-Cursors" in cursor_names
    assert "Yaru" in cursor_names
    assert "Papirus-Dark" not in cursor_names


def test_scan_all(mock_filesystem_structure):
    """Verifica che scan_all restituisca l'insieme completo di tutti i temi (inclusi Shell)."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    all_themes = scanner.scan_all()
    # Ci aspettiamo: Nordic (GTK), Adwaita (GTK), Papirus-Dark (ICON), Yaru (ICON), Yaru (CURSOR), Capitaine (CURSOR), Nordic (SHELL)
    assert len(all_themes) == 7


def test_scan_user_only(mock_filesystem_structure):
    """Verifica che user_only=True escluda tutti i temi di sistema."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    user_all = scanner.scan_all(user_only=True)
    for theme in user_all:
        assert theme.is_user_level is True

    user_names = [t.name for t in user_all]
    assert "Nordic" in user_names
    assert "Papirus-Dark" in user_names
    assert "Capitaine-Cursors" in user_names
    assert "Adwaita" not in user_names
    assert "Yaru" not in user_names


def test_find_theme(mock_filesystem_structure):
    """Verifica la ricerca di un tema per nome e tipo."""
    fs = mock_filesystem_structure
    scanner = ThemeScanner(
        user_theme_dirs=[fs["user_themes"]],
        user_icon_dirs=[fs["user_icons"]],
        system_theme_dirs=[fs["sys_themes"]],
        system_icon_dirs=[fs["sys_icons"]],
    )

    # Tema GTK esistente
    gtk_theme = scanner.find_theme("Nordic", ThemeType.GTK)
    assert gtk_theme is not None
    assert gtk_theme.name == "Nordic"
    assert gtk_theme.theme_type == ThemeType.GTK

    # Tema Shell esistente
    shell_theme = scanner.find_theme("Nordic", ThemeType.SHELL)
    assert shell_theme is not None
    assert shell_theme.name == "Nordic"
    assert shell_theme.theme_type == ThemeType.SHELL

    # Tema cercato con tipo errato -> deve restituire None
    wrong_type = scanner.find_theme("Capitaine-Cursors", ThemeType.GTK)
    assert wrong_type is None

    # Tema inesistente -> deve restituire None
    non_existent = scanner.find_theme("Fantasma", ThemeType.GTK)
    assert non_existent is None


def test_scanner_nonexistent_directory(tmp_path: Path):
    """Verifica che directory inesistenti vengano gestite senza sollevare eccezioni."""
    non_existent = tmp_path / "does_not_exist"
    scanner = ThemeScanner(
        user_theme_dirs=[non_existent],
        user_icon_dirs=[non_existent],
        system_theme_dirs=[non_existent],
        system_icon_dirs=[non_existent],
    )

    assert scanner.scan_all() == []
    assert scanner.scan_gtk_themes() == []
    assert scanner.scan_icon_themes() == []
    assert scanner.scan_cursor_themes() == []
    assert scanner.scan_shell_themes() == []


def test_dynamic_xdg_paths_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifica che le variabili d'ambiente XDG_DATA_HOME e XDG_DATA_DIRS vengano considerate dinamicamente."""
    custom_xdg_home = tmp_path / "custom_data_home"
    custom_xdg_dirs = f"{tmp_path}/custom_sys1:{tmp_path}/custom_sys2"

    monkeypatch.setenv("XDG_DATA_HOME", str(custom_xdg_home))
    monkeypatch.setenv("XDG_DATA_DIRS", custom_xdg_dirs)

    scanner = ThemeScanner()

    # Verifica user themes
    assert custom_xdg_home / "themes" in scanner.user_theme_dirs
    assert Path.home() / ".themes" in scanner.user_theme_dirs

    # Verifica user icons
    assert custom_xdg_home / "icons" in scanner.user_icon_dirs
    assert Path.home() / ".icons" in scanner.user_icon_dirs

    # Verifica system themes
    assert tmp_path / "custom_sys1" / "themes" in scanner.system_theme_dirs
    assert tmp_path / "custom_sys2" / "themes" in scanner.system_theme_dirs
    assert Path("/usr/share/themes") in scanner.system_theme_dirs

    # Verifica system icons
    assert tmp_path / "custom_sys1" / "icons" in scanner.system_icon_dirs
    assert tmp_path / "custom_sys2" / "icons" in scanner.system_icon_dirs
    assert Path("/usr/share/icons") in scanner.system_icon_dirs


def test_scanner_invalid_index_theme(tmp_path: Path):
    """Verifica che temi con index.theme corrotto/assente siano marcati come invalid ma non crashino lo scanner."""
    user_themes = tmp_path / "themes"
    user_themes.mkdir()

    # 1. Tema con index.theme corrotto (non parsabile come INI)
    bad_theme = user_themes / "CorruptedTheme"
    bad_theme.mkdir()
    (bad_theme / "index.theme").write_text("corrupted content without sections or key-value pairs")

    scanner = ThemeScanner(
        user_theme_dirs=[user_themes], user_icon_dirs=[], system_theme_dirs=[], system_icon_dirs=[]
    )
    themes = scanner.scan_gtk_themes()
    assert len(themes) == 1
    assert themes[0].name == "CorruptedTheme"
    assert themes[0].invalid is True


def test_scanner_inheritance_chain(tmp_path: Path):
    """Verifica la risoluzione ricorsiva dell'inheritance chain da index.theme fino a max depth 5."""
    user_themes = tmp_path / "themes"
    user_themes.mkdir()

    # Creiamo 6 temi in catena: Theme5 -> Theme4 -> Theme3 -> Theme2 -> Theme1 -> Theme0
    for i in range(6):
        theme_dir = user_themes / f"Theme{i}"
        theme_dir.mkdir()
        inherits = f"Theme{i - 1}" if i > 0 else ""
        (theme_dir / "index.theme").write_text(
            f"[Desktop Entry]\nName=Theme{i}\nInherits={inherits}\n"
        )

    scanner = ThemeScanner(
        user_theme_dirs=[user_themes], user_icon_dirs=[], system_theme_dirs=[], system_icon_dirs=[]
    )

    # Per Theme5 (depth 5), la catena deve fermarsi a Theme1 (Theme5, 4, 3, 2, 1) ed escludere Theme0
    theme5 = scanner.find_theme("Theme5", ThemeType.GTK)
    assert theme5 is not None
    assert "Theme4" in theme5.inheritance_chain
    assert "Theme1" in theme5.inheritance_chain
    assert "Theme0" not in theme5.inheritance_chain
