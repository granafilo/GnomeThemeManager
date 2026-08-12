#!/usr/bin/env bash
# =============================================================================
# GnomeThemeManager - Helper per mostrare i temi attualmente attivi
# Usage: ./scripts/themeCurrent.sh
# =============================================================================

# Calcola il percorso radice del progetto indipendentemente da dove viene eseguito lo script
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Esegue il comando 'current' impostando PYTHONPATH sulla cartella src
PYTHONPATH="$PROJECT_ROOT/src" python3 -m gnome_theme_manager.cli current "$@"
