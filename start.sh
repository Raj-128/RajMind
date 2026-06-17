#!/bin/bash
set -e
python manage.py collectstatic --noinput
python manage.py migrate
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000