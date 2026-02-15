#!/bin/bash
# Manual database switcher script
# Usage: ./scripts/switch-db.sh [production_dev|classroom_economy]

if [ -z "$1" ]; then
    echo "Usage: ./scripts/switch-db.sh [production_dev|classroom_economy]"
    echo ""
    if [ -f ".env" ] && grep -q "^DATABASE_URL=" .env; then
        echo "Current DATABASE_URL:"
        grep "^DATABASE_URL=" .env
    else
        echo "No DATABASE_URL found in .env"
    fi
    exit 1
fi

DB_NAME=$1
ENV_FILE=".env"

case $DB_NAME in
    production_dev)
        DB_URL="postgresql://postgres:postgres@localhost:5432/production_dev"
        ;;
    classroom_economy)
        DB_URL="postgresql://postgres:postgres@localhost:5432/classroom_economy"
        ;;
    *)
        echo "Error: Invalid database name. Use 'production_dev' or 'classroom_economy'"
        exit 1
        ;;
esac

# Create .env file if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo "DATABASE_URL=$DB_URL" > "$ENV_FILE"
    echo "✓ Created .env file and set $DB_NAME database"
    echo "  DATABASE_URL=$DB_URL"
    exit 0
fi

# Check if DATABASE_URL line exists
if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
    # Update existing line
    sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$DB_URL|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    # Append new line
    echo "DATABASE_URL=$DB_URL" >> "$ENV_FILE"
fi

echo "✓ Switched to $DB_NAME database"
echo "  DATABASE_URL=$DB_URL"
