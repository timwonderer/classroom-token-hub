#!/bin/bash
# scripts/generate_canonical_image.sh
# Automates the creation, migration, seeding, and dumping of the canonical DB image.

set -e

IMAGE_NAME="artifacts/canonical_v2_image.sql"
DB_NAME="canonical_v2_seed"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/$DB_NAME"

# Required keys for the app to start
export SECRET_KEY="dev-secret-key-change-in-production"
export ENCRYPTION_KEY="lgEPpAotjW6LI3RdtxClm3Ybr7SXyiweIXxj1IoMado="
export PEPPER_KEY="65rebL7nEzEj7M0qdXUVEaFqvKbuUobvbgf5i0Xf3zc"
export FLASK_ENV="development"
export FLASK_APP="wsgi.py"
# Skip load_dotenv override by setting CI=true
export CI=true

echo "===================================================="
echo " GENERATING CANONICAL DB IMAGE: CANONICAL-IMG-001 v1.0"
echo "===================================================="

# 1. SETUP CLEAN DB
echo "[1/4] Creating clean database: $DB_NAME"
dropdb --if-exists $DB_NAME
createdb $DB_NAME

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 2. RUN MIGRATIONS
echo "[2/4] Running migrations..."
flask db upgrade

# 3. SEED DATA
echo "[3/4] Seeding deterministic adversarial data..."
export PYTHONPATH=$PYTHONPATH:.
python3 scripts/seed_canonical_v2.py

# 4. GENERATE DUMP
echo "[4/4] Generating SQL dump: $IMAGE_NAME"
pg_dump $DATABASE_URL > $IMAGE_NAME

echo "===================================================="
echo " SUCCESS: Canonical image generated at $IMAGE_NAME"
echo "===================================================="
