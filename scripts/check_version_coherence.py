#!/usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later
"""Script per verificare la coerenza della versione del progetto tra tutti i file e i documenti."""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_version(root: Path | None = None) -> int:
    """Verifica la coerenza della versione tra tutti i file sorgente, di packaging e documentazione."""
    base_dir = root or ROOT_DIR

    # 1. Fonte di verità: src/gnome_theme_manager/__init__.py (__version__)
    init_path = base_dir / "src" / "gnome_theme_manager" / "__init__.py"
    if not init_path.is_file():
        print(f"Errore: File non trovato: {init_path}", file=sys.stderr)
        return 1

    init_content = init_path.read_text(encoding="utf-8")
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_content, re.MULTILINE)
    if not m_init:
        print("Errore: __version__ non trovata in __init__.py", file=sys.stderr)
        return 1
    current_ver = m_init.group(1)

    print("Controllo coerenza versione (Target Single Source of Truth):")
    print(f"  gnome_theme_manager.__version__:    {current_ver}")

    # 2. README.md: verifica presenza di '**Current release:** v{current_ver}'
    readme_path = base_dir / "README.md"
    if not readme_path.is_file():
        print(f"Errore: File non trovato: {readme_path}", file=sys.stderr)
        return 1

    readme_content = readme_path.read_text(encoding="utf-8")
    expected_readme_marker = f"**Current release:** v{current_ver}"
    if expected_readme_marker not in readme_content:
        print(
            f"Errore: README.md non contiene il marker atteso '{expected_readme_marker}'",
            file=sys.stderr,
        )
        return 1
    print(f"  README.md (Current release):        v{current_ver} [OK]")

    # 3. CHANGELOG.md: prima entry di versione corrisponde a current_ver
    changelog_path = base_dir / "CHANGELOG.md"
    if not changelog_path.is_file():
        print(f"Errore: File non trovato: {changelog_path}", file=sys.stderr)
        return 1

    changelog_content = changelog_path.read_text(encoding="utf-8")
    m_changelog = re.search(r"^##\s*\[([^\]]+)\]", changelog_content, re.MULTILINE)
    if not m_changelog:
        print("Errore: Nessuna sezione di versione trovata in CHANGELOG.md", file=sys.stderr)
        return 1
    changelog_ver = m_changelog.group(1)
    if changelog_ver != current_ver:
        print(
            f"Errore: La prima entry di CHANGELOG.md è [{changelog_ver}], attesa [{current_ver}]",
            file=sys.stderr,
        )
        return 1
    print(f"  CHANGELOG.md (Prima entry):         [{changelog_ver}] [OK]")

    # 4. scripts/build-appimage.sh
    build_path = base_dir / "scripts" / "build-appimage.sh"
    if build_path.is_file():
        build_content = build_path.read_text(encoding="utf-8")
        m_build = re.search(r'^VERSION="([^"]+)"', build_content, re.MULTILINE)
        if not m_build:
            print("Errore: VERSION non trovata in build-appimage.sh", file=sys.stderr)
            return 1
        build_ver = m_build.group(1)
        if build_ver != current_ver:
            print(
                f"Errore: VERSION in build-appimage.sh è '{build_ver}', attesa '{current_ver}'",
                file=sys.stderr,
            )
            return 1
        print(f"  scripts/build-appimage.sh:          {build_ver} [OK]")

    # 5. appimage/io.github.granafilo.ThemeManager.metainfo.xml (prima release)
    xml_path = base_dir / "appimage" / "io.github.granafilo.ThemeManager.metainfo.xml"
    if xml_path.is_file():
        xml_content = xml_path.read_text(encoding="utf-8")
        m_xml = re.search(r'<release\s+version="([^"]+)"', xml_content)
        if not m_xml:
            print("Errore: <release version=...> non trovata in metainfo.xml", file=sys.stderr)
            return 1
        xml_ver = m_xml.group(1)
        if xml_ver != current_ver:
            print(
                f"Errore: Versione in metainfo.xml è '{xml_ver}', attesa '{current_ver}'",
                file=sys.stderr,
            )
            return 1
        print(f"  metainfo.xml (AppStream):           {xml_ver} [OK]")

    print("✓ Tutte le versioni nei file e documenti sono coerenti!")
    return 0


if __name__ == "__main__":
    sys.exit(check_version())
