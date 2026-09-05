# SPDX-License-Identifier: GPL-3.0-or-later

"""Modulo GUI Nativa GTK4 / Libadwaita (Fase 5)."""

import logging
import sys
from collections.abc import Sequence

logger = logging.getLogger("gnome_theme_manager.gui_gtk")


def is_gtk_available() -> bool:
    """Verifica se PyGObject, GTK4 e Libadwaita sono disponibili nel sistema.

    Returns:
        True se i moduli PyGObject, Gtk 4.0 e Adw 1 sono importabili, False altrimenti.
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
    """Punto di ingresso per l'avvio della GUI nativa GTK4/Libadwaita.

    Args:
        manager: Istanza opzionale di ThemeManager.
        argv: Argomenti da riga di comando opzionali passati all'applicazione.

    Returns:
        Codice di uscita dell'applicazione (0 per successo, 1 se GTK4 non è disponibile).
    """
    if not is_gtk_available():
        print(
            "\n[ERRORE GUI] Impossibile avviare l'interfaccia grafica GTK4/Libadwaita.\n"
            "Assicurati di essere su un ambiente desktop compatibile e che i pacchetti siano installati:\n"
            "    sudo apt update && sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1\n",
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

    # Convertiamo gli argomenti per l'API GApplication.run()
    args_list = list(argv) if argv is not None else [sys.argv[0]]
    try:
        return app.run(args_list)
    except KeyboardInterrupt:
        logger.debug("Interruzione dell'applicazione da terminale (SIGINT/Ctrl+C).")
        return 130


__all__ = [
    "is_gtk_available",
    "launch_gui",
]
