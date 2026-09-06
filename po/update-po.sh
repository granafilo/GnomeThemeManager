#!/bin/bash
# Script to update POT template and PO files, and compile MO files.

set -e

# Move to project root if run from po/
cd "$(dirname "$0")/.."

echo "Extracting translatable strings..."
python3 po/extract-pot.py

echo "Updating .po files..."
for lang in $(cat po/LINGUAS); do
    if [ ! -f "po/${lang}.po" ]; then
        echo "Initializing po/${lang}.po..."
        if command -v msginit >/dev/null 2>&1; then
            msginit --no-translator -l "${lang}" -i po/gnomethememanager.pot -o "po/${lang}.po"
        else
            # Manual fallback if msginit is not installed
            cp po/gnomethememanager.pot "po/${lang}.po"
            sed -i 's/"Content-Type: text\/plain; charset=UTF-8\\n"/"Content-Type: text\/plain; charset=UTF-8\\n"\n"Language: '"${lang}"'\\n"/' "po/${lang}.po"
        fi
    else
        echo "Updating po/${lang}.po..."
        if command -v msgmerge >/dev/null 2>&1; then
            msgmerge -U "po/${lang}.po" po/gnomethememanager.pot
        else
            echo "Warning: msgmerge not found. Skipping automatic update of po/${lang}.po"
        fi
    fi
done

echo "Compiling .mo files..."
for lang in $(cat po/LINGUAS); do
    if [ -f "po/${lang}.po" ]; then
        echo "Compiling po/${lang}.po -> MO..."
        mkdir -p "src/gnome_theme_manager/locale/${lang}/LC_MESSAGES"
        python3 po/compile-po.py "po/${lang}.po" "src/gnome_theme_manager/locale/${lang}/LC_MESSAGES/gnomethememanager.mo"
    fi
done

echo "Done!"
