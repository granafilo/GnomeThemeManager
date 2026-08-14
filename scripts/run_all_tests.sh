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
# Se pytest-cov è installato usa il report di coverage, altrimenti esegui pytest normale
if [ -f "$PROJECT_ROOT/.venv/bin/pytest" ]; then
    if "$PROJECT_ROOT/.venv/bin/pytest" --help 2>&1 | grep -q -- "--cov"; then
        "$PROJECT_ROOT/.venv/bin/pytest" -v --cov=gnome_theme_manager
    else
        "$PROJECT_ROOT/.venv/bin/pytest" -v
    fi
else
    if pytest --help 2>&1 | grep -q -- "--cov"; then
        pytest -v --cov=gnome_theme_manager
    else
        pytest -v
    fi
fi

echo ""
echo "========================================"
echo " Running Ruff Linter & Format Checks"
echo "========================================"

RUFF_BIN="ruff"
if [ -f "$PROJECT_ROOT/.venv/bin/ruff" ]; then
    RUFF_BIN="$PROJECT_ROOT/.venv/bin/ruff"
fi

if command -v "$RUFF_BIN" &> /dev/null || [ -f "$RUFF_BIN" ]; then
    "$RUFF_BIN" check src tests
    "$RUFF_BIN" format --check src tests
    echo "✓ Ruff checks and formatting passed cleanly!"
else
    echo "Ruff non installato (opzionale: pip install ruff)"
fi
