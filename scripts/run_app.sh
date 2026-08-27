#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script per avviare l'applicazione GnomeThemeManager (GUI o CLI)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"

# Se non vengono passati argomenti, avvia l'interfaccia grafica GTK4
if [ "$#" -eq 0 ]; then
    echo "Avvio interfaccia grafica GTK4..."
    python3 -m gnome_theme_manager gui
else
    # Altrimenti passa i parametri alla CLI
    python3 -m gnome_theme_manager.cli.main "$@"
fi
