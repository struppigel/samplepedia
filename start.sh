#!/bin/bash
# Railway start command. Static files are collected at build time (railway.json).
# Stop on the first failure so a failed migration never starts the web server.
set -euo pipefail

cd sampledb

python manage.py migrate --no-input

# Create admin user if environment variables are set
python manage.py create_admin

# Create contributor group with permissions
python manage.py create_contributor_group

# exec so gunicorn receives Railway's stop signals directly
exec gunicorn sampledb.wsgi --bind "0.0.0.0:${PORT}"
