#!/usr/bin/env python3
"""Script per verificare la coerenza delle versioni nei file di configurazione."""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_version():
    # 1. pyproject.toml
    pyproject_path = ROOT_DIR / "pyproject.toml"
    pyproject_content = pyproject_path.read_text(encoding="utf-8")
    m_pyproject = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_content, re.MULTILINE)
    if not m_pyproject:
        print("Errore: Versione non trovata in pyproject.toml", file=sys.stderr)
        return 1
    pyproject_ver = m_pyproject.group(1)

    # 2. src/gnome_theme_manager/__init__.py
    init_path = ROOT_DIR / "src" / "gnome_theme_manager" / "__init__.py"
    init_content = init_path.read_text(encoding="utf-8")
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_content, re.MULTILINE)
    if not m_init:
        print("Errore: __version__ non trovata in __init__.py", file=sys.stderr)
        return 1
    init_ver = m_init.group(1)

    # 3. scripts/build-appimage.sh
    build_path = ROOT_DIR / "scripts" / "build-appimage.sh"
    build_content = build_path.read_text(encoding="utf-8")
    m_build = re.search(r'^VERSION="([^"]+)"', build_content, re.MULTILINE)
    if not m_build:
        print("Errore: VERSION non trovata in build-appimage.sh", file=sys.stderr)
        return 1
    build_ver = m_build.group(1)

    # 4. appimage/io.github.granafilo.ThemeManager.metainfo.xml
    xml_path = ROOT_DIR / "appimage" / "io.github.granafilo.ThemeManager.metainfo.xml"
    xml_content = xml_path.read_text(encoding="utf-8")
    m_xml = re.search(r'<release\s+version="([^"]+)"', xml_content)
    if not m_xml:
        print("Errore: <release version=...> non trovata in metainfo.xml", file=sys.stderr)
        return 1
    xml_ver = m_xml.group(1)

    print("Verifica coerenza versioni:")
    print(f"  pyproject.toml:                     {pyproject_ver}")
    print(f"  gnome_theme_manager/__init__.py:    {init_ver}")
    print(f"  build-appimage.sh:                  {build_ver}")
    print(f"  metainfo.xml (AppStream):           {xml_ver}")

    # Controlli di corrispondenza esatta
    if pyproject_ver != "0.9.0b2":
        print(f"Errore: versione pyproject.toml non è 0.9.0b2 (trovato: {pyproject_ver})", file=sys.stderr)
        return 1
    if init_ver != "0.9.0b2":
        print(f"Errore: versione __init__.py non è 0.9.0b2 (trovato: {init_ver})", file=sys.stderr)
        return 1
    if build_ver != "0.9.0-beta2":
        print(f"Errore: versione build-appimage.sh non è 0.9.0-beta2 (trovato: {build_ver})", file=sys.stderr)
        return 1
    if xml_ver != "0.9.0~beta2":
        print(f"Errore: versione metainfo.xml non è 0.9.0~beta2 (trovato: {xml_ver})", file=sys.stderr)
        return 1

    print("✓ Tutte le versioni sono coerenti!")
    return 0


if __name__ == "__main__":
    sys.exit(check_version())
