"""Test di base per i modelli e i percorsi costanti."""

from pathlib import Path
from gnome_theme_manager.core.constants import (
    GSETTINGS_SCHEMA_INTERFACE,
    GSETTINGS_SCHEMA_USER_THEME,
    GTK4_CONFIG_DIR,
    SYSTEM_ICONS_DIRS,
    SYSTEM_THEMES_DIRS,
    USER_ICONS_DIRS,
    USER_THEMES_DIRS,
)
from gnome_theme_manager.core.models import Theme, ThemeSet, ThemeType


def test_constants_defined():
    """Verifica che tutte le costanti di base siano definite correttamente."""
    assert len(USER_THEMES_DIRS) >= 2
    assert len(USER_ICONS_DIRS) >= 2
    assert len(SYSTEM_THEMES_DIRS) >= 1
    assert len(SYSTEM_ICONS_DIRS) >= 1
    assert GSETTINGS_SCHEMA_INTERFACE == "org.gnome.desktop.interface"
    assert GSETTINGS_SCHEMA_USER_THEME == "org.gnome.shell.extensions.user-theme"
    assert GTK4_CONFIG_DIR == Path.home() / ".config" / "gtk-4.0"


def test_theme_model(tmp_path: Path):
    """Verifica le proprietà della dataclass Theme con vari tipi di tema."""
    theme_path = tmp_path / "TestTheme"
    theme_path.mkdir()

    theme = Theme(
        name="TestTheme",
        theme_type=ThemeType.GTK,
        path=theme_path,
        is_user_level=True,
    )

    assert theme.name == "TestTheme"
    assert theme.theme_type == ThemeType.GTK
    assert theme.is_user_level is True
    assert theme.exists is True

    shell_theme = Theme(
        name="TestTheme",
        theme_type=ThemeType.SHELL,
        path=theme_path,
        is_user_level=False,
    )
    assert shell_theme.theme_type == ThemeType.SHELL
    assert str(ThemeType.SHELL) == "shell"


def test_theme_set_as_dict():
    """Verifica la serializzazione di ThemeSet in dizionario incluso shell_theme."""
    theme_set = ThemeSet(
        gtk_theme="Adwaita-dark",
        icon_theme="Papirus",
        cursor_theme="Yaru",
        color_scheme="prefer-dark",
        shell_theme="Nordic",
    )

    data = theme_set.as_dict()
    assert data["gtk_theme"] == "Adwaita-dark"
    assert data["icon_theme"] == "Papirus"
    assert data["cursor_theme"] == "Yaru"
    assert data["color_scheme"] == "prefer-dark"
    assert data["shell_theme"] == "Nordic"
