# SPDX-License-Identifier: GPL-3.0-or-later

"""Test unitari per la rilevazione dello stato di override GTK4 (Task 0.1)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gnome_theme_manager.core.gsettings import GSettingsClient, Gtk4OverrideStatus


@pytest.fixture
def mock_gio_minimal():
    """Fixture che simula Gio sufficientemente per istanziare GSettingsClient."""
    with (
        patch("gnome_theme_manager.core.gsettings._GIO_AVAILABLE", True),
        patch("gnome_theme_manager.core.gsettings.Gio") as mock_gio,
    ):
        mock_schema_source = mock_gio.SettingsSchemaSource.get_default.return_value
        mock_schema_source.lookup.return_value = "dummy_schema"
        mock_gio.Settings.new.return_value = "dummy_settings"
        mock_gio.Settings.new_full.return_value = "dummy_settings"
        yield mock_gio


def test_detect_gtk4_override_active(tmp_path: Path, mock_gio_minimal):
    """Verifica la rilevazione corretta dell'override se il file esiste."""
    gtk_dir = tmp_path / ".config" / "gtk-4.0"
    gtk_dir.mkdir(parents=True, exist_ok=True)
    css_file = gtk_dir / "gtk.css"
    css_file.write_text("body { background: red; }")

    client = GSettingsClient(custom_schema_dirs=[])
    with patch("gnome_theme_manager.core.gsettings.GTK4_CONFIG_DIR", gtk_dir):
        status = client.detect_gtk4_override()
        assert status == Gtk4OverrideStatus.ACTIVE


def test_detect_gtk4_override_inactive(tmp_path: Path, mock_gio_minimal):
    """Verifica che se il file non esiste lo stato sia INACTIVE."""
    gtk_dir = tmp_path / ".config" / "gtk-4.0"
    client = GSettingsClient(custom_schema_dirs=[])
    with patch("gnome_theme_manager.core.gsettings.GTK4_CONFIG_DIR", gtk_dir):
        status = client.detect_gtk4_override()
        assert status == Gtk4OverrideStatus.INACTIVE
