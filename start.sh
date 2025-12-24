#!/bin/bash

# Change to the Django project directory
cd sampledb

# Run database migrations
python manage.py migrate --no-input

# Collect static files
python manage.py collectstatic --no-input

# Create admin user if environment variables are set
python manage.py create_admin

# Start Gunicorn server
gunicorn sampledb.wsgi --bind 0.0.0.0:$PORT
