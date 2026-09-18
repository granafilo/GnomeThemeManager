#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Flatpak Build Script - GNOME Theme Manager
# ==============================================================================
# This script cleans previous build directories, runs flatpak-builder,
# and exports the offline bundle (.flatpak).
# ==============================================================================

set -eo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

APP_NAME="GNOMEThemeManager"
APP_ID="io.github.granafilo.ThemeManager"
VERSION="1.5.3"
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

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  Starting Flatpak generation for ${APP_NAME} v${VERSION}${NC}"
echo -e "${BLUE}====================================================${NC}"

# ------------------------------------------------------------------------------
# 1. Check required tools and Flathub repository
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/4] Checking Flatpak tools and runtime...${NC}"

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
echo -e "\n${YELLOW}[2/4] Cleaning cache and build directories...${NC}"
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
echo -e "\n${YELLOW}[3/4] Running flatpak-builder (downloading SDK/Runtime if needed)...${NC}"

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
echo -e "\n${YELLOW}[4/4] Generating offline bundle (.flatpak)...${NC}"

flatpak build-bundle "$REPO_DIR" "$BUNDLE_FILE" "$APP_ID" stable

echo -e "${GREEN}✓ Offline bundle generated: $BUNDLE_FILE${NC}"

# ------------------------------------------------------------------------------
# Summary and User Instructions
# ------------------------------------------------------------------------------
echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}  ✓ FLATPAK PACKAGE CREATED SUCCESSFULLY!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${BLUE}Standalone Offline Bundle:${NC} $BUNDLE_FILE"
echo -e "\n${YELLOW}How to install/update and run the application:${NC}"
echo -e "  • ${GREEN}Quick Update / Reinstall (Passwordless):${NC}"
echo -e "    flatpak install --user --reinstall -y $BUNDLE_FILE"
echo -e "    flatpak override --user --filesystem=~/.local/share/icons:create --filesystem=~/.local/share/themes:create --filesystem=~/.local/share/gnome-shell/extensions:create --filesystem=~/.icons:create --filesystem=~/.themes:create $APP_ID"
echo -e "\n  • ${GREEN}Run the application:${NC}"
echo -e "    flatpak run $APP_ID"
echo -e "${GREEN}====================================================${NC}\n"

# If --install or -i flag was passed, reinstall immediately
if [[ "$*" == *"--install"* ]] || [[ "$*" == *"-i"* ]]; then
    echo -e "${YELLOW}Creating user theme, icon, and extension directories on host if missing...${NC}"
    mkdir -p "$HOME/.local/share/themes" "$HOME/.local/share/icons" "$HOME/.local/share/gnome-shell/extensions" "$HOME/.local/share/applications"

    echo -e "${YELLOW}Updating/reinstalling Flatpak user package...${NC}"
    flatpak install --user --reinstall -y "$BUNDLE_FILE"

    echo -e "${YELLOW}Configuring user theme, icon & extension permissions...${NC}"
    flatpak override --user \
        --filesystem=~/.local/share/icons:create \
        --filesystem=~/.local/share/themes:create \
        --filesystem=~/.local/share/gnome-shell/extensions:create \
        --filesystem=~/.icons:create \
        --filesystem=~/.themes:create \
        "$APP_ID"

    echo -e "${YELLOW}Integrating application launcher and icons for immediate desktop visibility...${NC}"
    # Copy desktop file to ~/.local/share/applications/ so GNOME Shell displays it immediately without session reload
    EXPORTED_DESKTOP="$HOME/.local/share/flatpak/exports/share/applications/$APP_ID.desktop"
    TARGET_DESKTOP="$HOME/.local/share/applications/$APP_ID.desktop"
    if [ -f "$EXPORTED_DESKTOP" ]; then
        cp -f "$EXPORTED_DESKTOP" "$TARGET_DESKTOP"
        chmod +x "$TARGET_DESKTOP" 2>/dev/null || true
    fi

    # Export hicolor icons so GNOME Shell launcher displays the icon immediately
    for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512 scalable; do
        SRC_ICON="$HOME/.local/share/flatpak/exports/share/icons/hicolor/$size/apps/$APP_ID"
        DEST_DIR="$HOME/.local/share/icons/hicolor/$size/apps"
        mkdir -p "$DEST_DIR"
        for f in "${SRC_ICON}".*; do
            if [ -f "$f" ]; then
                cp -f "$f" "$DEST_DIR/" 2>/dev/null || true
            fi
        done
    done

    echo -e "${YELLOW}Refreshing desktop database and icon cache...${NC}"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    update-desktop-database "$HOME/.local/share/flatpak/exports/share/applications" 2>/dev/null || true
    gtk-update-icon-cache -q -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    gtk-update-icon-cache -q -f -t "$HOME/.local/share/flatpak/exports/share/icons/hicolor" 2>/dev/null || true

    echo -e "${GREEN}✓ Flatpak updated and integrated successfully! Visible in app menu without session restart.${NC}"
    echo -e "${GREEN}  Launch it from app menu or run: flatpak run $APP_ID${NC}\n"
fi
