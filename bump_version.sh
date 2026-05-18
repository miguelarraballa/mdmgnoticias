#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIT_FILE="$SCRIPT_DIR/feeds/__init__.py"
TOML_FILE="$SCRIPT_DIR/pyproject.toml"

# Read current version from __init__.py
current=$(grep -oP "(?<=__version__ = ')[^']+" "$INIT_FILE")

echo "Versión actual: $current"
read -rp "Nueva versión:  " new_version

if [[ -z "$new_version" ]]; then
  echo "Versión vacía. Sin cambios."
  exit 1
fi

# Update both files
sed -i "s/__version__ = '$current'/__version__ = '$new_version'/" "$INIT_FILE"
sed -i "s/^version = \"$current\"/version = \"$new_version\"/" "$TOML_FILE"

echo "Actualizado a $new_version en:"
echo "  $INIT_FILE"
echo "  $TOML_FILE"

# Reload gunicorn workers so the new version is served immediately
master_pid=$(pgrep -f "gunicorn.*config.wsgi" | head -1 || true)
if [[ -n "$master_pid" ]]; then
  kill -HUP "$master_pid"
  echo "Gunicorn recargado (PID $master_pid)"
else
  echo "Gunicorn no encontrado — recárgalo manualmente"
fi
