# SPDX-License-Identifier: GPL-3.0-or-later

"""Logical entry point for the Command Line Interface (CLI).

Handles command routing (`current`, `list`, `apply`, `install`, `uninstall`, `preset`),
delegating domain business logic to `ThemeManager` while managing user I/O
(ASCII formatting, status messaging, exception handling).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from gnome_theme_manager import _

from ..core.errors import (
    ArchiveExtractionError,
    GnomeThemeManagerError,
    GSettingsUnavailableError,
    ThemeNotFoundError,
    ThemeValidationError,
)
from ..core.manager import ThemeManager
from ..core.models import ApplyResult, Theme, ThemeSet, ThemeType
from .args import create_parser


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format rows into an aligned ASCII table.

    Args:
        headers: Column header strings.
        rows: Rows list of strings.

    Returns:
        Formatted ASCII table string.
    """
    if not rows:
        return _("No items to display.")

    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(cell)))

    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    data_lines = [
        "| " + " | ".join(f"{cell!s:<{w}}" for cell, w in zip(row, col_widths)) + " |"
        for row in rows
    ]

    return "\n".join([separator, header_line, separator] + data_lines + [separator])


# -----------------------------------------------------------------------------
# Handlers for CLI commands
# -----------------------------------------------------------------------------


def handle_current_command(manager: ThemeManager) -> int:
    """Handle `current` command showing active desktop themes."""
    current = manager.get_current_themes()
    status = manager.get_system_status()

    print(_("\nCurrently active GNOME themes:"))
    print(f"  {_('GTK Theme (Applications)')}:  {current.gtk_theme or _('Not set')}")
    print(f"  {_('Icon Theme')}:               {current.icon_theme or _('Not set')}")
    print(f"  {_('Cursor Theme')}:             {current.cursor_theme or _('Not set')}")

    if status.shell_theme_supported:
        shell_val = current.shell_theme if current.shell_theme else _("System Default")
        print(f"  {_('GNOME Shell Theme')}:         {shell_val}")
    else:
        print(_("  GNOME Shell Theme:         Not managed (requires 'User Themes' extension)"))

    if current.color_scheme:
        print(f"  {_('Color Scheme')}:            {current.color_scheme}")
    print()
    return 0


def handle_sandbox_status_command(manager: ThemeManager) -> int:
    """Handle `sandbox-status` command showing Snap and Flatpak integration status."""
    status = manager.get_system_status()
    sb = status.sandbox_status

    print(_("\n=== Sandbox Integration Status (Snap & Flatpak) ==="))
    if sb is not None:
        snap_str = _("✅ Available") if sb.snap_available else _("❌ Not available")
        snap_themes_str = (
            _("✅ Installed") if sb.snap_gtk_common_themes_installed else _("❌ Not installed")
        )
        flatpak_str = _("✅ Available") if sb.flatpak_available else _("❌ Not available")
        flatpak_ov_str = (
            _("✅ Active") if sb.flatpak_filesystem_override_active else _("❌ Not active")
        )

        print(f"  Snap:    {snap_str:<16} | gtk-common-themes:   {snap_themes_str}")
        print(f"  Flatpak: {flatpak_str:<16} | Filesystem override: {flatpak_ov_str}")
    else:
        print(_("  Sandbox status unavailable."))
    print()
    return 0


def handle_list_command(manager: ThemeManager, theme_type: str, user_only: bool) -> int:
    """Handle `list` command scanning and listing available themes.

    Args:
        manager: ThemeManager instance.
        theme_type: Theme type filter ('all', 'gtk', 'icon', 'cursor', 'shell').
        user_only: If True, show only user-installed themes.
    """
    t_type = ThemeType(theme_type) if theme_type != "all" else None
    themes: list[Theme] = manager.list_themes(theme_type=t_type, user_only=user_only)

    if not themes:
        print(
            _("\nNo theme found for type '{theme_type}' (user_only={user_only}).\n").format(
                theme_type=theme_type, user_only=user_only
            )
        )
        return 0

    headers = [_("NAME"), _("TYPE"), _("ORIGIN"), _("PATH")]
    rows = [
        [
            t.name,
            t.theme_type.value,
            _("User") if t.is_user_level else _("System"),
            str(t.path),
        ]
        for t in themes
    ]

    print()
    print(format_table(headers, rows))
    print(_("\nTotal themes found: {count}\n").format(count=len(themes)))
    return 0


def _print_apply_result(result: ApplyResult, no_gtk4_override: bool = False) -> None:
    """Print readable summary of applied themes."""
    print(_("\n✓ Changes applied successfully:"))
    if result.gtk_theme:
        print(_("  - GTK Theme set to:         {theme}").format(theme=result.gtk_theme))
        if result.gtk4_override_applied:
            print(_("    └─ GTK4/Libadwaita override applied in ~/.config/gtk-4.0"))
        elif not no_gtk4_override:
            print(_("    └─ No GTK4 file found in theme (applied to GTK2/GTK3 only)"))
    if result.icon_theme:
        print(_("  - Icon Theme set to:       {theme}").format(theme=result.icon_theme))
    if result.cursor_theme:
        print(_("  - Cursor Theme set to:     {theme}").format(theme=result.cursor_theme))
    if result.shell_theme:
        print(_("  - GNOME Shell Theme set to: {theme}").format(theme=result.shell_theme))
    if result.color_scheme:
        print(_("  - Color Scheme set to:    {scheme}").format(scheme=result.color_scheme))

    if result.sandbox_propagation:
        sb = result.sandbox_propagation
        if sb.flatpak_success:
            print(_("  - Flatpak Propagation:          ✓ Filesystem access and variables set"))
        if sb.snap_success and not sb.warnings:
            print(
                _(
                    "  - Snap Propagation:             ✓ Compatibility verified with gtk-common-themes"
                )
            )

    for warning in result.warnings:
        print(f"\n{_('[WARNING]')} {warning}")
    print()


def handle_apply_command(
    manager: ThemeManager,
    gtk: str | None,
    icon: str | None,
    cursor: str | None,
    shell: str | None,
    color_scheme: str | None,
    no_gtk4_override: bool = False,
    theme: str | None = None,
    no_sandbox: bool = False,
) -> int:
    """Handle `apply` command validating theme presence and applying them.

    Args:
        manager: ThemeManager instance.
        gtk: GTK theme name (optional).
        icon: Icon theme name (optional).
        cursor: Cursor theme name (optional).
        shell: GNOME Shell theme name (optional).
        color_scheme: Color scheme value (optional).
        no_gtk4_override: If True, do not apply symlink override in ~/.config/gtk-4.0.
        theme: Unified theme name for GTK and Shell (optional).
        no_sandbox: If True, do not propagate to Flatpak/Snap.
    """
    if not any([gtk, icon, cursor, shell, color_scheme, theme]):
        print(
            _(
                "Error: Specify at least one option to apply "
                "(--gtk, --theme, --icon, --cursor, --shell or --color-scheme)."
            ),
            file=sys.stderr,
        )
        return 1

    if theme is not None:
        has_gtk = bool(manager.find_theme(theme, ThemeType.GTK))
        has_shell = bool(manager.find_theme(theme, ThemeType.SHELL))

        if not has_gtk and not has_shell:
            raise ThemeNotFoundError(
                _("Theme '{theme}' was not found as GTK or GNOME Shell on the system.").format(
                    theme=theme
                )
            )

        if has_gtk:
            gtk = theme
        if has_shell:
            shell = theme

    target_set = ThemeSet(
        gtk_theme=gtk,
        icon_theme=icon,
        cursor_theme=cursor,
        color_scheme=color_scheme,
        shell_theme=shell,
    )

    result = manager.apply_themes(
        target_set,
        apply_gtk4_override=not no_gtk4_override,
        propagate_sandbox=not no_sandbox,
    )
    _print_apply_result(result, no_gtk4_override=no_gtk4_override)
    return 0


def handle_install_command(
    manager: ThemeManager,
    archive_file: str,
    theme_type_str: str | None = None,
    custom_name: str | None = None,
    overwrite: bool = False,
    target_dir: str | Path | None = None,
) -> int:
    """Handle `install` command extracting and installing themes from an archive.

    Args:
        manager: ThemeManager instance.
        archive_file: Path of the archive file to install.
        theme_type_str: Optional theme type ('gtk', 'icon', 'cursor', 'shell').
        custom_name: Custom destination folder name.
        overwrite: If True, overwrite existing themes.
        target_dir: Installation destination ('xdg', 'legacy', or Path).
    """
    archive_path = Path(archive_file)
    theme_type = ThemeType(theme_type_str) if theme_type_str else None

    installed_themes = manager.install_theme_archive(
        archive_path=archive_path,
        theme_type=theme_type,
        custom_name=custom_name,
        overwrite=overwrite,
        target_dir=target_dir,
    )

    headers = [_("THEME NAME"), _("TYPE"), _("INSTALLED PATH")]
    rows = [[t.name, t.theme_type.value, str(t.path)] for t in installed_themes]

    print(
        _("\n✓ Installation completed successfully ({count} theme(s) installed):").format(
            count=len(installed_themes)
        )
    )
    print(format_table(headers, rows))
    print()
    return 0


def handle_uninstall_command(
    manager: ThemeManager,
    name: str,
    theme_type_str: str,
    assume_yes: bool = False,
) -> int:
    """Handle `uninstall` command removing user themes.

    Args:
        manager: ThemeManager instance.
        name: Name of the theme to uninstall.
        theme_type_str: Theme type ('gtk', 'icon', 'cursor', 'shell').
        assume_yes: If True, uninstall without interactive confirmation prompt.
    """
    theme_type = ThemeType(theme_type_str)

    if not assume_yes:
        confirm = (
            input(
                _("Are you sure you want to uninstall theme '{name}' ({type})? [y/N]: ").format(
                    name=name, type=theme_type.value
                )
            )
            .strip()
            .lower()
        )
        if confirm not in ("y", "yes", "s", "si"):
            print(_("\nOperation cancelled by user.\n"))
            return 0

    manager.uninstall_theme(name=name, theme_type=theme_type)
    print(
        _("\n✓ Theme '{name}' ({type}) uninstalled successfully.\n").format(
            name=name, type=theme_type.value
        )
    )
    return 0


def handle_preset_command(manager: ThemeManager, args: argparse.Namespace) -> int:
    """Handle `preset` actions (list, save, apply, delete).

    Args:
        manager: ThemeManager instance.
        args: Parsed CLI arguments.
    """
    action = getattr(args, "preset_action", None)

    if action == "list":
        presets = manager.list_presets()
        if not presets:
            print(_("\nNo presets saved.\n"))
            return 0

        rows = [[p] for p in presets]
        print(_("\nAvailable saved presets:"))
        print(format_table([_("PRESET NAME")], rows))
        print(_("\nTotal presets: {count}\n").format(count=len(presets)))
        return 0

    elif action == "save":
        saved_path = manager.save_current_as_preset(args.name, overwrite=args.overwrite)
        print(
            _("\n✓ Preset '{name}' saved successfully in:\n  {path}\n").format(
                name=args.name, path=saved_path
            )
        )
        return 0

    elif action == "apply":
        no_sb = getattr(args, "no_sandbox", False)
        result = manager.apply_preset(
            args.name,
            apply_gtk4_override=not args.no_gtk4_override,
            propagate_sandbox=not no_sb,
        )
        print(_("\n✓ Preset '{name}' applied successfully:").format(name=args.name))
        _print_apply_result(result, no_gtk4_override=args.no_gtk4_override)
        return 0

    elif action == "delete":
        if not args.yes:
            confirm = (
                input(
                    _("Are you sure you want to delete preset '{name}'? [y/N]: ").format(
                        name=args.name
                    )
                )
                .strip()
                .lower()
            )
            if confirm not in ("y", "yes", "s", "si"):
                print(_("\nOperation cancelled by user.\n"))
                return 0

        manager.delete_preset(args.name)
        print(_("\n✓ Preset '{name}' deleted successfully.\n").format(name=args.name))
        return 0

    else:
        print(
            _("Error: Preset action not specified (use 'list', 'save', 'apply' or 'delete')."),
            file=sys.stderr,
        )
        return 1


# -----------------------------------------------------------------------------
# Main Router
# -----------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Run CLI application.

    Args:
        argv: Optional command line arguments.

    Returns:
        Exit code: 0 for success, 1 for application errors.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        if getattr(args, "gui", False) or args.command == "gui":
            try:
                from ..gui_gtk import launch_gui as launch_gui_gtk
            except (ImportError, ModuleNotFoundError) as err:
                print(
                    _(
                        "\n[GTK4 GUI ERROR] GTK4/Libadwaita is required to launch the graphical interface. Details: {err}\n"
                        "Install required dependencies with:\n"
                        "    sudo apt update && sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1\n"
                    ).format(err=err),
                    file=sys.stderr,
                )
                return 1

            manager = ThemeManager()
            return launch_gui_gtk(manager=manager)

        if not args.command:
            parser.print_help()
            return 0

        manager = ThemeManager()

        if args.command == "current":
            return handle_current_command(manager)
        elif args.command == "sandbox-status":
            return handle_sandbox_status_command(manager)
        elif args.command == "list":
            return handle_list_command(manager, theme_type=args.type, user_only=args.user_only)
        elif args.command == "apply":
            return handle_apply_command(
                manager=manager,
                gtk=args.gtk,
                icon=args.icon,
                cursor=args.cursor,
                shell=args.shell,
                color_scheme=args.color_scheme,
                no_gtk4_override=args.no_gtk4_override,
                theme=args.theme,
                no_sandbox=getattr(args, "no_sandbox", False),
            )
        elif args.command == "install":
            target_dir = "legacy" if getattr(args, "legacy", False) else "xdg"
            return handle_install_command(
                manager=manager,
                archive_file=args.file,
                theme_type_str=args.type,
                custom_name=args.name,
                overwrite=args.overwrite,
                target_dir=target_dir,
            )
        elif args.command == "uninstall":
            return handle_uninstall_command(
                manager=manager,
                name=args.name,
                theme_type_str=args.type,
                assume_yes=args.yes,
            )
        elif args.command == "preset":
            return handle_preset_command(manager=manager, args=args)
        else:
            parser.print_help()
            return 0

    except KeyboardInterrupt:
        return 130
    except GSettingsUnavailableError as err:
        print(f"\n{_('[GSETTINGS ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except ThemeNotFoundError as err:
        print(f"\n{_('[THEME ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except ArchiveExtractionError as err:
        print(f"\n{_('[ARCHIVE EXTRACTION ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except ThemeValidationError as err:
        print(f"\n{_('[THEME VALIDATION ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except FileExistsError as err:
        print(f"\n{_('[FILE ALREADY EXISTS ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except FileNotFoundError as err:
        print(f"\n{_('[FILE NOT FOUND ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except ValueError as err:
        print(f"\n{_('[INVALID VALUE ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except GnomeThemeManagerError as err:
        print(f"\n{_('[GNOME THEME MANAGER ERROR]')} {err}\n", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"\n{_('[UNEXPECTED ERROR]')} {err}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
