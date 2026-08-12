#!/usr/bin/env bash
# =============================================================================
# GnomeThemeManager - Helper per elencar i temi disponibili
# Usage: ./scripts/themeList.sh [--type gtk|icon|cursor|shell|all] [--user-only]
# =============================================================================

# Calcola il percorso radice del progetto indipendentemente da dove viene eseguito lo script
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Esegue il comando 'list' impostando PYTHONPATH sulla cartella src
PYTHONPATH="$PROJECT_ROOT/src" python3 -m gnome_theme_manager.cli list "$@"
