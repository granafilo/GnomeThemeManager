# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per il wrapper GSettingsClient.

Verifica l'interazione con Gio.Settings simulando (mocking):
- Lettura dei temi correnti (incluso il tema GNOME Shell)
- Applicazione in blocco o singola dei temi (apply, set_gtk_theme, set_shell_theme, ecc.)
- Rilevamento dello schema colori GNOME 42+ (color-scheme)
- Gestione degli errori quando PyGObject o gli schemi GSettings non sono disponibili
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.errors import GSettingsUnavailableError
from gnome_theme_manager.core.gsettings import GSettingsClient
from gnome_theme_manager.core.models import ThemeSet


class MockGioSettings:
    """Mock per simulare l'oggetto Gio.Settings di PyGObject."""

    def __init__(
        self,
        schema_id: str = "org.gnome.desktop.interface",
        initial_values: dict[str, str] | None = None,
    ) -> None:
        self.schema_id = schema_id
        self.values = initial_values or {
            "gtk-theme": "Adwaita",
            "icon-theme": "Adwaita",
            "cursor-theme": "Adwaita",
            "color-scheme": "default",
            "name": "Adwaita",
        }

    def get_string(self, key: str) -> str:
        return str(self.values.get(key, ""))

    def set_string(self, key: str, value: str) -> bool:
        self.values[key] = value
        return True

    def get_double(self, key: str) -> float:
        return float(self.values.get(key, 1.0))

    def set_double(self, key: str, value: float) -> bool:
        self.values[key] = value
        return True

    def list_keys(self) -> list[str]:
        return list(self.values.keys())


@pytest.fixture
def mock_gio_environment():
    """Fixture che fornisce un ambiente PyGObject / Gio simulato con successo."""
    mock_settings = MockGioSettings("org.gnome.desktop.interface")
    mock_shell_settings = MockGioSettings(
        "org.gnome.shell.extensions.user-theme", {"name": "Adwaita"}
    )

    mock_schema_source = MagicMock()

    schema_interface = MagicMock()
    schema_interface.get_id.return_value = "org.gnome.desktop.interface"

    schema_shell = MagicMock()
    schema_shell.get_id.return_value = "org.gnome.shell.extensions.user-theme"

    def lookup_side_effect(schema_name: str, recursive: bool):
        if schema_name == "org.gnome.shell.extensions.user-theme":
            return schema_shell
        if schema_name == "org.gnome.desktop.interface":
            return schema_interface
        return None

    mock_schema_source.lookup.side_effect = lookup_side_effect

    with (
        patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", True),
        patch("gnome_theme_manager.core.gsettings.Gio") as mock_gio,
    ):
        mock_gio.SettingsSchemaSource.get_default.return_value = mock_schema_source

        def settings_new_full(schema, backend, path):
            if (
                schema == schema_shell
                or getattr(schema, "get_id", lambda: "")()
                == "org.gnome.shell.extensions.user-theme"
            ):
                return mock_shell_settings
            return mock_settings

        mock_gio.Settings.new_full.side_effect = settings_new_full
        mock_gio.Settings.new.side_effect = lambda s: (
            mock_shell_settings if s == "org.gnome.shell.extensions.user-theme" else mock_settings
        )

        yield {
            "interface_settings": mock_settings,
            "shell_settings": mock_shell_settings,
        }


def test_gsettings_get_current(mock_gio_environment):
    """Verifica la corretta lettura dei temi attivi da GSettings incluso Shell."""
    client = GSettingsClient()
    current = client.get_current()

    assert isinstance(current, ThemeSet)
    assert current.gtk_theme == "Adwaita"
    assert current.icon_theme == "Adwaita"
    assert current.cursor_theme == "Adwaita"
    assert current.color_scheme == "default"
    assert current.shell_theme == "Adwaita"
    assert client.is_shell_theme_supported is True


def test_gsettings_apply_full(mock_gio_environment):
    """Verifica l'applicazione completa di un ThemeSet incluso Shell theme."""
    client = GSettingsClient()
    new_themes = ThemeSet(
        gtk_theme="Nordic",
        icon_theme="Papirus-Dark",
        cursor_theme="Capitaine-Cursors",
        color_scheme="prefer-dark",
        shell_theme="Nordic-Shell",
    )

    client.apply(new_themes)

    assert mock_gio_environment["interface_settings"].get_string("gtk-theme") == "Nordic"
    assert mock_gio_environment["interface_settings"].get_string("icon-theme") == "Papirus-Dark"
    assert (
        mock_gio_environment["interface_settings"].get_string("cursor-theme") == "Capitaine-Cursors"
    )
    assert mock_gio_environment["interface_settings"].get_string("color-scheme") == "prefer-dark"
    assert mock_gio_environment["shell_settings"].get_string("name") == "Nordic-Shell"


def test_gsettings_extension_schema_in_directory(tmp_path: Path):
    """Verifica la ricerca di schemi personalizzati nelle directory delle estensioni."""
    ext_dir = tmp_path / "extensions" / "user-theme@gnome" / "schemas"
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "gschemas.compiled").write_text("dummy")

    mock_schema_source = MagicMock()
    mock_schema_source.lookup.return_value = MagicMock()  # Interfaccia trovata

    mock_ext_source = MagicMock()
    mock_ext_source.lookup.return_value = MagicMock()  # Shell trovata nella cartella estensione

    with (
        patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", True),
        patch("gnome_theme_manager.core.gsettings.Gio") as mock_gio,
    ):
        mock_gio.SettingsSchemaSource.get_default.return_value = mock_schema_source
        mock_gio.SettingsSchemaSource.new_from_directory.return_value = mock_ext_source
        mock_gio.Settings.new_full.return_value = MockGioSettings(
            "org.gnome.shell.extensions.user-theme", {"name": "Yaru"}
        )

        client = GSettingsClient(custom_schema_dirs=[tmp_path / "extensions"])
        assert client.is_shell_theme_supported is True


def test_gsettings_set_shell_theme_unsupported(tmp_path: Path):
    """Verifica che set_shell_theme sollevi GSettingsUnavailableError se l'estensione non è presente."""
    mock_schema_source = MagicMock()

    def lookup_side_effect(schema: str, recursive: bool):
        if schema == "org.gnome.shell.extensions.user-theme":
            return None
        return MagicMock()

    mock_schema_source.lookup.side_effect = lookup_side_effect

    empty_dir = tmp_path / "empty_extensions"
    empty_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", True),
        patch("gnome_theme_manager.core.gsettings.Gio") as mock_gio,
        patch("pathlib.Path.home", return_value=empty_dir),
    ):
        mock_gio.SettingsSchemaSource.get_default.return_value = mock_schema_source
        mock_gio.Settings.new_full.return_value = MockGioSettings()

        client = GSettingsClient()
        # Non trova lo schema shell da nessuna parte
        client._shell_settings = None
        assert client.is_shell_theme_supported is False

        with pytest.raises(GSettingsUnavailableError, match="User Themes"):
            client.set_shell_theme("Nordic")


def test_gsettings_unavailable_when_gio_missing():
    """Verifica che venga sollevata GSettingsUnavailableError se PyGObject non è installato."""
    with (
        patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", False),
        pytest.raises(GSettingsUnavailableError, match="PyGObject .* is not available"),
    ):
        GSettingsClient()


def test_gsettings_get_and_apply_fonts():
    """Verifica lettura e scrittura font tramite GSettingsClient."""
    from gnome_theme_manager.core.fonts import FontConfig

    storage = {
        "font-name": "Cantarell 11",
        "document-font-name": "Sans 11",
        "monospace-font-name": "Monospace 11",
        "text-scaling-factor": 1.0,
    }

    mock_schema = MagicMock()
    mock_schema_source = MagicMock()
    mock_schema_source.lookup.return_value = mock_schema

    with (
        patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", True),
        patch("gnome_theme_manager.core.gsettings.Gio") as mock_gio,
    ):
        mock_gio.SettingsSchemaSource.get_default.return_value = mock_schema_source
        mock_gio.Settings.new_full.return_value = MockGioSettings(
            "org.gnome.desktop.interface", storage
        )

        client = GSettingsClient()
        fonts = client.get_fonts()
        assert fonts.interface_font == "Cantarell 11"
        assert fonts.document_font == "Sans 11"
        assert fonts.monospace_font == "Monospace 11"
        assert fonts.text_scaling_factor == 1.0

        # Apply new fonts
        new_fonts = FontConfig(
            interface_font="Inter 10",
            document_font="Inter 10",
            monospace_font="Fira Code 12",
            text_scaling_factor=1.25,
        )
        res = client.apply_fonts(new_fonts)
        assert res is True

        # Verify values updated
        updated = client.get_fonts()
        assert updated.interface_font == "Inter 10"
        assert updated.document_font == "Inter 10"
        assert updated.monospace_font == "Fira Code 12"
        assert updated.text_scaling_factor == 1.25

