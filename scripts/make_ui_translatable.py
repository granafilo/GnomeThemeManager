#!/usr/bin/env python3
# Script per rendere traducibili i file .ui aggiungendo translatable="yes"

import os
import re


def main():
    ui_dir = "src/gnome_theme_manager/gui_gtk/ui"
    properties_to_translate = {"label", "title", "subtitle", "description", "tooltip-text", "placeholder-text"}

    for filename in os.listdir(ui_dir):
        if not filename.endswith(".ui"):
            continue
        filepath = os.path.join(ui_dir, filename)
        print(f"Elaborazione file: {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        for prop in properties_to_translate:
            # Trova <property name="prop">valore</property> senza translatable="yes"
            pattern = re.compile(rf'<property\s+name="{prop}"(?!\s+translatable="yes")>([^<]+)</property>')
            
            # Sostituisce aggiungendo translatable="yes"
            new_content, count = pattern.subn(rf'<property name="{prop}" translatable="yes">\1</property>', content)
            if count > 0:
                content = new_content
                modified = True
                print(f"  - Aggiunto translatable=\"yes\" a {count} proprietà '{prop}'")
                
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

if __name__ == "__main__":
    main()
