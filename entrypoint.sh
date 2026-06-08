#!/bin/bash

set -e

# Navigate to the Django project directory
cd /app/tafakari

# Collect static files if not skipped
if [ "$SKIP_COLLECTSTATIC" != "1" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear
fi

echo "Starting application..."
exec "$@"
