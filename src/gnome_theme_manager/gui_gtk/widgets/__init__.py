# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom GUI widgets for GNOME Theme Manager."""

from .flatpak_dialog import FlatpakPropagationDialog
from .flatpak_wizard import FlatpakWizardDialog
from .font_utils import (
    install_glib_font_dialog_filter,
    safe_set_font_desc,
    suppress_font_dialog_critical,
)

__all__ = [
    "FlatpakPropagationDialog",
    "FlatpakWizardDialog",
    "install_glib_font_dialog_filter",
    "safe_set_font_desc",
    "suppress_font_dialog_critical",
]

