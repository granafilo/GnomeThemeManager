# SPDX-License-Identifier: GPL-3.0-or-later

"""Test per il sistema di traduzioni (i18n)."""

import gettext
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

# Trova il percorso locale_dir
ROOT_DIR = Path(__file__).parent.parent
LOCALE_DIR = ROOT_DIR / "src" / "gnome_theme_manager" / "locale"

def test_mo_files_exist():
    """Verifica che i file .mo per it ed en siano stati compilati e siano presenti."""
    it_mo = LOCALE_DIR / "it" / "LC_MESSAGES" / "gnomethememanager.mo"
    en_mo = LOCALE_DIR / "en" / "LC_MESSAGES" / "gnomethememanager.mo"
    
    assert it_mo.is_file(), f"File .mo italiano non trovato in {it_mo}"
    assert en_mo.is_file(), f"File .mo inglese non trovato in {en_mo}"
    assert it_mo.stat().st_size > 0, "Il file .mo italiano è vuoto"
    assert en_mo.stat().st_size > 0, "Il file .mo inglese è vuoto"

def test_translation_loading_it():
    """Verifica che la traduzione italiana venga caricata e traduca correttamente."""
    trans = gettext.translation(
        "gnomethememanager",
        localedir=str(LOCALE_DIR),
        languages=["it"],
        fallback=False
    )
    
    # Test della traduzione di una stringa
    orig = "\nTemi attualmente attivi su GNOME:"
    translated = trans.gettext(orig)
    assert translated == "\nTemi attualmente attivi su GNOME:"

    # Test della traduzione di un'altra stringa
    orig_set = "Non impostato"
    assert trans.gettext(orig_set) == "Non impostato"
    assert trans.gettext("Mostra i temi attualmente applicati sul desktop GNOME") == "Mostra i temi attualmente applicati sul desktop GNOME"

def test_translation_loading_en():
    """Verifica che la traduzione inglese traduca correttamente dall'italiano all'inglese."""
    trans = gettext.translation(
        "gnomethememanager",
        localedir=str(LOCALE_DIR),
        languages=["en"],
        fallback=False
    )
    
    # Verifica le stringhe tradotte
    assert trans.gettext("\nTemi attualmente attivi su GNOME:") == "\nCurrently active GNOME themes:"
    assert trans.gettext("Non impostato") == "Not set"
    assert trans.gettext("Default di sistema") == "System Default"
    assert trans.gettext("Mostra i temi attualmente applicati sul desktop GNOME") == "Show currently applied themes on GNOME desktop"

def test_translation_fallback():
    """Verifica che il fallback restituisca la stringa originale se la lingua non esiste o non ha traduzioni."""
    trans = gettext.translation(
        "gnomethememanager",
        localedir=str(LOCALE_DIR),
        languages=["fr"],
        fallback=True
    )
    
    orig = "Test stringa non tradotta"
    assert trans.gettext(orig) == orig


def test_appimage_build_includes_locale_directory():
    """Verifica che la build AppImage copi la directory delle traduzioni e che il package data sia configurato."""
    pyproject_data = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    assert '"gnome_theme_manager" = ["locale/**/*", "locale/*/LC_MESSAGES/*.mo"]' in pyproject_data

    build_script = (ROOT_DIR / "scripts" / "build-appimage.sh").read_text(encoding="utf-8")
    assert 'cp -r "$ROOT_DIR/src/gnome_theme_manager/locale"' in build_script
    assert 'TEXTDOMAINDIR' in build_script


def test_gtk_builder_uses_translation_domain():
    """Verifica che i builder GTK usino il dominio delle traduzioni corretto per il parsing dei file .ui."""
    for relative_path in [
        "src/gnome_theme_manager/gui_gtk/window.py",
        "src/gnome_theme_manager/gui_gtk/pages/status.py",
        "src/gnome_theme_manager/gui_gtk/pages/themes.py",
    ]:
        source = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
        assert 'set_translation_domain("gnomethememanager")' in source


def test_english_catalogue_has_key_gui_translations():
    """Verifica che le stringhe principali della GUI siano effettivamente tradotte in inglese."""
    en_po = (ROOT_DIR / "po" / "en.po").read_text(encoding="utf-8")
    translations = {
        "Stato attuale": "Current status",
        "Configurazione corrente letta tramite GSettings.": "Current configuration read via GSettings.",
        "Compatibilità con le applicazioni moderne GNOME.": "Compatibility with modern GNOME applications.",
        "GSettings / Gio": "GSettings / Gio",
        "Cartella Temi Utente": "User Themes Folder",
        "Cartella Icone Utente": "User Icons Folder",
        "Ambiente Desktop e Percorsi": "Desktop Environment and Paths",
        "Temi Attivi su GNOME": "Currently Active GNOME Themes",
    }
    for msgid, expected in translations.items():
        pattern = f'msgid "{msgid}"\nmsgstr "{expected}"'
        assert pattern in en_po, f"Voce mancante in en.po: {msgid}"


def test_english_catalogue_has_only_intentional_identical_entries():
    """Verifica che le voci msgid==msgstr in en.po siano solo termini neutri/intenzionali."""
    en_po = (ROOT_DIR / "po" / "en.po").read_text(encoding="utf-8")

    entries = []
    msgid = None
    msgstr = None
    for line in en_po.splitlines():
        if line.startswith("msgid "):
            if msgid is not None:
                entries.append((msgid, msgstr if msgstr is not None else ""))
            msgid = line[len("msgid ") :].strip().strip('"')
            msgstr = None
        elif line.startswith("msgstr "):
            msgstr = line[len("msgstr ") :].strip().strip('"')
    if msgid is not None:
        entries.append((msgid, msgstr if msgstr is not None else ""))

    identical = {mid for mid, mstr in entries if mid and mid == mstr}
    allowed = {
        "-",
        "Flatpak",
        "GNOME Shell",
        "GSettings / Gio",
        "GTK",
        "GTK4 / Libadwaita",
        "Gnome Theme Manager",
        "No",
        "OK",
        "Preset",
        "Snap",
        "System",
        "User",
        "~/.local/share/icons",
        "~/.local/share/themes",
    }
    assert identical == allowed, (
        "Voci non tradotte inattese in en.po: "
        f"{sorted(identical - allowed)}"
    )
