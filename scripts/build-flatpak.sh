#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Flatpak Build Script - GNOME Theme Manager
# ==============================================================================
# This script cleans previous build directories, runs flatpak-builder,
# exports the offline bundle (.flatpak), and generates the installation file (.flatpakref).
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
echo -e "${BLUE}  Starting Flatpak generation for ${APP_NAME} v${VERSION}${NC}"
echo -e "${BLUE}====================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Check required tools and Flathub repository
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/5] Checking Flatpak tools and runtime...${NC}"

if ! command -v flatpak &> /dev/null; then
    echo -e "${RED}Error: 'flatpak' not found. Install it with: sudo apt install flatpak${NC}" >&2
    exit 1
fi

if ! command -v flatpak-builder &> /dev/null; then
    echo -e "${RED}Error: 'flatpak-builder' not found. Install it with: sudo apt install flatpak-builder${NC}" >&2
    exit 1
fi

# Configure Flathub user remote if not already configured
echo -e "${BLUE}Configuring user Flathub repository...${NC}"
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

echo -e "${GREEN}✓ Flatpak tools, flatpak-builder, and Flathub remote configured.${NC}"

# ------------------------------------------------------------------------------
# 2. Clean previous build environment
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/5] Cleaning cache and build directories...${NC}"
if [ -d "$ROOT_DIR/.flatpak-builder/rofiles" ]; then
    for rof in "$ROOT_DIR/.flatpak-builder/rofiles"/*; do
        if [ -d "$rof" ]; then
            fusermount -u -z "$rof" 2>/dev/null || true
        fi
    done
fi
rm -rf "$BUILD_DIR" "$REPO_DIR" "$ROOT_DIR/.flatpak-builder"
mkdir -p "$OUTPUT_DIR"

# Compile gettext translation catalogs
if [ -f "$ROOT_DIR/scripts/compile_translations.py" ]; then
    python3 "$ROOT_DIR/scripts/compile_translations.py"
fi

# ------------------------------------------------------------------------------
# 3. Build Flatpak package with flatpak-builder
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/5] Running flatpak-builder (downloading SDK/Runtime if needed)...${NC}"

flatpak-builder --force-clean \
    --disable-cache \
    --user \
    --install-deps-from=flathub \
    --default-branch=stable \
    --repo="$REPO_DIR" \
    "$BUILD_DIR" \
    "$MANIFEST"

echo -e "${GREEN}✓ Flatpak build completed successfully in local repository.${NC}"

# ------------------------------------------------------------------------------
# 4. Generate Offline Bundle (.flatpak)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/5] Generating offline bundle (.flatpak)...${NC}"

flatpak build-bundle "$REPO_DIR" "$BUNDLE_FILE" "$APP_ID" stable

echo -e "${GREEN}✓ Offline bundle generated: $BUNDLE_FILE${NC}"

# ------------------------------------------------------------------------------
# 5. Generate .flatpakref file (Click-to-Install)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/5] Generating .flatpakref file...${NC}"

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

echo -e "${GREEN}✓ Flatpakref file generated: $FLATPAKREF_FILE${NC}"

# ------------------------------------------------------------------------------
# Summary and User Instructions
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}  ✓ FLATPAK PACKAGES CREATED SUCCESSFULLY!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${BLUE}1. Offline Bundle (single file):${NC} $BUNDLE_FILE"
echo -e "${BLUE}2. Click-to-Install File:${NC}         $FLATPAKREF_FILE"
echo -e "\n${YELLOW}How to install/update and run the application:${NC}"
echo -e "  • ${GREEN}Quick Update / Reinstall (Passwordless):${NC}"
echo -e "    flatpak install --user --reinstall -y $BUNDLE_FILE"
echo -e "    flatpak override --user --filesystem=~/.local/share/icons:rw --filesystem=~/.local/share/themes:rw --filesystem=~/.icons:rw --filesystem=~/.themes:rw $APP_ID"
echo -e "\n  • ${GREEN}Run the application:${NC}"
echo -e "    flatpak run $APP_ID"
echo -e "${GREEN}====================================================${NC}\n"

# If --install or -i flag was passed, reinstall immediately
if [[ "$*" == *"--install"* ]] || [[ "$*" == *"-i"* ]]; then
    echo -e "${YELLOW}Updating/reinstalling Flatpak user package...${NC}"
    flatpak install --user --reinstall -y "$BUNDLE_FILE"
    echo -e "${YELLOW}Configuring user theme & icon read-write permissions...${NC}"
    flatpak override --user --filesystem=~/.local/share/icons:rw --filesystem=~/.local/share/themes:rw --filesystem=~/.icons:rw --filesystem=~/.themes:rw "$APP_ID"
    echo -e "${YELLOW}Refreshing desktop database and icon cache...${NC}"
    rm -f "$HOME/.local/share/applications/$APP_ID.desktop" 2>/dev/null || true
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    gtk-update-icon-cache -q -f -t "$HOME/.local/share/flatpak/exports/share/icons/hicolor" 2>/dev/null || true
    update-desktop-database "$HOME/.local/share/flatpak/exports/share/applications" 2>/dev/null || true
    echo -e "${GREEN}✓ Flatpak updated and permissions configured successfully! Launch it with: flatpak run $APP_ID${NC}\n"
fi

