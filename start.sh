#!/bin/bash

# VexMail Startup Script

set -e

echo "Starting VexMail..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Creating from example..."
    cp env.example .env
    echo "Please edit .env file with your configuration before running again."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker container..."
    # Wait for dependencies
    echo "Waiting for database..."
    while ! pg_isready -h postgres -p 5432 -U vexmail_user; do
        sleep 1
    done
    
    echo "Waiting for Redis..."
    while ! redis-cli -h redis -p 6379 ping; do
        sleep 1
    done
    
    echo "Waiting for MinIO..."
    while ! curl -f http://minio:9000/minio/health/live; do
        sleep 1
    done
    
    # Run database migrations
    echo "Running database migrations..."
    python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"
    
    echo "Starting VexMail application..."
    exec "$@"
else
    echo "Running locally..."
    
    # Check if Docker Compose is available
    if command -v docker-compose &> /dev/null; then
        echo "Starting services with Docker Compose..."
        docker-compose up -d postgres redis minio
        
        echo "Waiting for services to be ready..."
        sleep 10
        
        # Run migrations
        echo "Running database migrations..."
        python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"
        
        echo "Starting VexMail application..."
        python app.py
    else
        echo "Docker Compose not found. Please install Docker and Docker Compose."
        echo "Or run the services manually: PostgreSQL, Redis, and MinIO."
        exit 1
    fi
fi
