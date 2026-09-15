#!/usr/bin/env python3
# Python script to extract translatable strings and generate .pot template.

import ast
import os
import sys
import xml.etree.ElementTree as ET


def extract_strings() -> None:
    if not os.path.exists("po/POTFILES.in"):
        print("Error: po/POTFILES.in not found")
        sys.exit(1)

    with open("po/POTFILES.in", "r", encoding="utf-8") as f:
        files = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    extracted: dict[str, list[tuple[str, int]]] = {}

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"Warning: file {filepath} not found")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if filepath.endswith(".py"):
            try:
                tree = ast.parse(content, filename=filepath)
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "_"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                    ):
                        raw_str = node.args[0].value
                        if raw_str.strip():
                            extracted.setdefault(raw_str, []).append((filepath, node.lineno))
            except Exception as exc:
                print(f"Error parsing {filepath}: {exc}")

        elif filepath.endswith(".ui"):
            try:
                tree = ET.fromstring(content)
                for elem in tree.iter():
                    if elem.attrib.get("translatable") == "yes" and elem.text:
                        decoded = elem.text.strip()
                        if decoded:
                            snippet = decoded[:30]
                            line_num = 1
                            for idx, line in enumerate(content.splitlines()):
                                if snippet in line:
                                    line_num = idx + 1
                                    break
                            extracted.setdefault(decoded, []).append((filepath, line_num))
            except Exception as exc:
                print(f"Error parsing {filepath}: {exc}")

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

    print(f"Extracted {len(extracted)} strings into po/gnomethememanager.pot")


if __name__ == "__main__":
    # Ensure current directory is project root
    if os.path.basename(os.getcwd()) == "po":
        os.chdir("..")
    extract_strings()
