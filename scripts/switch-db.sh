#!/bin/bash
# Manual database switcher script
# Usage: ./scripts/switch-db.sh [production_dev|classroom_economy]

if [ -z "$1" ]; then
    echo "Usage: ./scripts/switch-db.sh [production_dev|classroom_economy]"
    echo ""
    echo "Current DATABASE_URL:"
    grep "^DATABASE_URL=" .env
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

# Update .env file
sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$DB_URL|" "$ENV_FILE"
rm -f "$ENV_FILE.bak"

echo "✓ Switched to $DB_NAME database"
echo "  DATABASE_URL=$DB_URL"
