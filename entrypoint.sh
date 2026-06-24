#!/bin/sh
set -e

# Migrations + fichiers statiques (whitenoise manifest) au démarrage.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Serveur ASGI (HTTP + WebSocket Channels).
exec daphne -b 0.0.0.0 -p "${PORT:-8080}" config.asgi:application
