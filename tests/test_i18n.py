# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the translation system (i18n)."""

import gettext
from pathlib import Path

# Find locale_dir path
ROOT_DIR = Path(__file__).parent.parent
LOCALE_DIR = ROOT_DIR / "src" / "gnome_theme_manager" / "locale"


def test_mo_files_exist():
    """Verify that .mo files for it and en have been compiled and are present."""
    it_mo = LOCALE_DIR / "it" / "LC_MESSAGES" / "gnomethememanager.mo"
    en_mo = LOCALE_DIR / "en" / "LC_MESSAGES" / "gnomethememanager.mo"

    assert it_mo.is_file(), f"File .mo italiano non trovato in {it_mo}"
    assert en_mo.is_file(), f"File .mo inglese non trovato in {en_mo}"
    assert it_mo.stat().st_size > 0, "Il file .mo italiano è vuoto"
    assert en_mo.stat().st_size > 0, "Il file .mo inglese è vuoto"


def test_translation_loading_it():
    """Verify that Italian translation loads and translates from English (source) to Italian."""
    trans = gettext.translation(
        "gnomethememanager", localedir=str(LOCALE_DIR), languages=["it"], fallback=False
    )

    orig = "\nCurrently active GNOME themes:"
    assert trans.gettext(orig) == "\nTemi attualmente attivi su GNOME:"

    orig_set = "Not set"
    assert trans.gettext(orig_set) == "Non impostato"
    assert (
        trans.gettext("Show currently applied themes on GNOME desktop")
        == "Mostra i temi attualmente applicati sul desktop GNOME"
    )
    assert trans.gettext("Global Themes") == "Temi Globali"
    assert trans.gettext("Save Current Configuration") == "Salva configurazione attuale"
    assert trans.gettext("Delete Global Theme") == "Elimina Global Theme"


def test_translation_loading_en():
    """Verify that English translation maintains source strings in English."""
    trans = gettext.translation(
        "gnomethememanager", localedir=str(LOCALE_DIR), languages=["en"], fallback=False
    )

    assert trans.gettext("\nCurrently active GNOME themes:") == "\nCurrently active GNOME themes:"
    assert trans.gettext("Not set") == "Not set"
    assert trans.gettext("System Default") == "System Default"
    assert (
        trans.gettext("Show currently applied themes on GNOME desktop")
        == "Show currently applied themes on GNOME desktop"
    )
    assert trans.gettext("Global Themes") == "Global Themes"
    assert trans.gettext("Save Current Configuration") == "Save Current Configuration"
    assert trans.gettext("Delete Global Theme") == "Delete Global Theme"


def test_translation_fallback():
    """Verify that fallback returns original string if language does not exist or lacks translations."""
    trans = gettext.translation(
        "gnomethememanager", localedir=str(LOCALE_DIR), languages=["fr"], fallback=True
    )

    orig = "Untranslated test string"
    assert trans.gettext(orig) == orig


def test_flatpak_build_includes_locale_directory():
    """Verify that Flatpak build compiles translations and package data is configured in pyproject.toml."""
    pyproject_data = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    assert '"gnome_theme_manager" = ["locale/**/*", "locale/*/LC_MESSAGES/*.mo"]' in pyproject_data

    build_script = (ROOT_DIR / "scripts" / "build-flatpak.sh").read_text(encoding="utf-8")
    assert "compile_translations.py" in build_script


def test_gtk_builder_uses_translation_domain():
    """Verify that GTK builders use the correct translation domain when parsing .ui files."""
    for relative_path in [
        "src/gnome_theme_manager/gui_gtk/window.py",
        "src/gnome_theme_manager/gui_gtk/pages/installer.py",
        "src/gnome_theme_manager/gui_gtk/pages/status.py",
        "src/gnome_theme_manager/gui_gtk/pages/themes.py",
        "src/gnome_theme_manager/gui_gtk/pages/global_themes.py",
        "src/gnome_theme_manager/gui_gtk/pages/extensions.py",
        "src/gnome_theme_manager/gui_gtk/pages/terminal.py",
        "src/gnome_theme_manager/gui_gtk/pages/fonts.py",
        "src/gnome_theme_manager/gui_gtk/pages/editor_view.py",
        "src/gnome_theme_manager/gui_gtk/pages/sandbox.py",
        "src/gnome_theme_manager/gui_gtk/pages/store.py",
    ]:
        source = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
        assert 'set_translation_domain("gnomethememanager")' in source


def test_english_catalogue_has_key_gui_translations():
    """Verify that key GUI strings are present in the en.po catalogue."""
    en_po = (ROOT_DIR / "po" / "en.po").read_text(encoding="utf-8")
    translations = {
        "Current Status": "Current Status",
        "Desktop Environment and Paths": "Desktop Environment and Paths",
        "Currently Active GNOME Themes": "Currently Active GNOME Themes",
        "GSettings / Gio": "GSettings / Gio",
        "User Themes Folder": "User Themes Folder",
        "User Icons Folder": "User Icons Folder",
    }
    for msgid, expected in translations.items():
        pattern = f'msgid "{msgid}"\nmsgstr "{expected}"'
        assert pattern in en_po, f"Voce mancante in en.po: {msgid}"


def test_italian_catalogue_has_key_gui_translations():
    """Verify that key GUI strings have complete Italian translation in it.po."""
    it_po = (ROOT_DIR / "po" / "it.po").read_text(encoding="utf-8")
    translations = {
        "Current Status": "Stato attuale",
        "Desktop Environment and Paths": "Ambiente Desktop e Percorsi",
        "Currently Active GNOME Themes": "Temi Attivi su GNOME",
        "GSettings / Gio": "GSettings / Gio",
        "User Themes Folder": "Cartella Temi Utente",
        "User Icons Folder": "Cartella Icone Utente",
    }
    for msgid, expected in translations.items():
        pattern = f'msgid "{msgid}"\nmsgstr "{expected}"'
        assert pattern in it_po, f"Voce mancante o errata in it.po: {msgid}"
