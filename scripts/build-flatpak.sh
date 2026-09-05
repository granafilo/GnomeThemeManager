#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script di Build per Flatpak - GNOME Theme Manager
# ==============================================================================
# Questo script pulisce le vecchie directory di build, esegue flatpak-builder,
# esporta il bundle offline (.flatpak) e genera il file di installazione (.flatpakref).
# ==============================================================================

set -eo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

APP_NAME="GNOMEThemeManager"
APP_ID="io.github.granafilo.ThemeManager"
VERSION="1.5.0"
ARCH="${ARCH:-x86_64}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
    ROOT_DIR="$(dirname "$SCRIPT_DIR")"
else
    ROOT_DIR="$SCRIPT_DIR"
fi

MANIFEST="$ROOT_DIR/flatpak/${APP_ID}.yml"
BUILD_DIR="$ROOT_DIR/build-dir"
REPO_DIR="$ROOT_DIR/repo"
OUTPUT_DIR="$ROOT_DIR/dist"
BUNDLE_FILE="$OUTPUT_DIR/${APP_NAME}-${VERSION}-${ARCH}.flatpak"
FLATPAKREF_FILE="$OUTPUT_DIR/${APP_NAME}.flatpakref"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  Avvio Generazione Flatpak per ${APP_NAME} v${VERSION}${NC}"
echo -e "${BLUE}====================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Controllo strumenti richiesti e repository Flathub
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/5] Controllo strumenti Flatpak e runtime...${NC}"

if ! command -v flatpak &> /dev/null; then
    echo -e "${RED}Errore: 'flatpak' non trovato. Installalo con: sudo apt install flatpak${NC}" >&2
    exit 1
fi

if ! command -v flatpak-builder &> /dev/null; then
    echo -e "${RED}Errore: 'flatpak-builder' non trovato. Installalo con: sudo apt install flatpak-builder${NC}" >&2
    exit 1
fi

# Configura il remote flathub a livello utente se non già presente
echo -e "${BLUE}Configurazione repository Flathub utente...${NC}"
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

echo -e "${GREEN}✓ Strumenti flatpak, flatpak-builder e remote Flathub configurati.${NC}"

# ------------------------------------------------------------------------------
# 2. Pulizia ambiente di build precedente
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/5] Pulizia cache e directory di build...${NC}"
if [ -d "$ROOT_DIR/.flatpak-builder/rofiles" ]; then
    for rof in "$ROOT_DIR/.flatpak-builder/rofiles"/*; do
        if [ -d "$rof" ]; then
            fusermount -u "$rof" 2>/dev/null || true
        fi
    done
fi
rm -rf "$BUILD_DIR" "$REPO_DIR" "$ROOT_DIR/.flatpak-builder"
mkdir -p "$OUTPUT_DIR"

# Compila cataloghi traduzione gettext
if [ -f "$ROOT_DIR/scripts/compile_translations.py" ]; then
    python3 "$ROOT_DIR/scripts/compile_translations.py"
fi

# ------------------------------------------------------------------------------
# 3. Compilazione pacchetto Flatpak con flatpak-builder
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/5] Esecuzione flatpak-builder (download SDK/Runtime se necessario)...${NC}"

flatpak-builder --force-clean \
    --user \
    --install-deps-from=flathub \
    --default-branch=stable \
    --repo="$REPO_DIR" \
    "$BUILD_DIR" \
    "$MANIFEST"

echo -e "${GREEN}✓ Build Flatpak completata con successo nel repository locale.${NC}"

# ------------------------------------------------------------------------------
# 4. Generazione Bundle Offline (.flatpak)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/5] Generazione Bundle Offline (.flatpak)...${NC}"

flatpak build-bundle "$REPO_DIR" "$BUNDLE_FILE" "$APP_ID" stable

echo -e "${GREEN}✓ Bundle offline generato: $BUNDLE_FILE${NC}"

# ------------------------------------------------------------------------------
# 5. Generazione file .flatpakref (Click-to-Install)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/5] Generazione file .flatpakref...${NC}"

cat << EOF > "$FLATPAKREF_FILE"
[Flatpak Ref]
Name=${APP_ID}
Branch=stable
Title=GNOME Theme Manager
Comment=Modern GTK4 & Libadwaita theme, icon, cursor and shell manager for GNOME
Description=Manage GTK, Shell, Icon, and Cursor themes on GNOME seamlessly.
Icon=https://raw.githubusercontent.com/granafilo/GnomeThemeManager/main/data/icons/hicolor/512x512/apps/${APP_ID}.png
Url=https://raw.githubusercontent.com/granafilo/GnomeThemeManager/main/repo
SuggestRemoteName=gnomethememanager-repo
RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo
IsRuntime=false
EOF

echo -e "${GREEN}✓ File Flatpakref generato: $FLATPAKREF_FILE${NC}"

# ------------------------------------------------------------------------------
# Riepilogo e Istruzioni per l'utente
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}  ✓ PACCHETTI FLATPAK CREATI CON SUCCESSO!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${BLUE}1. Bundle Offline (singolo file):${NC} $BUNDLE_FILE"
echo -e "${BLUE}2. File Click-to-Install:${NC}         $FLATPAKREF_FILE"
echo -e "\n${YELLOW}Come installare ed eseguire l'applicazione:${NC}"
echo -e "  • ${GREEN}Installazione Utente (Zero richieste password - Consigliata):${NC}"
echo -e "    flatpak install --user --bundle $BUNDLE_FILE"
echo -e "    oppure:"
echo -e "    flatpak install --user $FLATPAKREF_FILE"
echo -e "\n  • ${GREEN}Installazione di Sistema:${NC}"
echo -e "    flatpak install --bundle $BUNDLE_FILE"
echo -e "\n  • ${GREEN}Esecuzione dell'app:${NC}"
echo -e "    flatpak run $APP_ID"
echo -e "${GREEN}====================================================${NC}\n"
