# SPDX-License-Identifier: GPL-3.0-or-later

"""GnomeThemeManager package.

Modular manager for GTK themes, icons, cursors, and GNOME Shell themes.
"""

import gettext
import locale
import os

__version__ = "1.3.0"

# Path to compiled translations (.mo)
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")
DOMAIN = "gnomethememanager"


def _candidate_languages() -> list[str]:
    """Return language preference order from runtime environment context."""
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
    return final_languages or ["en"]


def get_translation() -> gettext.NullTranslations:
    """Return active gettext translation object based on environment variables."""
    try:
        return gettext.translation(
            DOMAIN,
            localedir=LOCALE_DIR,
            languages=_candidate_languages(),
            fallback=True,
        )
    except (OSError, FileNotFoundError, ValueError):
        return gettext.NullTranslations()


def _(message: str) -> str:
    """Translate message dynamically using current runtime translation."""
    return get_translation().gettext(message)


# Initialize C locale and system gettext (required to translate strings in .ui templates loaded via Gtk.Builder)
try:
    locale.setlocale(locale.LC_ALL, "")
    locale.bindtextdomain(DOMAIN, LOCALE_DIR)
    locale.bind_textdomain_codeset(DOMAIN, "UTF-8")
except (locale.Error, AttributeError):
    pass
