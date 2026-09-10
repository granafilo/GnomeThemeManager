# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end integration tests for OS-tailored terminal detection and UI adaptation (Prompt 2.1 Step 5)."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.os_detector import OSInfo
from gnome_theme_manager.core.terminal_detector import TerminalInfo
from gnome_theme_manager.core.terminal_palette import TerminalPalette, TerminalProfileSummary
from gnome_theme_manager.core.terminal_profile import get_terminal_profile
from gnome_theme_manager.gui_gtk import is_gtk_available
from gnome_theme_manager.gui_gtk.pages.terminal import TerminalPage

UI_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "gnome_theme_manager"
    / "gui_gtk"
    / "ui"
    / "terminal_page.ui"
)


def test_terminal_page_ui_declarative_structure() -> None:
    """Verify presence of terminal environment and selector controls in terminal_page.ui."""
    tree = ET.parse(UI_PATH)
    root = tree.getroot()
    ids = [elem.attrib.get("id") for elem in root.iter("object") if "id" in elem.attrib]

    assert "terminal_environment_group" in ids
    assert "terminal_selector_row" in ids
    assert "terminal_icon_image" in ids
    assert "terminal_status_badge" in ids
    assert "terminal_command_row" in ids
    assert "terminal_warning_row" in ids
    assert "profiles_group" in ids


def test_scenario_a_ptyxis_detected_end_to_end() -> None:
    """Scenario A: Ptyxis is installed and default -> verified through full cascade."""
    fedora_os = OSInfo("fedora", "40", "dnf", "Fedora 40")
    ptyxis_term = TerminalInfo(
        terminal_id="ptyxis",
        terminal_name="Ptyxis",
        binary="ptyxis",
        desktop_file="org.gnome.Ptyxis.desktop",
        detection_method="xdg-terminal-exec",
        is_installed=True,
        is_default=True,
        supports_gsettings=True,
        schema_id="org.gnome.Ptyxis",
        schema_accessible=True,
    )
    assert ptyxis_term.terminal_id == "ptyxis"
    assert ptyxis_term.is_default is True

    profile = get_terminal_profile("ptyxis", os_info=fedora_os)
    assert profile.terminal_id == "ptyxis"
    assert profile.terminal_name == "Ptyxis"
    assert 'ptyxis -e "{cmd}"' in profile.launch_command
    assert "sudo dnf install -y ptyxis" in profile.install_command
    assert profile.supports_profiles is True
    assert profile.icon_name == "org.gnome.Ptyxis"


def test_scenario_b_unknown_fallback_end_to_end() -> None:
    """Scenario B: No terminal recognized / headless fallback."""
    arch_os = OSInfo("arch", "rolling", "pacman", "Arch Linux")
    profile = get_terminal_profile("unknown", os_info=arch_os)
    assert profile.terminal_id == "unknown"
    assert profile.terminal_name == "Generic Terminal"
    assert profile.launch_command == 'sh -c "{cmd}"'
    assert profile.supports_profiles is False


def test_scenario_c_manual_override_alacritty() -> None:
    """Scenario C: Manual override to Alacritty synthesizes correct config and install command."""
    ubuntu_os = OSInfo("ubuntu", "24.04", "apt", "Ubuntu 24.04")
    profile = get_terminal_profile("alacritty", os_info=ubuntu_os)
    assert profile.terminal_id == "alacritty"
    assert "alacritty -e {cmd}" in profile.launch_command
    assert "sudo apt install -y alacritty" in profile.install_command
    assert profile.supports_profiles is False
    assert "alacritty.toml" in profile.config_file_path


@pytest.mark.skipif(not is_gtk_available(), reason="GTK not available in current environment")
def test_terminal_page_gui_dynamic_adaptation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify TerminalPage dynamic UI updates across detection, override, and apply."""
    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.detect_os.return_value = OSInfo("ubuntu", "24.04", "apt", "Ubuntu 24.04")
    mock_mgr.detect_terminal.return_value = TerminalInfo(
        terminal_id="ptyxis",
        terminal_name="Ptyxis",
        binary="ptyxis",
        desktop_file="org.gnome.Ptyxis.desktop",
        detection_method="xdg-terminal-exec",
        is_installed=True,
        is_default=True,
        supports_gsettings=True,
        schema_id="org.gnome.Ptyxis",
        schema_accessible=True,
    )
    mock_mgr.detect_default_terminal.return_value = mock_mgr.detect_terminal.return_value
    mock_mgr.get_terminal_profile.side_effect = lambda tid: get_terminal_profile(
        tid, os_info=mock_mgr.detect_os.return_value
    )
    mock_mgr.list_terminal_profiles.return_value = [
        TerminalProfileSummary(id="default", name="Default", is_default=True)
    ]
    mock_mgr.get_current_terminal_palette.return_value = TerminalPalette()

    with patch(
        "gnome_theme_manager.gui_gtk.pages.terminal.is_terminal_installed", return_value=True
    ):
        page = TerminalPage(mock_mgr)
        page.refresh()

        # Check Scenario A: Ptyxis selected
        assert page._selected_terminal_id == "ptyxis"
        assert "Ptyxis" in page.terminal_selector_row.get_subtitle()
        assert page.terminal_status_badge.get_label() == "Default"
        assert 'ptyxis -e "{cmd}"' in page.terminal_command_row.get_subtitle()
        assert page.profiles_group.get_visible() is True
        assert page.terminal_warning_row.get_visible() is False

        # Check Scenario C: Manual override to Alacritty
        alacritty_idx = page._supported_terminals.index("alacritty")
        page.terminal_selector_row.set_selected(alacritty_idx)

        assert page._selected_terminal_id == "alacritty"
        assert "Alacritty" in page.terminal_selector_row.get_subtitle()
        assert "alacritty -e {cmd}" in page.terminal_command_row.get_subtitle()
        # Alacritty does not use profiles -> profiles_group hidden
        assert page.profiles_group.get_visible() is False
        # Notice shown because Alacritty uses file configuration
        assert page.terminal_warning_row.get_visible() is True
        assert "alacritty.toml" in page.terminal_warning_row.get_subtitle()


@pytest.mark.skipif(not is_gtk_available(), reason="GTK not available in current environment")
def test_terminal_page_not_installed_warning() -> None:
    """Verify warning banner and OS-tailored install command when target terminal is not installed."""
    mock_mgr = MagicMock(spec=ThemeManager)
    mock_mgr.detect_os.return_value = OSInfo("fedora", "40", "dnf", "Fedora 40")
    mock_mgr.detect_terminal.return_value = TerminalInfo(
        terminal_id="ptyxis",
        terminal_name="Ptyxis",
        binary="ptyxis",
        desktop_file="org.gnome.Ptyxis.desktop",
        detection_method="xdg-terminal-exec",
        is_installed=False,
        is_default=True,
    )
    mock_mgr.detect_default_terminal.return_value = mock_mgr.detect_terminal.return_value
    mock_mgr.get_terminal_profile.side_effect = lambda tid: get_terminal_profile(
        tid, os_info=mock_mgr.detect_os.return_value
    )
    mock_mgr.list_terminal_profiles.return_value = []
    mock_mgr.get_current_terminal_palette.return_value = TerminalPalette()

    with patch(
        "gnome_theme_manager.gui_gtk.pages.terminal.is_terminal_installed", return_value=False
    ):
        page = TerminalPage(mock_mgr)
        page.refresh()

        assert page.terminal_warning_row.get_visible() is True
        assert "sudo dnf install -y ptyxis" in page.terminal_warning_row.get_subtitle()
        assert "Not Installed" in page.terminal_status_badge.get_label()
        assert page.terminal_selector_row.has_css_class("warning")
