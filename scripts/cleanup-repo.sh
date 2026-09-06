#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Repository Cleanup Script - GNOME Theme Manager
# ==============================================================================
# Removes AppImage/Flatpak build artifacts, Python/pytest caches, temporary logs,
# and unnecessary files to keep the git repository clean.
# ==============================================================================

set -e

# ANSI colors for clear terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  🧹 Cleaning GNOME Theme Manager Repository${NC}"
echo -e "${BLUE}====================================================${NC}"

cd "$ROOT_DIR"

# 1. Packaging and build directories/artifacts (Flatpak & legacy AppImage)
echo -e "\n${YELLOW}[1/4] Removing build directories and artifacts (Flatpak & AppImage)...${NC}"
rm -rf AppDir/
rm -rf dist/
rm -rf squashfs-root/
rm -rf build-dir/
rm -rf repo/
rm -rf .flatpak-builder/
rm -rf scripts/.flatpak-builder/
rm -f *.AppImage
rm -f appimagetool-*.AppImage
rm -f *.flatpak
rm -f *.flatpakref

# 2. Python, pytest, and ruff caches
echo -e "\n${YELLOW}[2/4] Removing Python, pytest, and ruff caches...${NC}"
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
rm -rf .pytest_cache/
rm -rf .ruff_cache/
rm -rf .coverage
rm -rf htmlcov/

# 3. Temporary files, backups, and debug logs
echo -e "\n${YELLOW}[3/4] Removing temporary files, backups, and debug logs...${NC}"
find . -type f \( -name "*.log" -o -name "*.tmp" -o -name "*.bak" -o -name "*.backup" \) -delete 2>/dev/null || true
rm -f gtk414-warnings.txt README_old.md README_backup.md *.md.bak

# 4. Summary and status check
echo -e "\n${YELLOW}[4/4] Verifying repository status...${NC}"
COUNT=$(find . -type f -not -path './.git/*' -not -path './.venv/*' | wc -l)

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}  ✅ CLEANUP COMPLETED SUCCESSFULLY!${NC}"
echo -e "${GREEN}  Total source/project files (excluding .venv and .git): ${COUNT}${NC}"
echo -e "${GREEN}====================================================${NC}"

