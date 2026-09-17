# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GTK4 override status detection (Task 0.1)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from gnome_theme_manager.core.gsettings import GSettingsClient, Gtk4OverrideStatus


@pytest.fixture
def mock_gio_minimal():
    """Fixture that mocks Gio sufficiently to instantiate GSettingsClient."""
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
    """Verify correct detection of override if the file exists."""
    gtk_dir = tmp_path / ".config" / "gtk-4.0"
    gtk_dir.mkdir(parents=True, exist_ok=True)
    css_file = gtk_dir / "gtk.css"
    css_file.write_text("body { background: red; }")

    client = GSettingsClient(custom_schema_dirs=[])
    with patch("gnome_theme_manager.core.gsettings.GTK4_CONFIG_DIR", gtk_dir):
        status = client.detect_gtk4_override()
        assert status == Gtk4OverrideStatus.ACTIVE


def test_detect_gtk4_override_inactive(tmp_path: Path, mock_gio_minimal):
    """Verify that if the file does not exist the status is INACTIVE."""
    gtk_dir = tmp_path / ".config" / "gtk-4.0"
    client = GSettingsClient(custom_schema_dirs=[])
    with patch("gnome_theme_manager.core.gsettings.GTK4_CONFIG_DIR", gtk_dir):
        status = client.detect_gtk4_override()
        assert status == Gtk4OverrideStatus.INACTIVE


def test_detect_gtk4_override_run_host_symlink(tmp_path: Path, mock_gio_minimal):
    """Verify that a symlink pointing to /run/host/<path> is detected as ACTIVE if <path> exists."""
    gtk_dir = tmp_path / ".config" / "gtk-4.0"
    gtk_dir.mkdir(parents=True, exist_ok=True)
    real_css = tmp_path / "usr" / "share" / "themes" / "Colloid" / "gtk.css"
    real_css.parent.mkdir(parents=True, exist_ok=True)
    real_css.write_text("/* theme */")

    symlink_css = gtk_dir / "gtk.css"
    # Create symlink pointing to /run/host + real_css
    fake_run_host = Path(f"/run/host{real_css}")
    symlink_css.symlink_to(fake_run_host)

    client = GSettingsClient(custom_schema_dirs=[])
    with patch("gnome_theme_manager.core.gsettings.GTK4_CONFIG_DIR", gtk_dir):
        status = client.detect_gtk4_override()
        assert status == Gtk4OverrideStatus.ACTIVE


def test_detect_gtk4_override_flatpak_target_symlink(tmp_path: Path, mock_gio_minimal):
    """Verify that a symlink pointing to host path is detected inside Flatpak if /run/host/<path> exists."""
    gtk_dir = tmp_path / ".config" / "gtk-4.0"
    gtk_dir.mkdir(parents=True, exist_ok=True)

    symlink_css = gtk_dir / "gtk.css"
    # Points to /usr/share/... which doesn't exist on its own in Flatpak runtime
    symlink_css.symlink_to("/usr/share/themes/Colloid/gtk.css")

    real_is_file = Path.is_file

    def fake_is_file(self: Path) -> bool:
        if str(self) == "/run/host/usr/share/themes/Colloid/gtk.css":
            return True
        return real_is_file(self)

    client = GSettingsClient(custom_schema_dirs=[])
    with (
        patch("gnome_theme_manager.core.gsettings.GTK4_CONFIG_DIR", gtk_dir),
        patch.object(Path, "is_file", fake_is_file),
    ):
        status = client.detect_gtk4_override()
        assert status == Gtk4OverrideStatus.ACTIVE
