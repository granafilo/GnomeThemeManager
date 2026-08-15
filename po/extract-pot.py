#!/usr/bin/env python3
# Script Python per estrarre le stringhe tradotte e generare il file modello .pot.

import os
import re
import sys


def extract_strings():
    if not os.path.exists("po/POTFILES.in"):
        print("Errore: po/POTFILES.in non trovato")
        sys.exit(1)

    with open("po/POTFILES.in", "r", encoding="utf-8") as f:
        files = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    extracted = {}  # msgid -> lista di (file, riga)

    # Regex per Python: _("...") o _('...')
    py_re = re.compile(r'_\(\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*\)')

    # Regex per file UI/XML: <property name="..." translatable="yes">...</property>
    ui_re = re.compile(r'<property\s+[^>]*translatable="yes"[^>]*>([^<]*)</property>')

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"Avviso: file {filepath} non trovato")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if filepath.endswith(".py"):
            for line_idx, line in enumerate(lines):
                for match in py_re.finditer(line):
                    raw_str = match.group(1)
                    try:
                        decoded = eval(raw_str)
                        if decoded:
                            extracted.setdefault(decoded, []).append((filepath, line_idx + 1))
                    except Exception:
                        pass
        elif filepath.endswith(".ui"):
            content = "".join(lines)
            for match in ui_re.finditer(content):
                decoded = match.group(1).strip()
                if decoded:
                    pos = match.start()
                    line_num = content[:pos].count("\n") + 1
                    extracted.setdefault(decoded, []).append((filepath, line_num))

    os.makedirs("po", exist_ok=True)
    with open("po/gnomethememanager.pot", "w", encoding="utf-8") as f:
        f.write("# Translation template for gnome-theme-manager.\n")
        f.write("# Copyright (C) 2026 GnomeThemeManager Contributors\n")
        f.write(
            "# This file is distributed under the same license as the gnome-theme-manager project.\n"
        )
        f.write("#\n")
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Project-Id-Version: gnome-theme-manager 1.0.0\\n"\n')
        f.write('"MIME-Version: 1.0\\n"\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write('"Content-Transfer-Encoding: 8bit\\n"\n\n')

        for msgid, refs in sorted(extracted.items()):
            for filepath, line_num in refs:
                f.write(f"#: {filepath}:{line_num}\n")
            escaped_msgid = msgid.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            f.write(f'msgid "{escaped_msgid}"\n')
            f.write('msgstr ""\n\n')

    print(f"Estratte {len(extracted)} stringhe in po/gnomethememanager.pot")


if __name__ == "__main__":
    # Assicurati di essere nella root del progetto
    if os.path.basename(os.getcwd()) == "po":
        os.chdir("..")
    extract_strings()
