# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for TerminalProfile mapping and OS command synthesis (Prompt 2.1 Step 3)."""

from unittest.mock import MagicMock, patch

from gnome_theme_manager.core.manager import ThemeManager
from gnome_theme_manager.core.os_detector import OSInfo
from gnome_theme_manager.core.terminal_profile import (
    GENERIC_FALLBACK_PROFILE,
    TerminalProfile,
    get_terminal_profile,
    synthesize_install_command,
)


def test_terminal_profile_basic_and_formatting() -> None:
    """Verify profile fields and launch command string substitution."""
    profile = TerminalProfile(
        terminal_id="ptyxis",
        terminal_name="Ptyxis",
        launch_command='ptyxis -e "{cmd}"',
        config_file_path="dconf: /org/gnome/Ptyxis/",
        supports_tabs=True,
        supports_split=False,
        supports_profiles=True,
        install_command="sudo apt install -y ptyxis",
        icon_name="org.gnome.Ptyxis",
        notes="Modern terminal",
    )
    assert profile.format_launch_command("top") == 'ptyxis -e "top"'
    d = profile.to_dict()
    assert d["terminal_id"] == "ptyxis"
    assert d["supports_profiles"] is True


def test_synthesize_install_command_multi_os() -> None:
    """Verify installation commands generated for apt, dnf, pacman, and zypper."""
    # Ptyxis
    assert synthesize_install_command("ptyxis", "apt") == "sudo apt install -y ptyxis"
    assert synthesize_install_command("ptyxis", "dnf") == "sudo dnf install -y ptyxis"
    assert synthesize_install_command("ptyxis", "pacman") == "sudo pacman -S --noconfirm ptyxis"
    assert synthesize_install_command("ptyxis", "zypper") == "sudo zypper install -y ptyxis"

    # Package mapping (kgx -> gnome-console)
    assert synthesize_install_command("kgx", "apt") == "sudo apt install -y gnome-console"
    assert synthesize_install_command("kgx", "dnf") == "sudo dnf install -y gnome-console"

    # Fallback package manager
    assert synthesize_install_command("alacritty", "brew") == "sudo brew install alacritty"


def test_get_terminal_profile_ptyxis_with_os() -> None:
    """Verify get_terminal_profile generates correct commands based on OS."""
    fedora_os = OSInfo("fedora", "40", "dnf", "Fedora 40")
    profile = get_terminal_profile("ptyxis", os_info=fedora_os)
    assert profile.terminal_id == "ptyxis"
    assert profile.terminal_name == "Ptyxis"
    assert profile.install_command == "sudo dnf install -y ptyxis"
    assert profile.supports_profiles is True
    assert profile.icon_name == "org.gnome.Ptyxis"


def test_get_terminal_profile_gnome_terminal_arch() -> None:
    """Verify GNOME Terminal profile on Arch Linux."""
    arch_os = OSInfo("arch", "rolling", "pacman", "Arch Linux")
    profile = get_terminal_profile("gnome-terminal", os_info=arch_os)
    assert profile.terminal_id == "gnome-terminal"
    assert profile.install_command == "sudo pacman -S --noconfirm gnome-terminal"
    assert profile.supports_tabs is True


def test_get_terminal_profile_unknown_fallback() -> None:
    """Verify unknown terminal falls back to generic profile."""
    profile = get_terminal_profile("nonexistent-emulator")
    assert profile.terminal_id == "unknown"
    assert profile.terminal_name == "Generic Terminal"
    assert profile.launch_command == 'sh -c "{cmd}"'
    assert profile.icon_name == GENERIC_FALLBACK_PROFILE.icon_name


def test_theme_manager_get_terminal_profile() -> None:
    """Verify ThemeManager facade resolves profile delegating to detected terminal."""
    tm = ThemeManager(
        scanner=MagicMock(),
        gsettings=MagicMock(),
        gtk4_linker=MagicMock(),
        installer=MagicMock(),
        presets=MagicMock(),
        sandbox_bridge=MagicMock(),
        validator=MagicMock(),
        extensions=MagicMock(),
    )
    with patch.object(tm, "detect_terminal", return_value=MagicMock(terminal_id="ptyxis")):
        with patch.object(tm, "detect_os", return_value=OSInfo("ubuntu", "24.04", "apt", "Ubuntu")):
            prof = tm.get_terminal_profile()
            assert prof.terminal_id == "ptyxis"
            assert "apt install" in prof.install_command
