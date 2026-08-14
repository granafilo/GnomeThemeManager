# SPDX-License-Identifier: GPL-3.0-or-later

"""GnomeThemeManager package.

Manager modulare per temi GTK, icone e cursori su GNOME.
"""

import gettext
import locale
import os

__version__ = "0.9.0b3"

# Percorso delle traduzioni compiled (.mo)
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")
DOMAIN = "gnomethememanager"


def _candidate_languages() -> list[str]:
    """Restituisce l'ordine di preferenza delle lingue dal contesto di runtime."""
    values = []
    for env_var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env_var)
        if not value:
            continue
        for item in value.split(":"):
            code = item.strip()
            if not code:
                continue
            code = code.split(".")[0].split("@")[0]
            if code not in values:
                values.append(code)

    final_languages: list[str] = []
    for language in values:
        final_languages.append(language)
        if "_" in language:
            final_languages.append(language.split("_")[0])
    return final_languages or ["it", "en"]


# Inizializza gettext per Python selezionando la lingua in base all'ambiente di esecuzione.
gettext.bindtextdomain(DOMAIN, LOCALE_DIR)
gettext.textdomain(DOMAIN)
try:
    _translation = gettext.translation(
        DOMAIN,
        localedir=LOCALE_DIR,
        languages=_candidate_languages(),
        fallback=True,
    )
    _ = _translation.gettext
    gettext.install(DOMAIN, localedir=LOCALE_DIR, names=["gettext"])
except (OSError, FileNotFoundError, ValueError):
    _ = gettext.gettext

# Inizializza locale C e gettext a livello di sistema (necessario per tradurre stringhe nei file .ui caricati con Gtk.Builder)
try:
    locale.setlocale(locale.LC_ALL, "")
    locale.bindtextdomain(DOMAIN, LOCALE_DIR)
    locale.bind_textdomain_codeset(DOMAIN, "UTF-8")
except (locale.Error, AttributeError):
    pass
