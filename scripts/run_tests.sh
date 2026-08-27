#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script per eseguire la suite di test e i controlli di qualità
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

echo "========================================"
echo " 1. Running Pytest Suite"
echo "========================================"

if [ -f "$PROJECT_ROOT/.venv/bin/pytest" ]; then
    "$PROJECT_ROOT/.venv/bin/pytest" -v --cov=gnome_theme_manager
elif command -v pytest &> /dev/null; then
    pytest -v --cov=gnome_theme_manager
else
    echo "Errore: pytest non trovato. Esegui prima ./scripts/install_dependencies.sh"
    exit 1
fi

echo ""
echo "========================================"
echo " 2. Running Ruff Linter & Format Checks"
echo "========================================"

RUFF_BIN="ruff"
if [ -f "$PROJECT_ROOT/.venv/bin/ruff" ]; then
    RUFF_BIN="$PROJECT_ROOT/.venv/bin/ruff"
fi

if command -v "$RUFF_BIN" &> /dev/null || [ -f "$RUFF_BIN" ]; then
    "$RUFF_BIN" check src tests
    "$RUFF_BIN" format --check src tests
    echo "✓ Ruff checks e formatting superati!"
else
    echo "Ruff non installato (opzionale)."
fi

echo ""
echo "========================================"
echo " 3. Running Mypy Type Check"
echo "========================================"

MYPY_BIN="mypy"
if [ -f "$PROJECT_ROOT/.venv/bin/mypy" ]; then
    MYPY_BIN="$PROJECT_ROOT/.venv/bin/mypy"
fi

if command -v "$MYPY_BIN" &> /dev/null || [ -f "$MYPY_BIN" ]; then
    "$MYPY_BIN" --strict src
    echo "✓ Mypy type check superato!"
else
    echo "Mypy non installato (opzionale)."
fi

echo ""
echo "✓ Tutti i test e controlli completati con successo!"
