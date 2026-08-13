# SPDX-License-Identifier: GPL-3.0-or-later

"""GnomeThemeManager package.

Manager modulare per temi GTK, icone e cursori su GNOME.
"""

import gettext
import locale
import os

__version__ = "0.9.0b2"

# Percorso delle traduzioni compiled (.mo)
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")

# Inizializza gettext per Python
gettext.bindtextdomain("gnomethememanager", LOCALE_DIR)
gettext.textdomain("gnomethememanager")
_ = gettext.gettext

# Inizializza locale C e gettext a livello di sistema (necessario per tradurre stringhe nei file .ui caricati con Gtk.Builder)
try:
    locale.setlocale(locale.LC_ALL, "")
    locale.bindtextdomain("gnomethememanager", LOCALE_DIR)
    locale.bind_textdomain_codeset("gnomethememanager", "UTF-8")
except (locale.Error, AttributeError):
    pass


