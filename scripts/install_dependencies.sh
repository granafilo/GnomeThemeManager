#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script di installazione dipendenze di sistema e di sviluppo
#
# Utilizzo:
#   ./scripts/install_dependencies.sh          # Configura .venv e pacchetti locali
#   ./scripts/install_dependencies.sh --global # Installa anche i tool di test globalmente (pytest, mypy, ruff)
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
echo " 1. Verifica/Installazione pacchetti di sistema (APT)"
echo "======================================================"

PACKAGES_TO_INSTALL=()

# Controllo supporto venv / ensurepip
if ! python3 -m venv --help &>/dev/null || ! python3 -c "import ensurepip" 2>/dev/null; then
    PACKAGES_TO_INSTALL+=(python3-venv python3.12-venv python3-pip)
fi

# Controllo PyGObject / GTK4 / Libadwaita
if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
    PACKAGES_TO_INSTALL+=(python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1)
fi

# Se richiesta l'installazione globale (fuori da venv)
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
    echo "Opzione --global rilevata: installazione pacchetti di sistema..."
    PACKAGES_TO_INSTALL+=(python3-pytest python3-pytest-cov mypy)
fi

if [ ${#PACKAGES_TO_INSTALL[@]} -gt 0 ]; then
    echo "Installazione pacchetti APT: ${PACKAGES_TO_INSTALL[*]}"
    if command -v sudo &> /dev/null; then
        sudo apt install -y "${PACKAGES_TO_INSTALL[@]}"
    else
        apt install -y "${PACKAGES_TO_INSTALL[@]}"
    fi
else
    echo "✓ Tutti i pacchetti di sistema APT richiesti sono già installati."
fi

# Installazione globale di Ruff se richiesta
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
    if ! command -v ruff &> /dev/null; then
        echo "Installazione globale di Ruff..."
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
        echo "✓ Ruff già disponibile globalmente."
    fi
fi

echo ""
echo "======================================================"
echo " 2. Configurazione Virtual Environment (.venv)"
echo "======================================================"

if [ -d ".venv" ] && [ ! -f ".venv/bin/activate" ]; then
    echo "Rimozione virtualenv parziale/corrotto precedente..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo "Creazione virtualenv con accesso a system-site-packages..."
    python3 -m venv --system-site-packages .venv
else
    echo "✓ Virtualenv .venv pronto."
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo ""
echo "======================================================"
echo " 3. Installazione dipendenze Python nel virtualenv"
echo "======================================================"
pip install --upgrade pip
pip install -e ".[dev]"
pip install mypy ruff

echo ""
echo "======================================================"
echo " 4. Compilazione traduzioni gettext"
echo "======================================================"
if [ -f "scripts/compile_translations.py" ]; then
    python3 scripts/compile_translations.py
fi

echo ""
echo "======================================================"
echo " ✓ Installazione completata con successo!"
echo "======================================================"
echo "Per eseguire i test:       ./scripts/run_tests.sh"
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
    echo "                      oppure 'pytest -v' / 'ruff check .' (anche fuori dal venv)"
fi
echo "Per avviare l'applicazione: ./scripts/run_app.sh"
