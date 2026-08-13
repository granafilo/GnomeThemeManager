#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script per eseguire la suite di test globale (Pytest + Ruff)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

echo "========================================"
echo " Running Pytest Unit & Integration Tests"
echo "========================================"

# Se pytest-cov è installato usa il report di coverage, altrimenti esegui pytest normale
if python3 -c "import pytest_cov" 2>/dev/null; then
    pytest -v --cov=gnome_theme_manager
else
    pytest -v
fi

echo ""
echo "========================================"
echo " Running Ruff Linter Checks"
echo "========================================"
if command -v ruff &> /dev/null; then
    ruff check src tests
    echo "✓ Ruff checks passed cleanly!"
else
    echo "Ruff non installato (opzionale: pip install ruff)"
fi
