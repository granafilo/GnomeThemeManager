#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script di Pulizia Repository - GNOME Theme Manager
# ==============================================================================
# Rimuove artefatti di build AppImage, cache Python/pytest, log temporanei e
# file non necessari per mantenere la repository git pulita.
# ==============================================================================

set -e

# Modello dei colori ANSI per output chiaro a terminale
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  🧹 Pulizia Repository GNOME Theme Manager${NC}"
echo -e "${BLUE}====================================================${NC}"

cd "$ROOT_DIR"

# 1. Directory e file di build AppImage
echo -e "\n${YELLOW}[1/4] Rimuovo directory ed artefatti di build AppImage...${NC}"
rm -rf AppDir/
rm -rf dist/
rm -rf squashfs-root/
rm -f *.AppImage
rm -f appimagetool-*.AppImage

# 2. Cache Python, pytest e ruff
echo -e "\n${YELLOW}[2/4] Rimuovo cache Python, pytest e ruff...${NC}"
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
rm -rf .pytest_cache/
rm -rf .ruff_cache/
rm -rf .coverage
rm -rf htmlcov/

# 3. File temporanei, log e file di testo locali
echo -e "\n${YELLOW}[3/4] Rimuovo file temporanei, backup e log di debug...${NC}"
find . -type f \( -name "*.log" -o -name "*.tmp" -o -name "*.bak" -o -name "*.backup" \) -delete 2>/dev/null || true
rm -f gtk414-warnings.txt README_old.md README_backup.md *.md.bak

# 4. Riepilogo ed esito
echo -e "\n${YELLOW}[4/4] Verifica dello stato della repository...${NC}"
COUNT=$(find . -type f -not -path './.git/*' -not -path './.venv/*' | wc -l)

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}  ✅ PULIZIA COMPLETATA CON SUCCESSO!${NC}"
echo -e "${GREEN}  Totale file sorgente/progetto (escluso .venv e .git): ${COUNT}${NC}"
echo -e "${GREEN}====================================================${NC}"
