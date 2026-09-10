# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities for handling GTK font dialogs and buttons safely."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import GLib, Gtk, Pango


def _glib_gio_log_filter(
    domain: str,
    level: GLib.LogLevelFlags,
    message: str,
    user_data: Any = None,
) -> None:
    """Filter known upstream GTK 4.14 critical assertions on GtkFontDialogButton.

    Upstream GTK 4.14 has a bug in gtkfontdialogbutton.c where it invokes
    g_list_model_get_n_items() on a NULL PangoFontFamily when the configured
    font family is not installed in the system fontmap.
    """
    if domain == "GLib-GIO" and "g_list_model_get_n_items" in message:
        return
    GLib.log_default_handler(domain, level, message, user_data)


def install_glib_font_dialog_filter() -> None:
    """Install persistent GLib log handler to filter upstream GTK 4.14 critical assertions."""
    GLib.log_set_handler(
        "GLib-GIO",
        GLib.LogLevelFlags.LEVEL_CRITICAL,
        _glib_gio_log_filter,
        None,
    )


@contextmanager
def suppress_font_dialog_critical() -> Iterator[None]:
    """Context manager to temporarily suppress upstream GTK 4.14 critical assertions."""
    handler_id = None
    try:
        handler_id = GLib.log_set_handler(
            "GLib-GIO",
            GLib.LogLevelFlags.LEVEL_CRITICAL,
            _glib_gio_log_filter,
            None,
        )
        yield
    finally:
        if handler_id is not None:
            GLib.log_remove_handler("GLib-GIO", handler_id)


def safe_set_font_desc(
    btn: Gtk.FontDialogButton,
    desc: Pango.FontDescription,
) -> None:
    """Safely set Pango.FontDescription on a Gtk.FontDialogButton."""
    with suppress_font_dialog_critical():
        btn.set_font_desc(desc)
