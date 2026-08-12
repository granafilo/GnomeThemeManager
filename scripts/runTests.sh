#!/usr/bin/env bash
# =============================================================================
# GnomeThemeManager - Helper per eseguire la suite completa di test (pytest)
# Usage: ./scripts/runTests.sh
# =============================================================================

# Calcola il percorso radice del progetto ed esegue pytest
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

python3 -m pytest -v "$@"
