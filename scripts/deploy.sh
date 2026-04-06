#!/bin/bash
set -e

# Configuration
PROJECT_DIR="/var/www/kazibuddy-backend/kazibuddy-backend"
ENV_FILE="/var/www/kazibuddy-backend/kazibuddy-backend/.env.prod"
UPLOADS_DIR="/var/www/kazibuddy-backend/uploads"

echo "Starting deployment..."

# Navigate to project directory
cd $PROJECT_DIR

# Pull latest changes
echo "Pulling latest changes..."
git pull origin deployment

# Check if .env.prod exists
if [ ! -f "$ENV_FILE" ]; then
    echo "$ENV_FILE not found! Please create it before deploying."
    exit 1
fi

# Ensure upload directory exists with correct ownership
echo "Setting upload directory permissions..."
mkdir -p $UPLOADS_DIR/images
mkdir -p $UPLOADS_DIR/documents
chown -R 1000:1000 $UPLOADS_DIR
chmod -R 755 $UPLOADS_DIR

# Build and restart containers
echo "Building and restarting containers..."
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
# echo "Running database migrations..."
# docker compose -f docker-compose.prod.yml exec web python /app/tafakari/manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
docker compose -f docker-compose.prod.yml exec web python /app/tafakari/manage.py collectstatic --noinput --clear

# Clean up old images
echo "Cleaning up old unused images..."
docker image prune -f

echo "Deployment finished successfully!"