#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""Compile Gettext PO translation files into binary MO files.

Scans `po/*.po` files and compiles them into
`src/gnome_theme_manager/locale/<lang>/LC_MESSAGES/gnomethememanager.mo`.
Uses `msgfmt` if available, otherwise uses a pure Python MO compiler fallback.
"""

import shutil
import struct
import subprocess
import sys
from pathlib import Path

DOMAIN = "gnomethememanager"
ROOT_DIR = Path(__file__).resolve().parent.parent
PO_DIR = ROOT_DIR / "po"
LOCALE_DIR = ROOT_DIR / "src" / "gnome_theme_manager" / "locale"


def _parse_po_file(po_path: Path) -> dict[str, str]:
    """Parse PO file and extract msgid -> msgstr mappings (including header)."""
    content = po_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    translations: dict[str, str] = {}
    current_msgid: list[str] | None = None
    current_msgstr: list[str] | None = None
    in_msgid = False
    in_msgstr = False

    def unescape(s: str) -> str:
        s = s.strip()
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        return s.encode("utf-8").decode("unicode_escape")

    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue

        if line_s.startswith("msgid "):
            if current_msgid is not None and current_msgstr is not None:
                k = "".join(current_msgid)
                v = "".join(current_msgstr)
                translations[k] = v

            current_msgid = [unescape(line_s[6:])]
            current_msgstr = None
            in_msgid = True
            in_msgstr = False
        elif line_s.startswith("msgstr "):
            current_msgstr = [unescape(line_s[7:])]
            in_msgid = False
            in_msgstr = True
        elif line_s.startswith('"') and line_s.endswith('"'):
            if in_msgid and current_msgid is not None:
                current_msgid.append(unescape(line_s))
            elif in_msgstr and current_msgstr is not None:
                current_msgstr.append(unescape(line_s))

    if current_msgid is not None and current_msgstr is not None:
        k = "".join(current_msgid)
        v = "".join(current_msgstr)
        translations[k] = v

    return translations


def _generate_mo_data(translations: dict[str, str]) -> bytes:
    """Generate GNU gettext binary MO file contents from translation dictionary."""
    keys = sorted(translations.keys())
    count = len(keys)

    # Magic number for GNU gettext MO
    magic = 0x950412DE
    version = 0

    # Header size: 7 integers (28 bytes)
    # Orig table starts at 28
    # Trans table starts at 28 + count * 8
    orig_table_offset = 28
    trans_table_offset = orig_table_offset + count * 8
    strings_offset = trans_table_offset + count * 8

    orig_table: list[tuple[int, int]] = []
    trans_table: list[tuple[int, int]] = []
    data_bytes = bytearray()

    current_offset = strings_offset
    for key in keys:
        key_bytes = key.encode("utf-8") + b"\x00"
        val_bytes = translations[key].encode("utf-8") + b"\x00"

        orig_table.append((len(key.encode("utf-8")), current_offset))
        current_offset += len(key_bytes)
        data_bytes.extend(key_bytes)

    for key in keys:
        val_bytes = translations[key].encode("utf-8") + b"\x00"
        trans_table.append((len(translations[key].encode("utf-8")), current_offset))
        current_offset += len(val_bytes)
        data_bytes.extend(val_bytes)

    header = struct.pack(
        "Iiiiiii",
        magic,
        version,
        count,
        orig_table_offset,
        trans_table_offset,
        0,  # hash table size
        0,  # hash table offset
    )

    table_data = bytearray()
    for length, offset in orig_table:
        table_data.extend(struct.pack("ii", length, offset))
    for length, offset in trans_table:
        table_data.extend(struct.pack("ii", length, offset))

    return bytes(header + table_data + data_bytes)


def compile_with_python(po_file: Path, mo_file: Path) -> None:
    """Fallback pure-Python compilation of PO to MO."""
    translations = _parse_po_file(po_file)
    mo_data = _generate_mo_data(translations)
    mo_file.write_bytes(mo_data)


def compile_translations() -> int:
    """Compile all .po files in po/ directory into .mo files in LOCALE_DIR.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    msgfmt_bin = shutil.which("msgfmt")

    if not PO_DIR.is_dir():
        print(f"\033[0;31mError: PO directory not found: {PO_DIR}\033[0m", file=sys.stderr)
        return 1

    po_files = sorted(PO_DIR.glob("*.po"))
    if not po_files:
        print(f"\033[1;33mWarning: No .po files found in {PO_DIR}\033[0m")
        return 0

    success_count = 0
    for po_file in po_files:
        lang = po_file.stem  # e.g., 'it', 'en'
        target_dir = LOCALE_DIR / lang / "LC_MESSAGES"
        target_dir.mkdir(parents=True, exist_ok=True)
        mo_file = target_dir / f"{DOMAIN}.mo"

        if msgfmt_bin:
            cmd = [msgfmt_bin, "-o", str(mo_file), str(po_file)]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(
                    f"\033[0;32m✓ Compiled (msgfmt):\033[0m {po_file.relative_to(ROOT_DIR)} -> {mo_file.relative_to(ROOT_DIR)}"
                )
                success_count += 1
            except subprocess.CalledProcessError as err:
                print(
                    f"\033[0;31m✗ Failed to compile {po_file}:\033[0m\n{err.stderr}",
                    file=sys.stderr,
                )
                return 1
        else:
            try:
                compile_with_python(po_file, mo_file)
                print(
                    f"\033[0;32m✓ Compiled (pure-python):\033[0m {po_file.relative_to(ROOT_DIR)} -> {mo_file.relative_to(ROOT_DIR)}"
                )
                success_count += 1
            except Exception as err:
                print(f"\033[0;31m✗ Failed to compile {po_file}:\033[0m\n{err}", file=sys.stderr)
                return 1

    print(f"\033[0;32mSuccessfully compiled {success_count} translation catalog(s).\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(compile_translations())
