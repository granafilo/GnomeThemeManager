#!/bin/bash
# Script per testare rapidamente a riga di comando le traduzioni del manager.

set -e

# Muoviti nella root del progetto
cd "$(dirname "$0")/.."

echo "========================================="
echo "Test di traduzione: ITALIANO"
echo "========================================="
export LANG=it_IT.UTF-8
export LC_ALL=it_IT.UTF-8
PYTHONPATH=src .venv/bin/python3 -m gnome_theme_manager current

echo ""
echo "========================================="
echo "Test di traduzione: INGLESE"
echo "========================================="
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
PYTHONPATH=src .venv/bin/python3 -m gnome_theme_manager current
