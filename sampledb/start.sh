#!/bin/bash

# Run database migrations
python manage.py migrate --no-input

# Collect static files
python manage.py collectstatic --no-input

# Start Gunicorn server
gunicorn sampledb.wsgi --bind 0.0.0.0:$PORT
