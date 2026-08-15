#!/usr/bin/env python3
# Script Python per compilare i file .po in .mo in modo portabile e autonomo.

import re
import struct
import sys


def compile_po(po_path, mo_path):
    with open(po_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex per trovare coppie di msgid/msgstr
    pattern = re.compile(
        r'msgid\s+((?:"(?:[^"\\]|\\.)*"\s*)+)\s*'
        r'msgstr\s+((?:"(?:[^"\\]|\\.)*"\s*)+)'
    )

    pairs = []
    for match in pattern.finditer(content):
        msgid_raw = match.group(1)
        msgstr_raw = match.group(2)

        # Concatena le righe racchiuse tra virgolette
        msgid = "".join(eval(chunk) for chunk in msgid_raw.splitlines() if chunk.strip())
        msgstr = "".join(eval(chunk) for chunk in msgstr_raw.splitlines() if chunk.strip())

        # gettext richiede che le stringhe siano in byte UTF-8 terminati da null
        pairs.append((msgid.encode("utf-8"), msgstr.encode("utf-8")))

    # gettext impone l'ordinamento in base ai msgid originali
    pairs.sort(key=lambda x: x[0])
    num_strings = len(pairs)

    orig_table_offset = 28
    trans_table_offset = 28 + 8 * num_strings
    data_offset = 28 + 16 * num_strings

    orig_table = []
    trans_table = []
    data = bytearray()

    for orig, trans in pairs:
        # Original
        orig_len = len(orig)
        orig_offset = data_offset + len(data)
        data.extend(orig + b"\x00")
        orig_table.append((orig_len, orig_offset))

        # Translation
        trans_len = len(trans)
        trans_offset = data_offset + len(data)
        data.extend(trans + b"\x00")
        trans_table.append((trans_len, trans_offset))

    with open(mo_path, "wb") as f:
        # Magic number: 0x950412de (little endian)
        f.write(
            struct.pack(
                "<Iiiiiii",
                0x950412DE,  # magic
                0,  # revision
                num_strings,
                orig_table_offset,
                trans_table_offset,
                0,  # hash table size
                0,  # hash table offset
            )
        )

        f.writelines(struct.pack("<ii", length, offset) for length, offset in orig_table)

        f.writelines(struct.pack("<ii", length, offset) for length, offset in trans_table)

        f.write(data)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: compile-po.py <input.po> <output.mo>")
        sys.exit(1)
    compile_po(sys.argv[1], sys.argv[2])
    print(f"Compilato con successo {sys.argv[1]} -> {sys.argv[2]}")
