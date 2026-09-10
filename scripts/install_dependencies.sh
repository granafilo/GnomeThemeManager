#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# System and Development Dependency Installation Script
#
# Usage:
#   ./scripts/install_dependencies.sh          # Configure .venv and local packages
#   ./scripts/install_dependencies.sh --global # Also install test tools globally (pytest, mypy, ruff)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

GLOBAL_INSTALL=0
for arg in "$@"; do
    if [ "$arg" == "--global" ] || [ "$arg" == "-g" ] || [ "$arg" == "--system" ]; then
        GLOBAL_INSTALL=1
    fi
done

echo "======================================================"
echo " 1. Checking/Installing System Packages (APT)"
echo "======================================================"

PACKAGES_TO_INSTALL=()

# Check venv / ensurepip support
if ! python3 -m venv --help &>/dev/null || ! python3 -c "import ensurepip" 2>/dev/null; then
    PACKAGES_TO_INSTALL+=(python3-venv python3.12-venv python3-pip)
fi

# Check PyGObject / GTK4 / Libadwaita
if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
    PACKAGES_TO_INSTALL+=(python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1)
fi

# If global installation requested (outside venv)
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
    echo "Option --global detected: installing system packages..."
    PACKAGES_TO_INSTALL+=(python3-pytest python3-pytest-cov mypy)
fi

if [ ${#PACKAGES_TO_INSTALL[@]} -gt 0 ]; then
    echo "Installing APT packages: ${PACKAGES_TO_INSTALL[*]}"
    if command -v sudo &> /dev/null; then
        sudo apt install -y "${PACKAGES_TO_INSTALL[@]}"
    else
        apt install -y "${PACKAGES_TO_INSTALL[@]}"
    fi
else
    echo "✓ All required APT system packages are already installed."
fi

# Global installation of Ruff if requested
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
    if ! command -v ruff &> /dev/null; then
        echo "Installing Ruff globally..."
        if command -v snap &> /dev/null; then
            if command -v sudo &> /dev/null; then
                sudo snap install ruff --classic || pip install --user --break-system-packages ruff || true
            else
                snap install ruff --classic || pip install --user --break-system-packages ruff || true
            fi
        else
            pip install --user --break-system-packages ruff || true
        fi
    else
        echo "✓ Ruff already available globally."
    fi
fi

echo ""
echo "======================================================"
echo " 2. Virtual Environment Setup (.venv)"
echo "======================================================"

if [ -d ".venv" ] && [ ! -f ".venv/bin/activate" ]; then
    echo "Removing previous partial/corrupted virtualenv..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtualenv with access to system-site-packages..."
    python3 -m venv --system-site-packages .venv
else
    echo "✓ Virtualenv .venv ready."
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo ""
echo "======================================================"
echo " 3. Installing Python Dependencies in Virtualenv"
echo "======================================================"
pip install --upgrade pip
pip install -e ".[dev]"
pip install mypy ruff

echo ""
echo "======================================================"
echo " 4. Compiling gettext Translations"
echo "======================================================"
if [ -f "scripts/compile_translations.py" ]; then
    python3 scripts/compile_translations.py
fi

echo ""
echo "======================================================"
echo " ✓ Installation completed successfully!"
echo "======================================================"
echo "To run tests:             ./scripts/run_tests.sh"
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
    echo "                          or 'pytest -v' / 'ruff check .' (also outside venv)"
fi
echo "To launch the application: ./scripts/run_app.sh"

