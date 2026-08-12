#!/usr/bin/env bash
# Shortcut alla cartella scripts/test_env.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/test_env.sh" "$@"
