#!/bin/bash
# Script to quickly test manager translations via CLI.

set -e

# Move to project root
cd "$(dirname "$0")/.."

echo "========================================="
echo "Translation Test: ITALIAN"
echo "========================================="
export LANG=it_IT.UTF-8
export LC_ALL=it_IT.UTF-8
PYTHONPATH=src .venv/bin/python3 -m gnome_theme_manager current

echo ""
echo "========================================="
echo "Translation Test: ENGLISH"
echo "========================================="
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
PYTHONPATH=src .venv/bin/python3 -m gnome_theme_manager current
