#!/usr/bin/env bash
# Installation script for MDMG Noticias
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$(dirname "$PROJECT_DIR")/venv"
STATIC_DIR="$(dirname "$PROJECT_DIR")/public_html/static"

echo "==> Creating virtual environment at $VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

echo "==> Setting up environment file"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo ""
    echo "  !! .env created from .env.example"
    echo "  !! Edit $PROJECT_DIR/.env and fill in your database credentials and SECRET_KEY before continuing."
    echo ""
    read -rp "  Press Enter once you have filled in .env..." _
fi

echo "==> Running database migrations"
python "$PROJECT_DIR/manage.py" migrate

echo "==> Collecting static files"
mkdir -p "$STATIC_DIR"
python "$PROJECT_DIR/manage.py" collectstatic --noinput

echo "==> Creating superuser (for the admin panel)"
python "$PROJECT_DIR/manage.py" createsuperuser

echo ""
echo "==> Installation complete."
echo ""
echo "    Start the development server with:"
echo "      source $VENV_DIR/bin/activate"
echo "      python $PROJECT_DIR/manage.py runserver"
echo ""
echo "    For production, configure Gunicorn and a reverse proxy (Apache/Nginx)."
echo "    See README.md for the recommended cron jobs."
