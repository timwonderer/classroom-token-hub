#!/bin/bash
# Deploy application updates. Access restrictions are managed in Cloudflare Access.

echo "=== Deploying Updates ==="

# Check if running from production directory
if [ -d "/root/classroom-economy" ]; then
    DEPLOY_DIR="/root/classroom-economy"
    echo "Deploying to production: $DEPLOY_DIR"
else
    DEPLOY_DIR="/home/user/classroom-economy"
    echo "Deploying to development: $DEPLOY_DIR"
fi

cd "$DEPLOY_DIR" || exit 1

echo ""
echo "Step 1: Pulling latest changes from git..."
git fetch origin
git pull origin main

echo ""
echo "Step 2: Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo ""
echo "Step 3: Running database migration..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    flask db upgrade
else
    echo "Warning: venv not found, attempting system python..."
    python -m flask db upgrade
fi

echo ""
echo "Step 4: Reloading application..."
touch wsgi.py

echo "Deployment executed (branch: main). Cloudflare Access policy is unchanged."
