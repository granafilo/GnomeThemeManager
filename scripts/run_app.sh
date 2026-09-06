#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Script to launch GnomeThemeManager (GUI or CLI)
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

# If no arguments are passed, launch the GTK4 graphical interface
if [ "$#" -eq 0 ]; then
    echo "Launching GTK4 graphical interface..."
    python3 -m gnome_theme_manager gui
else
    # Otherwise forward arguments to the CLI
    python3 -m gnome_theme_manager.cli.main "$@"
fi
