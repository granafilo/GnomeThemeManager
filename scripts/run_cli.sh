#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script wrapper per eseguire la CLI di GnomeThemeManager
# ==============================================================================

set -e

# Determina la radice del progetto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Attiva l'ambiente virtuale se presente
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Se gnome-theme-manager è installato usa il comando, altrimenti usa python3 -m
if command -v gnome-theme-manager &> /dev/null; then
    gnome-theme-manager "$@"
else
    python3 -m gnome_theme_manager.cli.main "$@"
fi
