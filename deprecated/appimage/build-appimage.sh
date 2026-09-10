#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script di Build per AppImage - GNOME Theme Manager
# ==============================================================================
# Questo script pulisce la directory di build AppDir, copia i sorgenti Python,
# le risorse desktop/icone/metadati, crea il wrapper AppRun ed impacchetta
# l'applicazione tramite appimagetool.
# ==============================================================================

set -eo pipefail

# Modello dei colori ANSI per output chiaro a terminale
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
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$ROOT_DIR/AppDir"
OUTPUT_DIR="$ROOT_DIR/dist"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  Avvio Generazione AppImage per ${APP_NAME} v${VERSION}${NC}"
echo -e "${BLUE}====================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Verifiche preliminari dei prerequisiti
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/6] Controllo strumenti richiesti...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Errore: 'python3' non trovato nel sistema.${NC}" >&2
    exit 1
fi

APPIMAGETOOL_BIN=""
if command -v appimagetool &> /dev/null; then
    APPIMAGETOOL_BIN="appimagetool"
elif [ -f "$ROOT_DIR/appimagetool-x86_64.AppImage" ]; then
    APPIMAGETOOL_BIN="$ROOT_DIR/appimagetool-x86_64.AppImage"
else
    echo -e "${YELLOW}  'appimagetool' non trovato nel PATH. Download temporaneo in corso...${NC}"
    curl -sLO "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
    APPIMAGETOOL_BIN="./appimagetool-x86_64.AppImage"
fi

echo -e "${GREEN}✓ Strumenti ok (appimagetool: ${APPIMAGETOOL_BIN})${NC}"

# ------------------------------------------------------------------------------
# 2. Pulizia e creazione struttura AppDir
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/6] Preparazione struttura directory AppDir...${NC}"

# Compilazione delle traduzioni .po in .mo prima di copiare i sorgenti
python3 "$ROOT_DIR/scripts/compile_translations.py"

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/lib/python3/site-packages"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APP_DIR/usr/share/metainfo"
mkdir -p "$OUTPUT_DIR"

# Copia la directory locale dentro il package Python dell'AppDir in modo
# che gettext trovi i file .mo a runtime anche all'interno dell'AppImage.
mkdir -p "$APP_DIR/usr/lib/python3/site-packages/gnome_theme_manager"
cp -r "$ROOT_DIR/src/gnome_theme_manager/locale" "$APP_DIR/usr/lib/python3/site-packages/gnome_theme_manager/"

# ------------------------------------------------------------------------------
# 3. Copia file del codice sorgente Python e dipendenze
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/6] Copia sorgenti Python e moduli...${NC}"

cp -r "$ROOT_DIR/src/gnome_theme_manager" "$APP_DIR/usr/lib/python3/site-packages/"

# Copia risorse desktop, metadati ed icone
if [ -f "$ROOT_DIR/data/desktop/$APP_ID.desktop" ]; then
    cp "$ROOT_DIR/data/desktop/$APP_ID.desktop" "$APP_DIR/usr/share/applications/"
    cp "$ROOT_DIR/data/desktop/$APP_ID.desktop" "$APP_DIR/"
elif [ -f "$ROOT_DIR/appimage/$APP_ID.desktop" ]; then
    cp "$ROOT_DIR/appimage/$APP_ID.desktop" "$APP_DIR/usr/share/applications/"
    cp "$ROOT_DIR/appimage/$APP_ID.desktop" "$APP_DIR/"
fi
cp "$ROOT_DIR/appimage/$APP_ID.metainfo.xml" "$APP_DIR/usr/share/metainfo/"

# Copia definizioni MIME
mkdir -p "$APP_DIR/usr/share/mime/packages"
if [ -f "$ROOT_DIR/data/mime/packages/gtm-appimage.xml" ]; then
    cp "$ROOT_DIR/data/mime/packages/gtm-appimage.xml" "$APP_DIR/usr/share/mime/packages/"
fi

# Copia icone hicolor dell'applicazione (512x512, 256x256, 128x128 e scalable - apps e mimetypes)
mkdir -p "$APP_DIR/usr/share/icons/hicolor/512x512/apps"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/512x512/mimetypes"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/mimetypes"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/128x128/mimetypes"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/scalable/mimetypes"

# Icona 512x512 PNG canonica
if [ -f "$ROOT_DIR/data/icons/hicolor/512x512/apps/$APP_ID.png" ]; then
    cp "$ROOT_DIR/data/icons/hicolor/512x512/apps/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/512x512/apps/$APP_ID.png"
    cp "$ROOT_DIR/data/icons/hicolor/512x512/apps/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/512x512/mimetypes/application-vnd.appimage.png"
    cp "$ROOT_DIR/data/icons/hicolor/512x512/apps/$APP_ID.png" "$APP_DIR/$APP_ID.png"
    # .DirIcon DEVE essere un file PNG regolare 512x512 (non symlink, non SVG)
    cp "$ROOT_DIR/data/icons/hicolor/512x512/apps/$APP_ID.png" "$APP_DIR/.DirIcon"
elif [ -f "$ROOT_DIR/data/icons/$APP_ID.png" ]; then
    cp "$ROOT_DIR/data/icons/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/512x512/apps/$APP_ID.png"
    cp "$ROOT_DIR/data/icons/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/512x512/mimetypes/application-vnd.appimage.png"
    cp "$ROOT_DIR/data/icons/$APP_ID.png" "$APP_DIR/$APP_ID.png"
    cp "$ROOT_DIR/data/icons/$APP_ID.png" "$APP_DIR/.DirIcon"
fi

# Icona 256x256 PNG canonica
if [ -f "$ROOT_DIR/data/icons/hicolor/256x256/apps/$APP_ID.png" ]; then
    cp "$ROOT_DIR/data/icons/hicolor/256x256/apps/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
    cp "$ROOT_DIR/data/icons/hicolor/256x256/apps/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/256x256/mimetypes/application-vnd.appimage.png"
fi

# Icona 128x128 PNG canonica
if [ -f "$ROOT_DIR/data/icons/hicolor/128x128/apps/$APP_ID.png" ]; then
    cp "$ROOT_DIR/data/icons/hicolor/128x128/apps/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/128x128/apps/$APP_ID.png"
    cp "$ROOT_DIR/data/icons/hicolor/128x128/apps/$APP_ID.png" "$APP_DIR/usr/share/icons/hicolor/128x128/mimetypes/application-vnd.appimage.png"
fi

# Icona Scalable SVG
if [ -f "$ROOT_DIR/data/icons/hicolor/scalable/apps/$APP_ID.svg" ]; then
    cp "$ROOT_DIR/data/icons/hicolor/scalable/apps/$APP_ID.svg" "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
    cp "$ROOT_DIR/data/icons/hicolor/scalable/apps/$APP_ID.svg" "$APP_DIR/usr/share/icons/hicolor/scalable/mimetypes/application-vnd.appimage.svg"
elif [ -f "$ROOT_DIR/appimage/$APP_ID.svg" ]; then
    cp "$ROOT_DIR/appimage/$APP_ID.svg" "$APP_DIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
    cp "$ROOT_DIR/appimage/$APP_ID.svg" "$APP_DIR/usr/share/icons/hicolor/scalable/mimetypes/application-vnd.appimage.svg"
fi

# Copia icone bundled dell'applicazione
if [ -d "$ROOT_DIR/data/icons" ]; then
    mkdir -p "$APP_DIR/usr/share/icons"
    cp -r "$ROOT_DIR/data/icons"/* "$APP_DIR/usr/share/icons/"
    # Link simbolico per compatibilità percorsi senza duplicazione byte
    mkdir -p "$APP_DIR/data"
    ln -sfn "../usr/share/icons" "$APP_DIR/data/icons"
fi

# ------------------------------------------------------------------------------
# 4. Generazione script di avvio (AppRun e wrapper binario)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/6] Generazione script AppRun e wrapper esecuzione...${NC}"

# Wrapper binario gnome-theme-manager
cat << 'EOF' > "$APP_DIR/usr/bin/gnome-theme-manager"
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
APP_ROOT="$(dirname "$(dirname "$HERE")")"

export PYTHONPATH="$APP_ROOT/usr/lib/python3/site-packages:$PYTHONPATH"
export XDG_DATA_DIRS="$APP_ROOT/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec python3 -m gnome_theme_manager "$@"
EOF
chmod +x "$APP_DIR/usr/bin/gnome-theme-manager"

# AppRun entry point per AppImage
cat << 'EOF' > "$APP_DIR/AppRun"
#!/usr/bin/env bash
# AppRun - Entry point per AppImage

if [ -z "$APPDIR" ]; then
    APPDIR="$(dirname "$(readlink -f "$0")")"
fi

export PATH="${APPDIR}/usr/bin:${PATH}"
export PYTHONPATH="${APPDIR}/usr/lib/python3/site-packages:${PYTHONPATH}"
export TEXTDOMAINDIR="${APPDIR}/usr/lib/python3/site-packages/gnome_theme_manager/locale"
export XDG_DATA_DIRS="${APPDIR}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export XDG_CONFIG_DIRS="${APPDIR}/etc:${XDG_CONFIG_DIRS:-/etc/xdg}"

# Esegui la GUI se non vengono passati argomenti, altrimenti esegui il comando richiesto
if [ $# -eq 0 ]; then
    exec "${APPDIR}/usr/bin/gnome-theme-manager" gui
else
    exec "${APPDIR}/usr/bin/gnome-theme-manager" "$@"
fi
EOF
chmod +x "$APP_DIR/AppRun"

echo -e "${GREEN}✓ AppRun e wrapper binari creati con successo.${NC}"

# Pulizia file cache temporanei prima del packaging per minimizzare la dimensione dell'AppImage
find "$APP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$APP_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# ------------------------------------------------------------------------------
# 5. Generazione file AppImage con appimagetool
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/6] Creazione pacchetto AppImage...${NC}"

TARGET_FILE="$OUTPUT_DIR/${APP_NAME}-${VERSION}-${ARCH}.AppImage"
rm -f "$TARGET_FILE"

echo -e "${BLUE}Uso appimagetool in modalità extract-and-run per evitare la dipendenza FUSE del runner.${NC}"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL_BIN" "$APP_DIR" "$TARGET_FILE"

# ------------------------------------------------------------------------------
# 6. Verifiche finali e riepilogo
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/6] Validazione pacchetto generato...${NC}"

if [ -f "$TARGET_FILE" ]; then
    SIZE=$(du -h "$TARGET_FILE" | cut -f1)
    
    # Verifica post-build delle icone (.DirIcon e file desktop)
    echo -e "${YELLOW}Verifica integrità icone incorporate (.DirIcon)...${NC}"
    TMP_EXTRACT=$(mktemp -d)
    (
        cd "$TMP_EXTRACT"
        ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TARGET_FILE" --appimage-extract > /dev/null 2>&1 || true
        if [ -f "squashfs-root/.DirIcon" ] && [ -f "squashfs-root/$APP_ID.png" ]; then
            echo -e "${GREEN}✓ Icona .DirIcon e $APP_ID.png estratte e confermate nell'AppImage.${NC}"
        else
            echo -e "${RED}Attenzione: Impossibile confermare la presenza di .DirIcon nell'AppImage estratto.${NC}" >&2
        fi
    )
    rm -rf "$TMP_EXTRACT"

    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN}  ✓ APPIMAGE CREATO CON SUCCESSO!${NC}"
    echo -e "${GREEN}  Percorso:  $TARGET_FILE${NC}"
    echo -e "${GREEN}  Dimensione: $SIZE${NC}"
    echo -e "${GREEN}====================================================${NC}"
else
    echo -e "${RED}Errore: Generazione dell'AppImage fallita. File $TARGET_FILE non trovato.${NC}" >&2
    exit 1
fi
