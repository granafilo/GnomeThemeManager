# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for GNOME Shell Extensions core manager (Task 5.3)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.extensions import (
    ExtensionsManager,
)


@pytest.fixture
def mock_user_extensions_dir(tmp_path: Path) -> Path:
    ext_dir = tmp_path / "user_extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extension 1: user-theme
    user_theme_dir = ext_dir / "user-theme@gnome-shell-extensions.gcampax.github.com"
    user_theme_dir.mkdir(parents=True, exist_ok=True)
    (user_theme_dir / "metadata.json").write_text(
        json.dumps(
            {
                "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com",
                "name": "User Themes",
                "description": "Load shell themes from user directory.",
                "url": "https://gitlab.gnome.org/GNOME/gnome-shell-extensions",
                "version": 46,
            }
        ),
        encoding="utf-8",
    )

    # 2. Extension 2: dash-to-dock
    dock_dir = ext_dir / "dash-to-dock@micxgx.gmail.com"
    dock_dir.mkdir(parents=True, exist_ok=True)
    (dock_dir / "metadata.json").write_text(
        json.dumps(
            {
                "uuid": "dash-to-dock@micxgx.gmail.com",
                "name": "Dash to Dock",
                "description": "A dock for the Gnome Shell.",
                "url": "https://micheleg.github.io/dash-to-dock/",
                "version": 90,
            }
        ),
        encoding="utf-8",
    )

    return ext_dir


@pytest.fixture
def mock_system_extensions_dir(tmp_path: Path) -> Path:
    sys_dir = tmp_path / "system_extensions"
    sys_dir.mkdir(parents=True, exist_ok=True)

    # System Extension: ubuntu-dock
    dock_dir = sys_dir / "ubuntu-dock@ubuntu.com"
    dock_dir.mkdir(parents=True, exist_ok=True)
    (dock_dir / "metadata.json").write_text(
        json.dumps(
            {
                "uuid": "ubuntu-dock@ubuntu.com",
                "name": "Ubuntu Dock",
                "description": "Ubuntu default dock.",
                "url": "https://github.com/ubuntu/gnome-shell-extension-ubuntu-dock",
                "version": 85,
            }
        ),
        encoding="utf-8",
    )

    return sys_dir


def test_extensions_manager_list_extensions(
    tmp_path: Path, mock_user_extensions_dir: Path, mock_system_extensions_dir: Path
) -> None:
    """Test discovering and listing all installed GNOME Shell extensions."""
    with (
        patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
        patch("shutil.which", return_value="/usr/bin/gnome-extensions"),
        patch("subprocess.run") as mock_run,
    ):
        # Mock gnome-extensions list --enabled returning user-theme
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="user-theme@gnome-shell-extensions.gcampax.github.com\n",
        )

        manager = ExtensionsManager(
            prefs_file=tmp_path / "ui_prefs.json",
            user_extensions_dir=mock_user_extensions_dir,
            system_extensions_dir=mock_system_extensions_dir,
        )

        extensions = manager.list_extensions()
        assert len(extensions) == 3

        ext_map = {e.uuid: e for e in extensions}
        assert "user-theme@gnome-shell-extensions.gcampax.github.com" in ext_map
        assert "dash-to-dock@micxgx.gmail.com" in ext_map
        assert "ubuntu-dock@ubuntu.com" in ext_map

        # user-theme is enabled
        user_theme = ext_map["user-theme@gnome-shell-extensions.gcampax.github.com"]
        assert user_theme.name == "User Themes"
        assert user_theme.enabled is True
        assert user_theme.is_user_level is True
        assert user_theme.version == "46"

        # dash-to-dock is disabled
        dock = ext_map["dash-to-dock@micxgx.gmail.com"]
        assert dock.enabled is False
        assert dock.is_user_level is True

        # ubuntu-dock is system level
        sys_dock = ext_map["ubuntu-dock@ubuntu.com"]
        assert sys_dock.is_user_level is False


def test_extensions_manager_enable_and_disable(tmp_path: Path) -> None:
    """Test enable, disable, and toggle methods via CLI fallback."""
    with (
        patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
        patch("shutil.which", return_value="/usr/bin/gnome-extensions"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)

        manager = ExtensionsManager(prefs_file=tmp_path / "ui_prefs.json")

        assert manager.enable_extension("dash-to-dock@micxgx.gmail.com") is True
        mock_run.assert_called_with(
            ["gnome-extensions", "enable", "dash-to-dock@micxgx.gmail.com"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert manager.disable_extension("dash-to-dock@micxgx.gmail.com") is True
        mock_run.assert_called_with(
            ["gnome-extensions", "disable", "dash-to-dock@micxgx.gmail.com"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert manager.toggle_extension("dash-to-dock@micxgx.gmail.com", True) is True
        assert manager.toggle_extension("dash-to-dock@micxgx.gmail.com", False) is True


def test_extensions_manager_get_store_url() -> None:
    """Test building official GNOME extensions web URL."""
    manager = ExtensionsManager()
    url = manager.get_store_url("dash-to-dock@micxgx.gmail.com")
    assert "extensions.gnome.org" in url
    assert "dash-to-dock" in url or "micxgx" in url


def test_extensions_manager_open_prefs_and_app() -> None:
    """Test launching extension preferences and official extensions app."""
    manager = ExtensionsManager()
    with (
        patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
        patch("shutil.which", return_value="/usr/bin/gnome-extensions"),
        patch("subprocess.Popen") as mock_popen,
    ):
        assert manager.open_prefs("dash-to-dock@micxgx.gmail.com") is True
        mock_popen.assert_called_with(
            ["gnome-extensions", "prefs", "dash-to-dock@micxgx.gmail.com"]
        )

        with patch(
            "shutil.which",
            side_effect=lambda cmd: "/usr/bin/" + cmd if cmd == "extension-manager" else None,
        ):
            assert manager.open_extensions_app() is True
            mock_popen.assert_called_with(["extension-manager"])


def test_extensions_manager_uninstall(tmp_path: Path) -> None:
    """Test uninstalling user-level extension via CLI and fallback directory deletion."""
    user_ext_dir = tmp_path / "user_extensions"
    user_ext_dir.mkdir(parents=True, exist_ok=True)
    ext_dir = user_ext_dir / "test@ext.org"
    ext_dir.mkdir(parents=True, exist_ok=True)

    manager = ExtensionsManager(
        user_extensions_dir=user_ext_dir,
        system_extensions_dir=tmp_path / "system_extensions",
    )

    # 1. CLI success
    with (
        patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
        patch("shutil.which", return_value="/usr/bin/gnome-extensions"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        assert manager.uninstall_extension("test@ext.org") is True

    # 2. Direct directory fallback
    with (
        patch("gnome_theme_manager.core.extensions._GIO_AVAILABLE", False),
        patch("shutil.which", return_value="/usr/bin/gnome-extensions"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=1)
        assert ext_dir.exists()
        assert manager.uninstall_extension("test@ext.org") is True
        assert not ext_dir.exists()
