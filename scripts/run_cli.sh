#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# ==============================================================================
# Wrapper script to run GnomeThemeManager CLI
# ==============================================================================

set -e

# Determine project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Activate virtual environment if present
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# If gnome-theme-manager is installed use the command, otherwise use python3 -m
if command -v gnome-theme-manager &> /dev/null; then
    gnome-theme-manager "$@"
else
    python3 -m gnome_theme_manager.cli.main "$@"
fi
