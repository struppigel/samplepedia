#!/bin/bash

# Change to the Django project directory
cd sampledb

# Run tests - fail build if tests fail
echo "Running tests..."
python manage.py test samples.test_task_submission --verbosity=1
if [ $? -ne 0 ]; then
    echo "Tests failed! Aborting deployment."
    exit 1
fi
echo "All tests passed!"

# Run database migrations
python manage.py migrate --no-input

# Collect static files
python manage.py collectstatic --no-input

# Create admin user if environment variables are set
python manage.py create_admin

# Create contributor group with permissions
python manage.py create_contributor_group

# Start Gunicorn server
gunicorn sampledb.wsgi --bind 0.0.0.0:$PORT
