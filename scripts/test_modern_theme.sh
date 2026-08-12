#!/usr/bin/env bash
# ==============================================================================
# Script di test per Temi Moderni Unificati (GTK3, GTK4, Libadwaita, GNOME Shell)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RUN_CLI="$SCRIPT_DIR/run_cli.sh"

TMP_THEME_DIR="/tmp/Nordic-Modern-Test"
ARCHIVE_PATH="/tmp/Nordic-Modern-Test.zip"

echo "======================================================================"
echo " 1. Creazione dell'archivio di un tema moderno unificato"
echo "======================================================================"
rm -rf "$TMP_THEME_DIR" "$ARCHIVE_PATH"
mkdir -p "$TMP_THEME_DIR/gtk-3.0"
mkdir -p "$TMP_THEME_DIR/gtk-4.0"
mkdir -p "$TMP_THEME_DIR/gnome-shell"

echo "/* GTK3 CSS */" > "$TMP_THEME_DIR/gtk-3.0/gtk.css"
echo "/* GTK4 & Libadwaita CSS */" > "$TMP_THEME_DIR/gtk-4.0/gtk.css"
echo "/* GNOME Shell CSS */" > "$TMP_THEME_DIR/gnome-shell/gnome-shell.css"
cat <<EOF > "$TMP_THEME_DIR/index.theme"
[Desktop Entry]
Type=X-GNOME-Metatheme
Name=Nordic-Modern-Test
Comment=Tema unificato di test moderno GTK3/GTK4/Shell
Encoding=UTF-8
EOF

(cd /tmp && zip -r "$ARCHIVE_PATH" Nordic-Modern-Test)
echo "✓ Archivio creato in: $ARCHIVE_PATH"

echo ""
echo "======================================================================"
echo " 2. Installazione del tema unificato con GnomeThemeManager"
echo "======================================================================"
"$RUN_CLI" install --file "$ARCHIVE_PATH" --overwrite

echo ""
echo "======================================================================"
echo " 3. Elenco dei temi utente installati nel sistema"
echo "======================================================================"
"$RUN_CLI" list --user-only

echo ""
echo "======================================================================"
echo " 4. Simulazione applicazione del tema unificato"
echo "======================================================================"
"$RUN_CLI" apply --gtk "Nordic-Modern-Test" || echo "(GSettings in ambiente headless o non GNOME ignorato)"

echo ""
echo "======================================================================"
echo " 5. Disinstallazione del tema unificato"
echo "======================================================================"
"$RUN_CLI" uninstall --name "Nordic-Modern-Test" --type gtk -y

echo ""
echo "======================================================================"
echo " 6. Pulizia file temporanei"
echo "======================================================================"
rm -rf "$TMP_THEME_DIR" "$ARCHIVE_PATH"
echo "✓ Test completato con successo!"
