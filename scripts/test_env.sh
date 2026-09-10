#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# =============================================================================
# GnomeThemeManager - Development and Test Environment Setup Script
# =============================================================================
# This script:
# 1. Checks for Python 3 and required system packages (PyGObject).
# 2. Creates the virtual environment (.venv) with --system-site-packages support.
# 3. Installs and updates runtime and development dependencies (pytest, ruff, etc.).
# 4. Installs the package in editable mode (pip install -e .).
# 5. Runs a diagnostic verification check.
# =============================================================================

set -e

# Terminal output colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Navigate to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  Environment Setup: GnomeThemeManager                ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 not found. Install Python with:${NC}"
    echo "  sudo apt update && sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}✓ Found:${NC} $PYTHON_VERSION"

# 2. Check Ubuntu system dependencies for PyGObject (GSettings / Gio)
echo -e "\n${BLUE}[1/4] Checking GNOME/PyGObject system dependencies...${NC}"
if ! dpkg -s python3-gi &> /dev/null; then
    echo -e "${YELLOW}[WARNING] Some recommended system packages do not appear to be installed.${NC}"
    echo "To ensure full compatibility with GSettings on Ubuntu, run:"
    echo -e "${YELLOW}  sudo apt update && sudo apt install -y python3-gi libglib2.0-0 gnome-shell-extension-user-theme${NC}"
else
    echo -e "${GREEN}✓ System package python3-gi is present.${NC}"
fi

# 3. Create Virtual Environment (.venv)
echo -e "\n${BLUE}[2/4] Setting up virtual environment (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    echo "Creating new virtualenv with access to system site packages..."
    python3 -m venv --system-site-packages .venv
    echo -e "${GREEN}✓ Folder .venv created successfully.${NC}"
else
    echo -e "${GREEN}✓ Virtualenv .venv already exists.${NC}"
fi

# 4. Activate and install dependencies
echo -e "\n${BLUE}[3/4] Installing dependencies and local package...${NC}"
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip --quiet
pip install -e .[dev] --quiet

echo -e "${GREEN}✓ Dependencies installed (pytest, pytest-cov, ruff, gnome_theme_manager).${NC}"

# 5. Diagnostic import and verification test
echo -e "\n${BLUE}[4/4] Running diagnostic verification...${NC}"
python3 -c "
import sys
from gnome_theme_manager.core import ThemeManager, PresetManager

manager = ThemeManager()
status = manager.get_system_status()

print('  - PyGObject / GSettings available:  ', status.gsettings_available)
print('  - GNOME Shell Theme support:        ', status.shell_theme_supported)
print('  - User themes directory:            ', status.user_themes_path)
print('  - User icons directory:             ', status.user_icons_path)
print('  - Available presets:                ', len(manager.list_presets()))
"

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  ✓ Environment ready for use!                       ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "To activate the environment in your current shell, run:\n"
echo -e "  ${YELLOW}source .venv/bin/activate${NC}\n"
echo -e "To run the complete test suite:\n"
echo -e "  ${YELLOW}pytest -v${NC}\n"
echo -e "To use the manager CLI:\n"
echo -e "  ${YELLOW}gnome-theme-manager current${NC}"
echo -e "  ${YELLOW}gnome-theme-manager list${NC}"
echo -e "  ${YELLOW}gnome-theme-manager preset list${NC}\n"
