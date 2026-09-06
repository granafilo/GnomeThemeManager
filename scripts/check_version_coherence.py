#!/usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later
"""Script to verify project version consistency across all files and documents."""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_version(root: Path | None = None) -> int:
    """Check version consistency across source code, packaging, and documentation."""
    base_dir = root or ROOT_DIR

    # 1. Source of truth: src/gnome_theme_manager/__init__.py (__version__)
    init_path = base_dir / "src" / "gnome_theme_manager" / "__init__.py"
    if not init_path.is_file():
        print(f"Error: File not found: {init_path}", file=sys.stderr)
        return 1

    init_content = init_path.read_text(encoding="utf-8")
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_content, re.MULTILINE)
    if not m_init:
        print("Error: __version__ not found in __init__.py", file=sys.stderr)
        return 1
    current_ver = m_init.group(1)

    print("Checking version consistency (Target Single Source of Truth):")
    print(f"  gnome_theme_manager.__version__:    {current_ver}")

    # 2. README.md: verify presence of '**Current release:** v{current_ver}'
    readme_path = base_dir / "README.md"
    if not readme_path.is_file():
        print(f"Error: File not found: {readme_path}", file=sys.stderr)
        return 1

    readme_content = readme_path.read_text(encoding="utf-8")
    expected_readme_marker = f"**Current release:** v{current_ver}"
    if expected_readme_marker not in readme_content:
        print(
            f"Error: README.md does not contain expected marker '{expected_readme_marker}'",
            file=sys.stderr,
        )
        return 1
    print(f"  README.md (Current release):        v{current_ver} [OK]")

    # 3. CHANGELOG.md: first version entry matches current_ver
    changelog_path = base_dir / "CHANGELOG.md"
    if not changelog_path.is_file():
        print(f"Error: File not found: {changelog_path}", file=sys.stderr)
        return 1

    changelog_content = changelog_path.read_text(encoding="utf-8")
    m_changelog = re.search(r"^##\s*\[([^\]]+)\]", changelog_content, re.MULTILINE)
    if not m_changelog:
        print("Error: No version section found in CHANGELOG.md", file=sys.stderr)
        return 1
    changelog_ver = m_changelog.group(1)
    if changelog_ver != current_ver:
        print(
            f"Error: First entry in CHANGELOG.md is [{changelog_ver}], expected [{current_ver}]",
            file=sys.stderr,
        )
        return 1
    print(f"  CHANGELOG.md (First entry):         [{changelog_ver}] [OK]")

    # 4. scripts/build-flatpak.sh
    build_path = base_dir / "scripts" / "build-flatpak.sh"
    if build_path.is_file():
        build_content = build_path.read_text(encoding="utf-8")
        m_build = re.search(r'^VERSION="([^"]+)"', build_content, re.MULTILINE)
        if not m_build:
            print("Error: VERSION not found in build-flatpak.sh", file=sys.stderr)
            return 1
        build_ver = m_build.group(1)
        if build_ver != current_ver:
            print(
                f"Error: VERSION in build-flatpak.sh is '{build_ver}', expected '{current_ver}'",
                file=sys.stderr,
            )
            return 1
        print(f"  scripts/build-flatpak.sh:           {build_ver} [OK]")

    # 5. data/metainfo/io.github.granafilo.ThemeManager.metainfo.xml (first release)
    xml_path = base_dir / "data" / "metainfo" / "io.github.granafilo.ThemeManager.metainfo.xml"
    if xml_path.is_file():
        xml_content = xml_path.read_text(encoding="utf-8")
        m_xml = re.search(r'<release\s+version="([^"]+)"', xml_content)
        if not m_xml:
            print("Error: <release version=...> not found in metainfo.xml", file=sys.stderr)
            return 1
        xml_ver = m_xml.group(1)
        if xml_ver != current_ver:
            print(
                f"Error: Version in metainfo.xml is '{xml_ver}', expected '{current_ver}'",
                file=sys.stderr,
            )
            return 1
        print(f"  metainfo.xml (AppStream):           {xml_ver} [OK]")

    print("✓ All versions across files and documents are consistent!")
    return 0


if __name__ == "__main__":
    sys.exit(check_version())
