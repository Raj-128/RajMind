#!/bin/bash
set -e
python manage.py collectstatic --noinput
python manage.py migrate
# Render/Railway provide the port in $PORT; 8000 for local Docker.
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout 120
