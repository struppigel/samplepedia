#!/bin/bash

# Change to the Django project directory
cd sampledb

# Run database migrations
python manage.py migrate --no-input

# Collect static files
python manage.py collectstatic --no-input

# Create superuser if environment variables are set
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    python manage.py createsuperuser --noinput || true
fi

# Start Gunicorn server
gunicorn sampledb.wsgi --bind 0.0.0.0:$PORT
