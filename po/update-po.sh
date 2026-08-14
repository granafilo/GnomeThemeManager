#!/bin/bash
# Script per aggiornare il file modello POT e i file PO, e compilare i file MO.

set -e

# Muoviti nella root del progetto se eseguito da po/
cd "$(dirname "$0")/.."

echo "Estrazione delle stringhe da tradurre..."
python3 po/extract-pot.py

echo "Aggiornamento dei file .po..."
for lang in $(cat po/LINGUAS); do
    if [ ! -f "po/${lang}.po" ]; then
        echo "Inizializzazione di po/${lang}.po..."
        if command -v msginit >/dev/null 2>&1; then
            msginit --no-translator -l "${lang}" -i po/gnomethememanager.pot -o "po/${lang}.po"
        else
            # Fallback manuale se msginit non è installato
            cp po/gnomethememanager.pot "po/${lang}.po"
            sed -i 's/"Content-Type: text\/plain; charset=UTF-8\\n"/"Content-Type: text\/plain; charset=UTF-8\\n"\n"Language: '"${lang}"'\\n"/' "po/${lang}.po"
        fi
    else
        echo "Aggiornamento di po/${lang}.po..."
        if command -v msgmerge >/dev/null 2>&1; then
            msgmerge -U "po/${lang}.po" po/gnomethememanager.pot
        else
            echo "Avviso: msgmerge non trovato. Salto aggiornamento automatico di po/${lang}.po"
        fi
    fi
done

echo "Compilazione dei file .mo..."
for lang in $(cat po/LINGUAS); do
    if [ -f "po/${lang}.po" ]; then
        echo "Compilazione di po/${lang}.po -> MO..."
        mkdir -p "src/gnome_theme_manager/locale/${lang}/LC_MESSAGES"
        python3 po/compile-po.py "po/${lang}.po" "src/gnome_theme_manager/locale/${lang}/LC_MESSAGES/gnomethememanager.mo"
    fi
done

echo "Fatto!"
