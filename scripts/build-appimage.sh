#!/usr/bin/env bash
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
VERSION="0.9.0-beta1"
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

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/lib/python3/site-packages"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APP_DIR/usr/share/metainfo"
mkdir -p "$OUTPUT_DIR"

# ------------------------------------------------------------------------------
# 3. Copia file del codice sorgente Python e dipendenze
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/6] Copia sorgenti Python e moduli...${NC}"

cp -r "$ROOT_DIR/src/gnome_theme_manager" "$APP_DIR/usr/lib/python3/site-packages/"

# Copia risorse desktop, metadati ed icone
cp "$ROOT_DIR/appimage/$APP_ID.desktop" "$APP_DIR/usr/share/applications/"
cp "$ROOT_DIR/appimage/$APP_ID.desktop" "$APP_DIR/"
cp "$ROOT_DIR/appimage/$APP_ID.svg" "$APP_DIR/usr/share/icons/hicolor/scalable/apps/"
cp "$ROOT_DIR/appimage/$APP_ID.svg" "$APP_DIR/$APP_ID.svg"
cp "$ROOT_DIR/appimage/$APP_ID.svg" "$APP_DIR/.DirIcon"
cp "$ROOT_DIR/appimage/$APP_ID.metainfo.xml" "$APP_DIR/usr/share/metainfo/"

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
export XDG_DATA_DIRS="${APPDIR}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export XDG_CONFIG_DIRS="${APPDIR}/etc:${XDG_CONFIG_DIRS:-/etc/xdg}"

# Esegui la GUI automaticamente
exec "${APPDIR}/usr/bin/gnome-theme-manager" gui "$@"
EOF
chmod +x "$APP_DIR/AppRun"

echo -e "${GREEN}✓ AppRun e wrapper binari creati con successo.${NC}"

# ------------------------------------------------------------------------------
# 5. Generazione file AppImage con appimagetool
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/6] Creazione pacchetto AppImage...${NC}"

TARGET_FILE="$OUTPUT_DIR/${APP_NAME}-${VERSION}-${ARCH}.AppImage"
rm -f "$TARGET_FILE"

ARCH="$ARCH" "$APPIMAGETOOL_BIN" "$APP_DIR" "$TARGET_FILE"

# ------------------------------------------------------------------------------
# 6. Verifiche finali e riepilogo
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/6] Validazione pacchetto generato...${NC}"

if [ -f "$TARGET_FILE" ]; then
    SIZE=$(du -h "$TARGET_FILE" | cut -f1)
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN}  ✓ APPIMAGE CREATO CON SUCCESSO!${NC}"
    echo -e "${GREEN}  Percorso:  $TARGET_FILE${NC}"
    echo -e "${GREEN}  Dimensione: $SIZE${NC}"
    echo -e "${GREEN}====================================================${NC}"
else
    echo -e "${RED}Errore: Generazione dell'AppImage fallita. File $TARGET_FILE non trovato.${NC}" >&2
    exit 1
fi
