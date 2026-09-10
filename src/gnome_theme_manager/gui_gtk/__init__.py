# SPDX-License-Identifier: GPL-3.0-or-later

"""Native GTK4 / Libadwaita GUI module."""

import logging
import sys
from collections.abc import Sequence

logger = logging.getLogger("gnome_theme_manager.gui_gtk")


def is_gtk_available() -> bool:
    """Check if PyGObject, GTK4, and Libadwaita are available on the system.

    Returns:
        True if PyGObject, Gtk 4.0, and Adw 1 modules can be imported, False otherwise.
    """
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk  # noqa: F401

        Adw.init()
        return True
    except Exception:
        return False


def launch_gui(
    manager: object | None = None,
    argv: Sequence[str] | None = None,
) -> int:
    """Entry point for launching the native GTK4/Libadwaita GUI.

    Args:
        manager: Optional ThemeManager instance.
        argv: Optional command line arguments passed to the application.

    Returns:
        Application exit code (0 for success, 1 if GTK4 is not available).
    """
    if not is_gtk_available():
        from ..core.os_detector import get_install_command

        install_cmd = get_install_command("gtk4")
        print(
            "\n[GUI ERROR] Unable to start GTK4/Libadwaita graphical interface.\n"
            "Ensure you are running in a compatible desktop environment with the required packages installed:\n"
            f"    {install_cmd}\n",
            file=sys.stderr,
        )
        return 1

    from gi.repository import GLib

    from ..core.manager import ThemeManager
    from .app import GnomeThemeApplication

    GLib.set_prgname("io.github.granafilo.ThemeManager")
    GLib.set_application_name("GNOME Theme Manager")

    theme_mgr = manager if isinstance(manager, ThemeManager) else ThemeManager()
    app = GnomeThemeApplication(manager=theme_mgr)

    # Convert arguments for the GApplication.run() API
    args_list = list(argv) if argv is not None else [sys.argv[0]]
    try:
        return app.run(args_list)
    except KeyboardInterrupt:
        logger.debug("Application interrupted from terminal (SIGINT/Ctrl+C).")
        return 130


__all__ = [
    "is_gtk_available",
    "launch_gui",
]
