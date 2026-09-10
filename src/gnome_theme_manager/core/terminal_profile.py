# SPDX-License-Identifier: GPL-3.0-or-later

"""Terminal profile mapping and OS-specific command synthesis module (Prompt 2.1 Step 3).

Provides command specifications, configuration paths, feature capabilities,
and OS-tailored installation commands for all supported Linux terminal emulators.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from .os_detector import OSInfo, detect_os, get_install_command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TerminalProfile:
    """Represents the configuration and capability profile of a terminal emulator."""

    terminal_id: str
    terminal_name: str
    launch_command: str
    config_file_path: str
    supports_tabs: bool
    supports_split: bool
    supports_profiles: bool
    install_command: str
    icon_name: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to dictionary."""
        return asdict(self)

    def format_launch_command(self, cmd: str) -> str:
        """Format the terminal launch command with the specified command string."""
        return self.launch_command.replace("{cmd}", cmd)


# Package names across various package managers if distinct from terminal_id
PACKAGE_MAP: dict[str, dict[str, str]] = {
    "kgx": {
        "apt": "gnome-console",
        "dnf": "gnome-console",
        "pacman": "gnome-console",
        "zypper": "gnome-console",
    },
    "warp": {
        "apt": "warp-terminal",
        "dnf": "warp-terminal",
        "pacman": "warp-terminal",
        "zypper": "warp-terminal",
    },
    "urxvt": {
        "apt": "rxvt-unicode",
        "dnf": "rxvt-unicode",
        "pacman": "rxvt-unicode",
        "zypper": "rxvt-unicode",
    },
}

# Base profile definitions
BASE_TERMINAL_PROFILES: dict[str, dict[str, Any]] = {
    "ptyxis": {
        "terminal_name": "Ptyxis",
        "launch_command": 'ptyxis -e "{cmd}"',
        "config_file_path": "dconf: /org/gnome/Ptyxis/",
        "supports_tabs": True,
        "supports_split": False,
        "supports_profiles": True,
        "icon_name": "org.gnome.Ptyxis",
        "notes": "Default container-oriented terminal on GNOME 47+",
    },
    "gnome-terminal": {
        "terminal_name": "GNOME Terminal",
        "launch_command": 'gnome-terminal -- bash -c "{cmd}"',
        "config_file_path": "dconf: /org/gnome/terminal/legacy/profiles:/",
        "supports_tabs": True,
        "supports_split": False,
        "supports_profiles": True,
        "icon_name": "org.gnome.Terminal",
        "notes": "Standard GNOME Terminal with relocatable GSettings profile support",
    },
    "kgx": {
        "terminal_name": "GNOME Console",
        "launch_command": 'kgx -e "{cmd}"',
        "config_file_path": "dconf: /org/gnome/Console/",
        "supports_tabs": True,
        "supports_split": False,
        "supports_profiles": False,
        "icon_name": "org.gnome.Console",
        "notes": "Minimal GNOME terminal with system palette synchronization",
    },
    "konsole": {
        "terminal_name": "Konsole",
        "launch_command": 'konsole -e "{cmd}"',
        "config_file_path": "~/.local/share/konsole/",
        "supports_tabs": True,
        "supports_split": True,
        "supports_profiles": True,
        "icon_name": "org.kde.konsole",
        "notes": "KDE Plasma terminal emulator with split-view and tabs",
    },
    "xfce4-terminal": {
        "terminal_name": "XFCE Terminal",
        "launch_command": 'xfce4-terminal -e "{cmd}"',
        "config_file_path": "~/.config/xfce4/terminal/terminalrc",
        "supports_tabs": True,
        "supports_split": False,
        "supports_profiles": False,
        "icon_name": "xfce4-terminal",
        "notes": "Lightweight XFCE desktop terminal emulator",
    },
    "mate-terminal": {
        "terminal_name": "MATE Terminal",
        "launch_command": 'mate-terminal -e "{cmd}"',
        "config_file_path": "dconf: /org/mate/terminal/",
        "supports_tabs": True,
        "supports_split": False,
        "supports_profiles": True,
        "icon_name": "mate-terminal",
        "notes": "MATE desktop environment terminal with tabbed profiles",
    },
    "tilix": {
        "terminal_name": "Tilix",
        "launch_command": 'tilix -e "{cmd}"',
        "config_file_path": "dconf: /com/gexperts/Tilix/",
        "supports_tabs": True,
        "supports_split": True,
        "supports_profiles": True,
        "icon_name": "com.gexperts.Tilix",
        "notes": "Advanced GTK tiling terminal emulator following GNOME HIG",
    },
    "terminator": {
        "terminal_name": "Terminator",
        "launch_command": 'terminator -e "{cmd}"',
        "config_file_path": "~/.config/terminator/config",
        "supports_tabs": True,
        "supports_split": True,
        "supports_profiles": True,
        "icon_name": "terminator",
        "notes": "Multi-grid tiling terminal written in Python/GTK",
    },
    "alacritty": {
        "terminal_name": "Alacritty",
        "launch_command": "alacritty -e {cmd}",
        "config_file_path": "~/.config/alacritty/alacritty.toml",
        "supports_tabs": False,
        "supports_split": False,
        "supports_profiles": False,
        "icon_name": "Alacritty",
        "notes": "Fast, GPU-accelerated terminal emulator configured via TOML",
    },
    "kitty": {
        "terminal_name": "Kitty",
        "launch_command": "kitty {cmd}",
        "config_file_path": "~/.config/kitty/kitty.conf",
        "supports_tabs": True,
        "supports_split": True,
        "supports_profiles": False,
        "icon_name": "kitty",
        "notes": "GPU-accelerated terminal emulator with extensive graphics and font support",
    },
    "warp": {
        "terminal_name": "Warp",
        "launch_command": 'warp-terminal -e "{cmd}"',
        "config_file_path": "~/.config/warp-terminal/",
        "supports_tabs": True,
        "supports_split": True,
        "supports_profiles": False,
        "icon_name": "dev.warp.Warp",
        "notes": "Modern block-based terminal emulator",
    },
    "wezterm": {
        "terminal_name": "WezTerm",
        "launch_command": 'wezterm start -- "{cmd}"',
        "config_file_path": "~/.config/wezterm/wezterm.lua",
        "supports_tabs": True,
        "supports_split": True,
        "supports_profiles": False,
        "icon_name": "org.wezfurlong.wezterm",
        "notes": "GPU-accelerated cross-platform terminal configured via Lua",
    },
    "xterm": {
        "terminal_name": "xterm",
        "launch_command": 'xterm -e "{cmd}"',
        "config_file_path": "~/.Xresources",
        "supports_tabs": False,
        "supports_split": False,
        "supports_profiles": False,
        "icon_name": "xterm",
        "notes": "Standard terminal emulator for the X Window System",
    },
    "urxvt": {
        "terminal_name": "rxvt-unicode",
        "launch_command": 'urxvt -e "{cmd}"',
        "config_file_path": "~/.Xresources",
        "supports_tabs": True,
        "supports_split": False,
        "supports_profiles": False,
        "icon_name": "utilities-terminal",
        "notes": "Customizable unicode terminal emulator for X11",
    },
}

GENERIC_FALLBACK_PROFILE = TerminalProfile(
    terminal_id="unknown",
    terminal_name="Generic Terminal",
    launch_command='sh -c "{cmd}"',
    config_file_path="",
    supports_tabs=False,
    supports_split=False,
    supports_profiles=False,
    install_command="",
    icon_name="utilities-terminal-symbolic",
    notes="Generic POSIX fallback terminal",
)


def synthesize_install_command(
    terminal_id: str,
    package_manager: str,
) -> str:
    """Synthesize the exact distribution package installation command.

    Args:
        terminal_id: Unique identifier of the terminal.
        package_manager: Detected package manager ('apt', 'dnf', 'pacman', 'zypper').

    Returns:
        Shell command string (e.g. 'sudo dnf install -y ptyxis').
    """
    return get_install_command(terminal_id, package_manager=package_manager)


def get_terminal_profile(
    terminal_id: str,
    os_info: OSInfo | None = None,
) -> TerminalProfile:
    """Retrieve the capability profile and commands for a given terminal emulator.

    Args:
        terminal_id: Internal terminal identifier (e.g. 'ptyxis', 'gnome-terminal').
        os_info: Optional OSInfo instance; auto-detected if not supplied.

    Returns:
        TerminalProfile instance.
    """
    clean_id = terminal_id.lower().strip()
    spec = BASE_TERMINAL_PROFILES.get(clean_id)
    if not spec:
        return GENERIC_FALLBACK_PROFILE

    resolved_os = os_info if os_info is not None else detect_os()
    pm = resolved_os.package_manager if resolved_os.package_manager != "unknown" else "apt"
    install_cmd = synthesize_install_command(clean_id, pm)

    return TerminalProfile(
        terminal_id=clean_id,
        terminal_name=str(spec["terminal_name"]),
        launch_command=str(spec["launch_command"]),
        config_file_path=str(spec["config_file_path"]),
        supports_tabs=bool(spec["supports_tabs"]),
        supports_split=bool(spec["supports_split"]),
        supports_profiles=bool(spec["supports_profiles"]),
        install_command=install_cmd,
        icon_name=str(spec["icon_name"]),
        notes=str(spec["notes"]),
    )
