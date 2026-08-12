"""Test di base per i modelli e i percorsi costanti."""

from pathlib import Path
from gnome_theme_manager.core.constants import (
    USER_THEMES_DIRS,
    USER_ICONS_DIRS,
    SYSTEM_THEMES_DIRS,
    SYSTEM_ICONS_DIRS,
    GSETTINGS_SCHEMA_INTERFACE,
)
from gnome_theme_manager.core.models import Theme, ThemeSet, ThemeType


def test_constants_defined():
    """Verifica che tutte le costanti di base siano definite correttamente."""
    assert len(USER_THEMES_DIRS) >= 2
    assert len(USER_ICONS_DIRS) >= 2
    assert len(SYSTEM_THEMES_DIRS) >= 1
    assert len(SYSTEM_ICONS_DIRS) >= 1
    assert GSETTINGS_SCHEMA_INTERFACE == "org.gnome.desktop.interface"


def test_theme_model(tmp_path: Path):
    """Verifica le proprietà della dataclass Theme."""
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


def test_theme_set_as_dict():
    """Verifica la serializzazione di ThemeSet in dizionario."""
    theme_set = ThemeSet(
        gtk_theme="Adwaita-dark",
        icon_theme="Papirus",
        cursor_theme="Yaru",
        color_scheme="prefer-dark",
    )

    data = theme_set.as_dict()
    assert data["gtk_theme"] == "Adwaita-dark"
    assert data["icon_theme"] == "Papirus"
    assert data["cursor_theme"] == "Yaru"
    assert data["color_scheme"] == "prefer-dark"
