# SPDX-License-Identifier: GPL-3.0-or-later

"""CLI argument parser definition and configuration with argparse."""

import argparse

from gnome_theme_manager import _, __version__


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the main ArgumentParser for the application."""
    parser = argparse.ArgumentParser(
        prog="gnome-theme-manager",
        description=_("Modular theme manager for GTK, icons, cursors, and GNOME Shell."),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-g",
        "--gui",
        action="store_true",
        help=_("Launch native GNOME GTK4/Libadwaita graphical interface"),
    )

    subparsers = parser.add_subparsers(
        title=_("commands"),
        dest="command",
        help=_("Command to execute"),
    )

    # Subcommand: gui (GTK4/Libadwaita)
    subparsers.add_parser(
        "gui",
        help=_("Launch native GNOME GTK4/Libadwaita graphical interface"),
    )

    # Subcommand: current
    subparsers.add_parser(
        "current",
        help=_("Show currently applied themes on GNOME desktop"),
    )

    # Subcommand: sandbox-status
    subparsers.add_parser(
        "sandbox-status",
        help=_("Show sandbox runtime integration status (Snap and Flatpak)"),
    )

    # Subcommand: list
    list_parser = subparsers.add_parser(
        "list",
        help=_("List available themes on the system"),
    )
    list_parser.add_argument(
        "-t",
        "--type",
        choices=["all", "gtk", "icon", "cursor", "shell"],
        default="all",
        help=_("Filter by theme type (default: all)"),
    )
    list_parser.add_argument(
        "--user-only",
        action="store_true",
        help=_("Show only user-installed themes (~/.local/share/...)"),
    )

    # Subcommand: apply
    apply_parser = subparsers.add_parser(
        "apply",
        help=_("Apply one or more themes on GNOME"),
    )
    apply_parser.add_argument(
        "--gtk",
        metavar="NAME",
        help=_("GTK theme name to apply"),
    )
    apply_parser.add_argument(
        "--theme",
        metavar="NAME",
        help=_("Apply unified theme (GTK, Shell, and GTK4/Libadwaita override) with matching name"),
    )
    apply_parser.add_argument(
        "--icon",
        metavar="NAME",
        help=_("Icon theme name to apply"),
    )
    apply_parser.add_argument(
        "--cursor",
        metavar="NAME",
        help=_("Cursor theme name to apply"),
    )
    apply_parser.add_argument(
        "--shell",
        metavar="NAME",
        help=_("GNOME Shell theme name to apply"),
    )
    apply_parser.add_argument(
        "--color-scheme",
        choices=["default", "prefer-dark"],
        help=_("Color scheme preference (default or prefer-dark for GNOME 42+)"),
    )
    apply_parser.add_argument(
        "--no-gtk4-override",
        action="store_true",
        help=_("Do not apply GTK4 override in ~/.config/gtk-4.0 when setting a GTK theme"),
    )
    apply_parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help=_("Do not propagate theme to Snap/Flatpak apps"),
    )
    apply_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("Bypass confirmation prompt when applying incomplete or invalid themes"),
    )

    # Subcommand: install
    install_parser = subparsers.add_parser(
        "install",
        help=_("Install a theme from an archive file (.zip, .tar.*)"),
    )
    install_parser.add_argument(
        "-f",
        "--file",
        required=True,
        metavar="PATH",
        help=_("Path of the archive file to install"),
    )
    install_parser.add_argument(
        "-t",
        "--type",
        choices=["gtk", "icon", "cursor", "shell"],
        help=_("Theme type (if omitted, auto-detection will be performed)"),
    )
    install_parser.add_argument(
        "-n",
        "--name",
        metavar="NAME",
        help=_("Custom name for the destination theme directory"),
    )
    install_parser.add_argument(
        "-y",
        "--overwrite",
        action="store_true",
        help=_("Overwrite theme if destination directory already exists"),
    )
    install_parser.add_argument(
        "--legacy",
        action="store_true",
        help=_(
            "Install into legacy paths ~/.themes and ~/.icons instead of XDG standard (~/.local/share/themes)"
        ),
    )

    # Subcommand: uninstall
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help=_("Uninstall a specific theme from user directories"),
    )
    uninstall_parser.add_argument(
        "-n",
        "--name",
        required=True,
        metavar="NAME",
        help=_("Name of the theme to uninstall"),
    )
    uninstall_parser.add_argument(
        "-t",
        "--type",
        choices=["gtk", "icon", "cursor", "shell"],
        required=True,
        help=_("Type of the theme to uninstall"),
    )
    uninstall_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("Confirm uninstallation without interactive prompt"),
    )

    # Subcommand: preset
    preset_parser = subparsers.add_parser(
        "preset",
        help=_("Manage theme configuration presets and profiles"),
    )
    preset_subparsers = preset_parser.add_subparsers(
        title=_("preset actions"),
        dest="preset_action",
        help=_("Action to perform on preset"),
    )

    # preset list
    preset_subparsers.add_parser(
        "list",
        help=_("List all stored presets"),
    )

    # preset save <name> [--overwrite]
    save_parser = preset_subparsers.add_parser(
        "save",
        help=_("Save current theme combination as a new preset"),
    )
    save_parser.add_argument(
        "name",
        metavar="NAME",
        help=_("Identifier name of the preset to save"),
    )
    save_parser.add_argument(
        "-y",
        "--overwrite",
        action="store_true",
        help=_("Overwrite preset if already existing"),
    )

    # preset apply <name> [--no-gtk4-override]
    apply_preset_parser = preset_subparsers.add_parser(
        "apply",
        help=_("Apply a saved preset"),
    )
    apply_preset_parser.add_argument(
        "name",
        metavar="NAME",
        help=_("Name of the preset to apply"),
    )
    apply_preset_parser.add_argument(
        "--no-gtk4-override",
        action="store_true",
        help=_("Do not apply GTK4 override in ~/.config/gtk-4.0"),
    )
    apply_preset_parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help=_("Do not propagate theme to Snap/Flatpak apps"),
    )

    # preset delete <name> [-y]
    delete_preset_parser = preset_subparsers.add_parser(
        "delete",
        help=_("Delete a stored preset"),
    )
    delete_preset_parser.add_argument(
        "name",
        metavar="NAME",
        help=_("Name of the preset to delete"),
    )
    delete_preset_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("Confirm deletion without interactive prompt"),
    )

    # Subcommand: integrate-desktop
    subparsers.add_parser(
        "integrate-desktop",
        help=_("Install desktop launcher and application icons in ~/.local/share"),
    )

    return parser
