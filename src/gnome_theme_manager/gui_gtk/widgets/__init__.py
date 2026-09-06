# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom GUI widgets for GNOME Theme Manager."""

from .font_utils import (
    install_glib_font_dialog_filter,
    safe_set_font_desc,
    suppress_font_dialog_critical,
)

__all__ = [
    "install_glib_font_dialog_filter",
    "safe_set_font_desc",
    "suppress_font_dialog_critical",
]
