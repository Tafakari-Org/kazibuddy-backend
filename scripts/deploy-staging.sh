#!/bin/bash
set -e

# Configuration
PROJECT_DIR="/var/www/kazibuddy-backend/kazibuddy-backend-staging"
ENV_FILE="/var/www/kazibuddy-backend/kazibuddy-backend-staging/tafakari/.env.staging"
UPLOADS_DIR="/var/www/kazibuddy-backend/uploads-staging"

echo "Starting staging deployment..."

# Navigate to project directory
cd $PROJECT_DIR

# Pull latest changes
echo "Pulling latest changes from test branch..."
git pull origin test

# Check if .env.staging exists
if [ ! -f "$ENV_FILE" ]; then
    echo "$ENV_FILE not found! Please create it before deploying."
    exit 1
fi

# Ensure staging directories exist with correct ownership
echo "Setting staging directory permissions..."
mkdir -p $UPLOADS_DIR/images
mkdir -p $UPLOADS_DIR/documents
mkdir -p $PROJECT_DIR/tafakari/logs-staging
chown -R 1000:1000 $UPLOADS_DIR
chmod -R 755 $UPLOADS_DIR
chown -R 1000:1000 $PROJECT_DIR/tafakari/logs-staging
chmod -R 755 $PROJECT_DIR/tafakari/logs-staging

# Build and restart staging containers
echo "Building and restarting staging containers..."
docker compose -f docker-compose.staging.yml up -d --build

# Run migrations
# echo "Running database migrations..."
# docker compose -f docker-compose.staging.yml exec web python /app/tafakari/manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
docker compose -f docker-compose.staging.yml exec web python /app/tafakari/manage.py collectstatic --noinput --clear

# Clean up old images
echo "Cleaning up old unused images..."
docker image prune -f

echo "Staging deployment finished successfully!"
